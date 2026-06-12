import os
import re
import json
import logging
import threading
import time as time_mod
import atexit
from datetime import datetime, time as dtime, timezone, timedelta
from flask import Flask, abort, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import (
    fetch_multi_day_lhb,
    get_jjyd, parse_jjyd,
    get_top_volume, parse_top_volume, compute_capital_signals,
)
from kpl_api import MAX_SERIES_DAYS, fetch_interval_all, fetch_interval_series

CN_TZ = timezone(timedelta(hours=8))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fupan.app")


def _now_cn():
    return datetime.now(CN_TZ)

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "data.json")
REVIEWS_DIR = os.path.join(os.path.dirname(__file__), "data", "reviews")

# 复盘报告文件名约定：<YYYY-MM-DD>_<type>.md，type 取以下白名单。
REVIEW_TYPES = {"fupan": "日复盘", "jieli": "连板接力", "jingjia": "集合竞价"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_cache = {
    "data": [],
    "trading_days": [],
    "updated_at": "",
    "lhb_at": 0.0,
    "jjyd": [],
    "jjyd_at": 0.0,
    "top_volume": [],
    "capital_signals": {},
    "capital_at": 0.0,
    "kpl_interval": {},
    "kpl_at": 0.0,
}
_lhb_lock = threading.Lock()
_jjyd_lock = threading.Lock()
_capital_lock = threading.Lock()
_kpl_lock = threading.Lock()
# 磁盘写专用锁：LHB/KPL 两条刷新路径各持自己的数据锁进入 _save_to_disk，
# 共用同一个 .tmp 路径，没有这把锁原子写在并发下不原子
_disk_lock = threading.Lock()
# /api/kpl_interval 自选区间查询缓存 {(start,end,series): (ts, payload)}
_kpl_query_cache = {}
_kpl_query_lock = threading.Lock()


def _mark_cooldown(stamp_key, ttl):
    """抓取失败后把时间戳回拨半个 TTL：冷却 ttl/2 秒再试，避免每次请求都打远端。"""
    _cache[stamp_key] = time_mod.time() - ttl / 2


def _load_from_disk():
    if not os.path.exists(DATA_FILE):
        return False
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            d = json.load(f)
        _cache["data"] = d.get("data", [])
        _cache["trading_days"] = d.get("trading_days", [])
        _cache["jjyd"] = d.get("jjyd", [])
        _cache["top_volume"] = d.get("top_volume", [])
        _cache["capital_signals"] = d.get("capital_signals", {})
        _cache["kpl_interval"] = d.get("kpl_interval", {})
        _cache["updated_at"] = d.get("updated_at", "")
        return bool(_cache["data"])
    except Exception:
        log.exception("读取 %s 失败，按无本地数据处理", DATA_FILE)
        return False


def _save_to_disk():
    """把当前缓存写回 data/data.json，使服务器重启后能读到最新数据。"""
    with _disk_lock:
        _save_to_disk_locked()


def _save_to_disk_locked():
    try:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": _cache["updated_at"],
                "trading_days": _cache["trading_days"],
                "data": _cache["data"],
                "jjyd": _cache["jjyd"],
                "top_volume": _cache["top_volume"],
                "capital_signals": _cache["capital_signals"],
                "kpl_interval": _cache["kpl_interval"],
            }, f, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)
    except Exception:
        log.exception("写回 %s 失败（内存缓存不受影响）", DATA_FILE)


def _lhb_ttl():
    """多日龙虎榜 TTL（秒）：
    - 交易时段（9:00–15:30）→ 10 分钟
    - 收盘后至 20:00 仍 → 10 分钟（盘后数据出来不必等 18:30 cron）
    - 其余（深夜/清晨/周末）→ 60 分钟
    """
    now = _now_cn()
    if now.weekday() >= 5:
        return 3600
    t = now.time()
    if dtime(9, 0) <= t <= dtime(20, 0):
        return 600
    return 3600


def refresh_lhb(force=False):
    """抓多日龙虎榜写盘。force=True 跳过 TTL（启动/cron/手动刷新用）。
    返回 True 表示本次成功拉到新数据并写盘；抓取失败时保留旧数据。"""
    ttl = _lhb_ttl()
    if not force and time_mod.time() - _cache["lhb_at"] < ttl and _cache["data"]:
        return False
    if not _lhb_lock.acquire(blocking=False):
        return False
    try:
        # 双检：等锁期间可能已被别的线程刷新过
        if not force and time_mod.time() - _cache["lhb_at"] < ttl and _cache["data"]:
            return False
        data, days = fetch_multi_day_lhb()
        if data:
            _cache["data"] = data
            _cache["trading_days"] = days
            _cache["lhb_at"] = time_mod.time()
            _cache["updated_at"] = _now_cn().strftime("%Y-%m-%d %H:%M:%S")
            _save_to_disk()
            return True
        # 抓取失败：保留旧数据，冷却 ttl/2 秒后再试
        log.warning("龙虎榜抓取返回空，保留旧数据并冷却重试")
        _mark_cooldown("lhb_at", ttl)
        return False
    except Exception:
        log.exception("龙虎榜抓取异常，保留旧数据并冷却重试")
        _mark_cooldown("lhb_at", ttl)
        return False
    finally:
        _lhb_lock.release()


