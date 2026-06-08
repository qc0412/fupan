import os
import re
import json
import threading
import time as time_mod
import atexit
from datetime import datetime, time as dtime, timezone, timedelta
from flask import Flask, abort
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import (
    fetch_multi_day_lhb,
    get_jjyd, parse_jjyd,
    get_top_volume, parse_top_volume, compute_capital_signals,
)

CN_TZ = timezone(timedelta(hours=8))


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
    "jjyd": [],
    "jjyd_at": 0.0,
    "top_volume": [],
    "capital_signals": {},
    "capital_at": 0.0,
}
_lhb_lock = threading.Lock()
_jjyd_lock = threading.Lock()
_capital_lock = threading.Lock()


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
        _cache["updated_at"] = d.get("updated_at", "")
        return bool(_cache["data"])
    except Exception:
        return False


def _save_to_disk():
    """把当前缓存写回 data/data.json，使服务器重启后能读到最新数据。"""
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
            }, f, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)
    except Exception:
        pass


def refresh_lhb():
    if not _lhb_lock.acquire(blocking=False):
        return
    try:
        data, days = fetch_multi_day_lhb()
        if data:
            _cache["data"] = data
            _cache["trading_days"] = days
            _cache["updated_at"] = _now_cn().strftime("%Y-%m-%d %H:%M:%S")
            _save_to_disk()
    finally:
        _lhb_lock.release()


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
            _cache["jjyd_at"] = time_mod.time() - ttl + ttl / 2
    except Exception:
        _cache["jjyd_at"] = time_mod.time() - ttl + ttl / 2
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
            # 抓取失败：冷却 ttl/2 秒后再试，避免每次请求都重复打远端
            _cache["capital_at"] = time_mod.time() - ttl + ttl / 2
    except Exception:
        _cache["capital_at"] = time_mod.time() - ttl + ttl / 2
    finally:
        _capital_lock.release()


if not _load_from_disk():
    refresh_lhb()
threading.Thread(target=refresh_jjyd_if_stale, daemon=True).start()
threading.Thread(target=refresh_capital_if_stale, daemon=True).start()

scheduler = BackgroundScheduler(timezone=CN_TZ)
scheduler.add_job(refresh_lhb, "cron", day_of_week="mon-fri", hour=18, minute=30)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


@app.route("/api/data")
def api_data():
    """前端 SPA 数据接口：触发 TTL 刷新后返回全部四块数据。"""
    refresh_jjyd_if_stale()
    refresh_capital_if_stale()
    return {
        "updated_at": _cache["updated_at"],
        "data": _cache["data"],
        "trading_days": _cache["trading_days"],
        "jjyd": _cache["jjyd"],
        "top_volume": _cache["top_volume"],
        "capital_signals": _cache["capital_signals"],
    }


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


@app.route("/healthz")
def healthz():
    return {
        "ok": True,
        "lhb": len(_cache["data"]),
        "jjyd": len(_cache["jjyd"]),
        "top_volume": len(_cache["top_volume"]),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