def refresh_lhb_if_stale():
    """请求路径用：TTL 内直接返回；过期则后台线程刷新，不阻塞 /api/data
    （多日回溯抓取较重，放后台避免拖慢响应，下一次轮询即可拿到新数据）。"""
    if time_mod.time() - _cache["lhb_at"] < _lhb_ttl() and _cache["data"]:
        return
    threading.Thread(target=refresh_lhb, daemon=True).start()


def _is_trading_hours():
    now = _now_cn()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 0) <= t <= dtime(15, 30)


def refresh_jjyd_if_stale():
    ttl = 30 if _is_trading_hours() else 600
    if time_mod.time() - _cache["jjyd_at"] < ttl and _cache["jjyd"]:
        return
    if not _jjyd_lock.acquire(blocking=False):
        return
    try:
        if time_mod.time() - _cache["jjyd_at"] < ttl and _cache["jjyd"]:
            return
        jjyd = parse_jjyd(get_jjyd())
        if jjyd:
            _cache["jjyd"] = jjyd
            _cache["jjyd_at"] = time_mod.time()
            _cache["updated_at"] = _now_cn().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # 抓取失败：冷却 ttl/2 秒后再试，保留旧缓存
            log.warning("竞价净额抓取返回空，冷却重试")
            _mark_cooldown("jjyd_at", ttl)
    except Exception:
        log.exception("竞价净额抓取异常，冷却重试")
        _mark_cooldown("jjyd_at", ttl)
    finally:
        _jjyd_lock.release()


def refresh_capital_if_stale():
    ttl = 30 if _is_trading_hours() else 600
    if time_mod.time() - _cache["capital_at"] < ttl and _cache["top_volume"]:
        return
    if not _capital_lock.acquire(blocking=False):
        return
    try:
        if time_mod.time() - _cache["capital_at"] < ttl and _cache["top_volume"]:
            return
        top = parse_top_volume(get_top_volume(20))
        if top:
            _cache["top_volume"] = top
            _cache["capital_signals"] = compute_capital_signals(top)
            _cache["capital_at"] = time_mod.time()
            _cache["updated_at"] = _now_cn().strftime("%Y-%m-%d %H:%M:%S")
        else:
            log.warning("成交额榜抓取返回空，冷却重试")
            _mark_cooldown("capital_at", ttl)
    except Exception:
        log.exception("成交额榜抓取异常，冷却重试")
        _mark_cooldown("capital_at", ttl)
    finally:
        _capital_lock.release()


def refresh_kpl_if_stale(force=False):
    ttl = 600 if _is_trading_hours() else 3600
    if not force and time_mod.time() - _cache["kpl_at"] < ttl and _cache["kpl_interval"]:
        return
    if not _kpl_lock.acquire(blocking=False):
        return
    try:
        if not force and time_mod.time() - _cache["kpl_at"] < ttl and _cache["kpl_interval"]:
            return
        payload = fetch_interval_all()
        # payload 是 dict 恒为真，必须看榜单本身是否非空，空榜不许覆盖缓存/落盘
        if payload and (payload.get("stocks") or payload.get("sectors")):
            _cache["kpl_interval"] = payload
            _cache["kpl_at"] = time_mod.time()
            _cache["updated_at"] = _now_cn().strftime("%Y-%m-%d %H:%M:%S")
            _save_to_disk()
        else:
            log.warning("开盘啦区间榜抓取返回空，冷却重试")
            _mark_cooldown("kpl_at", ttl)
    except Exception:
        log.exception("开盘啦区间榜抓取异常，冷却重试")
        _mark_cooldown("kpl_at", ttl)
    finally:
        _kpl_lock.release()


if not _load_from_disk():
    # 兜底抓 30 天龙虎榜较重（30-60 秒），放后台线程避免 import 阶段阻塞启动；
    # 首次请求若数据未就绪，接口返回空结构即可，下一次轮询自然拿到。
    threading.Thread(target=refresh_lhb, kwargs={"force": True}, daemon=True).start()
threading.Thread(target=refresh_jjyd_if_stale, daemon=True).start()
threading.Thread(target=refresh_capital_if_stale, daemon=True).start()
threading.Thread(target=refresh_kpl_if_stale, daemon=True).start()

scheduler = BackgroundScheduler(timezone=CN_TZ)
scheduler.add_job(lambda: refresh_lhb(force=True), "cron",
                  day_of_week="mon-fri", hour=18, minute=30)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


def _validate_kpl_range(start, end):
    if not start or not end:
        return None, None, "缺少 start 或 end 参数"
    if not _DATE_RE.match(start) or not _DATE_RE.match(end):
        return None, None, "日期格式必须是 YYYY-MM-DD"
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return None, None, "日期不是有效日历日期"
    if start_dt > end_dt:
        return None, None, "start 不能晚于 end"
    if (end_dt - start_dt).days > 60:
        return None, None, "区间最长支持 60 天"
    return start, end, None


@app.route("/api/data")
def api_data():
    """前端 SPA 数据接口：触发 TTL 刷新后返回全部四块数据。"""
    refresh_lhb_if_stale()
    refresh_jjyd_if_stale()
    refresh_capital_if_stale()
    # 不许 force：缓存为空 + 上游持续返回空时，force 会绕过冷却，
    # 让每个 /api/data 请求都同步打满上游回退探测（前端是轮询的 = 自我放大）
    refresh_kpl_if_stale()
    return {
        "updated_at": _cache["updated_at"],
        "data": _cache["data"],
        "trading_days": _cache["trading_days"],
        "jjyd": _cache["jjyd"],
        "top_volume": _cache["top_volume"],
        "capital_signals": _cache["capital_signals"],
        "kpl_interval": _cache["kpl_interval"],
    }


@app.route("/api/kpl_interval")
def api_kpl_interval():
    """开盘啦区间榜：支持前端自选 start/end，不污染默认 /api/data 缓存。

    series=1 时附带逐日时间轴（每个交易日的吸金榜+板块强度榜，
    区间限 MAX_SERIES_DAYS 个自然日；历史日个股数值被接口脱敏，仅排名可信）。
    """
    start, end, err = _validate_kpl_range(
        request.args.get("start", ""),
        request.args.get("end", ""),
    )
    if err:
        return jsonify({"error": err}), 400
    want_series = request.args.get("series") == "1"
    if want_series:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
        if (end_dt - start_dt).days > MAX_SERIES_DAYS:
            return jsonify({"error": f"逐日模式区间最长 {MAX_SERIES_DAYS} 个自然日"}), 400
    # 短 TTL 查询缓存：一次区间查询最多触发几十次上游调用（回退探测/series 逐日），
    # 无缓存等于把上游请求放大器直接暴露在公网
    key = (start, end, want_series)
    ttl = 120 if _is_trading_hours() else 600
    now = time_mod.time()
    with _kpl_query_lock:
        hit = _kpl_query_cache.get(key)
        if hit and now - hit[0] < ttl:
            return jsonify(hit[1])
    try:
        payload = fetch_interval_all(start, end)
        if want_series:
            payload["series"] = fetch_interval_series(start, end)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"开盘啦区间榜抓取失败：{type(e).__name__}"}), 502
    with _kpl_query_lock:
        _kpl_query_cache[key] = (now, payload)
        while len(_kpl_query_cache) > 64:  # 防恶意区间枚举撑爆内存
            _kpl_query_cache.pop(next(iter(_kpl_query_cache)))
    return jsonify(payload)


@app.route("/api/reviews")
def api_reviews():
    """列出已发布的复盘报告，按日期倒序：[{date, types:[{type,label}]}]。"""
    by_date = {}
    if os.path.isdir(REVIEWS_DIR):
        for fn in os.listdir(REVIEWS_DIR):
            if not fn.endswith(".md"):
                continue
            stem = fn[:-3]
            date, sep, rtype = stem.partition("_")
            if not sep or not _DATE_RE.match(date) or rtype not in REVIEW_TYPES:
                continue
            by_date.setdefault(date, []).append(rtype)
    reviews = [
        {
            "date": d,
            "types": [
                {"type": t, "label": REVIEW_TYPES[t]}
                for t in REVIEW_TYPES  # 固定顺序：fupan 在前
                if t in by_date[d]
            ],
        }
        for d in sorted(by_date, reverse=True)
    ]
    return {"reviews": reviews}


@app.route("/api/review/<date>/<rtype>")
def api_review(date, rtype):
    """返回指定日期+类型的复盘 markdown 原文。"""
    if not _DATE_RE.match(date) or rtype not in REVIEW_TYPES:
        abort(404)
    path = os.path.join(REVIEWS_DIR, f"{date}_{rtype}.md")
    # 防目录穿越：解析后必须仍在 REVIEWS_DIR 下
    if os.path.realpath(os.path.dirname(path)) != os.path.realpath(REVIEWS_DIR):
        abort(404)
    if not os.path.exists(path):
        abort(404)
    with open(path, encoding="utf-8") as f:
        markdown = f.read()
    return {"date": date, "type": rtype, "label": REVIEW_TYPES[rtype], "markdown": markdown}


@app.route("/api/refresh/lhb", methods=["GET", "POST"])
def api_refresh_lhb():
    """手动/内部强制刷新多日龙虎榜（阻塞直到完成），并写回 data/data.json。
    返回更新结果，便于确认数据新鲜度。"""
    updated = refresh_lhb(force=True)
    days = _cache["trading_days"]
    return {
        "updated": updated,                 # 是否成功拉到新数据（失败/被占用为 False，旧数据保留）
        "updated_at": _cache["updated_at"],
        "latest_trading_day": days[0] if days else None,
        "count": len(_cache["data"]),
    }


@app.route("/healthz")
def healthz():
    return {
        "ok": True,
        "lhb": len(_cache["data"]),
        "jjyd": len(_cache["jjyd"]),
        "top_volume": len(_cache["top_volume"]),
        "kpl_interval": len((_cache.get("kpl_interval") or {}).get("stocks", [])),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
