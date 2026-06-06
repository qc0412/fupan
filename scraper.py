import requests
import time
import os
import json
from datetime import date, datetime, timedelta, timezone

CN_TZ = timezone(timedelta(hours=8))


def now_cn_str():
    return datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")

BASE_URL = "https://duanxianxia.cn"
def _load_credentials():
    username = os.environ.get("DXX_USERNAME")
    password = os.environ.get("DXX_PASSWORD")
    if username and password:
        return username, password
    cred_file = os.path.expanduser("~/.claude/duanxianxia_credentials.json")
    with open(cred_file) as f:
        c = json.load(f)
    return c["username"], c["password"]

COOKIE_FILE = os.path.join(os.path.dirname(__file__), ".cookie_cache")

_session = None


def _login():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/web/login",
    })
    username, password = _load_credentials()
    r = s.post(BASE_URL + "/api/userLogin", data={"username": username, "password": password}, timeout=10)
    r.raise_for_status()
    if r.json().get("result") != "success":
        raise RuntimeError("登录失败")
    cookie_str = "; ".join(f"{c.name}={c.value}" for c in s.cookies)
    try:
        with open(COOKIE_FILE, "w") as f:
            f.write(cookie_str)
    except OSError:
        pass
    s.headers["Cookie"] = cookie_str
    return s


def _get_session():
    global _session
    if _session is not None:
        return _session
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/web/longhu/4ac6af32a6ffc014",
    })
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE) as f:
            s.headers["Cookie"] = f.read().strip()
    _session = s
    return _session


def get_lhb(date_str):
    global _session
    for attempt in range(2):
        try:
            r = _get_session().post(
                BASE_URL + "/api/getLhbByStock",
                data={"date": date_str},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data:
                return data
            # null 或空列表说明 cookie 失效，重新登录
            if attempt == 0:
                _session = _login()
        except Exception:
            if attempt == 0:
                try:
                    _session = _login()
                except Exception:
                    pass
    return []


def get_jjyd():
    """抓取竞价净额数据（/mob/jjyd 页面"竞价净额"tab，背后接口 /data/getJjzhuliData/4，按竞价主力净额降序）。"""
    global _session
    for attempt in range(2):
        try:
            s = _get_session()
            r = s.post(
                BASE_URL + "/data/getJjzhuliData/4",
                headers={"Referer": BASE_URL + "/mob/jjyd/4ac6af32a6ffc014"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and data.get("list"):
                return data["list"]
            if attempt == 0:
                _session = _login()
        except Exception:
            if attempt == 0:
                try:
                    _session = _login()
                except Exception:
                    pass
    return []


# 东财 push2 是 0~99 编号的负载均衡子域，HTTPS 在部分网络下不稳，用 HTTP 直连更可靠
EASTMONEY_HOSTS = [
    "http://push2his.eastmoney.com",   # 主路径
    "http://82.push2.eastmoney.com",   # 子域 fallback
    "http://0.push2.eastmoney.com",
    "https://82.push2.eastmoney.com",  # HTTPS 兜底
]
# 全 A 股市场（沪深主板+创业板+科创板+北交所）
EASTMONEY_FS = "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"


def get_top_volume(n=20):
    """从东方财富取成交额前 N 的个股快照。失败时自动切换 push2 子域重试。"""
    fields = "f2,f3,f6,f7,f8,f12,f14,f62,f100"
    # f2 最新价 / f3 涨跌幅% / f6 成交额(元) / f7 振幅% / f8 换手率%
    # f12 代码 / f14 名称 / f62 主力净流入(元) / f100 行业
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
    for base in EASTMONEY_HOSTS:
        url = (f"{base}/api/qt/clist/get"
               f"?pn=1&pz={n}&po=1&fid=f6"
               f"&fs={EASTMONEY_FS}&fields={fields}")
        try:
            r = requests.get(url, headers=headers, timeout=6)
            r.raise_for_status()
            j = r.json()
            diff = (j.get("data") or {}).get("diff") or {}
            if not diff:
                continue
            if isinstance(diff, list):
                return diff
            return [diff[k] for k in sorted(diff.keys(), key=int)]
        except Exception:
            continue
    return []


def _scale(v, factor=100):
    """东财 f2/f3/f7/f8 是 ×100 的整数，统一除回去。"""
    if v is None or v == "-":
        return None
    try:
        return round(float(v) / factor, 2)
    except (TypeError, ValueError):
        return None


def parse_top_volume(raw):
    """重命名字段、过滤 B 股/ST/无成交（避免盘前/收盘前的占位数据污染列表）。"""
    result = []
    for it in raw:
        code = str(it.get("f12") or "")
        name = it.get("f14") or ""
        if not code or code.startswith("900") or code.startswith("200") or "ST" in name.upper():
            continue
        if not (it.get("f6") or 0):
            continue  # 成交额为 0 直接丢弃
        result.append({
            "code": code,
            "name": name,
            "price": _scale(it.get("f2")),
            "zf": _scale(it.get("f3")),
            "turnover": it.get("f6"),
            "amp": _scale(it.get("f7")),
            "hsl": _scale(it.get("f8")),
            "zhuli": it.get("f62"),
            "industry": it.get("f100"),
        })
    return result


def compute_capital_signals(parsed):
    """从前 N 大成交额股票推导出大资金情绪指标。"""
    n = len(parsed)
    sum_turnover = sum((s.get("turnover") or 0) for s in parsed)
    # 盘前/收盘前数据全 0：返回占位状态，不产生假信号
    if n == 0 or sum_turnover == 0:
        return {
            "up_count": 0, "down_count": 0, "flat_count": 0,
            "avg_zf": 0, "sum_zhuli": 0, "sum_turnover": 0,
            "temp": None, "signals": [{"type": "neutral", "label": "暂无成交数据"}],
        }

    up = sum(1 for s in parsed if (s.get("zf") or 0) > 0)
    down = sum(1 for s in parsed if (s.get("zf") or 0) < 0)
    flat = n - up - down
    avg_zf = sum((s.get("zf") or 0) for s in parsed) / n
    sum_zhuli = sum((s.get("zhuli") or 0) for s in parsed)

    # 情绪温度 0-100：红绿比 + 平均涨幅 + 主力净额占比 三因子加权
    rg_score = max(-25, min(25, (up / max(down, 1) - 1) * 15))
    avg_score = max(-25, min(25, avg_zf * 5))
    zhuli_pct = sum_zhuli / sum_turnover * 100
    zhuli_score = max(-25, min(25, zhuli_pct * 5))
    temp = round(50 + rg_score + avg_score + zhuli_score)
    temp = max(0, min(100, temp))

    signals = []
    # 泛绿出逃：下跌数显著多于上涨数
    if down > 0 and down >= up * 2 and n >= 15:
        signals.append({"type": "warn", "label": "泛绿出逃",
                        "tip": f"前{n}中 {down} 只下跌"})
    # 放量滞涨：平均涨幅平平 + 多空分歧不明显（没有压倒性方向）
    if -1 <= avg_zf <= 3 and n >= 15 and abs(up - down) <= n // 3:
        signals.append({"type": "warn", "label": "放量滞涨",
                        "tip": f"成交额前列但平均仅 {avg_zf:.2f}%，{up}红{down}绿无明显方向"})
    # 主力出货：净流出超成交额 2%
    if sum_zhuli < 0 and abs(sum_zhuli) > sum_turnover * 0.02:
        signals.append({"type": "warn", "label": "主力出货",
                        "tip": f"合计净流出 {abs(sum_zhuli)/1e8:.2f} 亿"})
    # 普涨进攻：多数上涨且涨幅明显
    if up >= n * 0.7 and avg_zf >= 3 and n >= 15:
        signals.append({"type": "ok", "label": "普涨进攻",
                        "tip": f"{up}/{n} 上涨，平均 +{avg_zf:.2f}%"})
    if not signals:
        if temp >= 65:
            signals.append({"type": "ok", "label": "情绪偏强"})
        elif temp <= 35:
            signals.append({"type": "warn", "label": "情绪偏弱"})
        else:
            signals.append({"type": "neutral", "label": "情绪中性"})

    return {
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "avg_zf": round(avg_zf, 2),
        "sum_zhuli": sum_zhuli,
        "sum_turnover": sum_turnover,
        "temp": temp,
        "signals": signals,
    }


def parse_jjyd(raw_list):
    """竞价净额字段映射。来源 /data/getJjzhuliData/4（jjyd.dxx.js getZhuli()），每行：
    [代码, 名称, 竞价涨幅%, 现价涨幅%, 竞价主力净额(万), 竞额(万), 流通市值(亿), 概念, 竞价换手%]
    """
    result = []
    for it in raw_list:
        if not it or len(it) < 9:
            continue
        code = str(it[0] or "")
        name = it[1]
        if not code or code.startswith("9") or "ST" in str(name).upper():
            continue
        result.append({
            "code": code,
            "name": name,
            "jjzf": it[2],          # 竞价涨幅 %
            "zf": it[3],            # 现价涨幅 %
            "zhuli": it[4],         # 竞价主力净额 (万元) —— 即"竞价净额"
            "jje": it[5],           # 竞额 (万元)
            "ltsz": it[6],          # 流通市值 (亿元)
            "concept": it[7],       # 概念
            "jjhs": it[8],          # 竞价换手 %
        })
    return result


def fetch_multi_day_lhb():
    trading_days = []
    day_data = {}
    d = date.today()
    while len(trading_days) < 30 and (date.today() - d).days < 60:
        if d.weekday() < 5:
            date_str = d.strftime("%Y-%m-%d")
            data = get_lhb(date_str)
            time.sleep(0.5)
            if data:
                trading_days.append(date_str)
                day_data[date_str] = data
        d -= timedelta(days=1)

    stock_map = {}
    for date_str in trading_days:
        data = day_data[date_str]
        seen = set()
        for item in data:
            code = item["info"]["code"]
            if code in seen:
                continue
            seen.add(code)
            name = item["info"]["name"]
            if code.startswith("9") or "ST" in name.upper() or "退" in name:
                continue
            if code not in stock_map:
                stock_map[code] = {"name": name, "code": code, "appearances": []}
            stock_map[code]["appearances"].append({"date": date_str, "zf": item["info"]["zf"]})

    result = list(stock_map.values())
    result.sort(key=lambda x: -len(x["appearances"]))
    return result, trading_days


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    data_path = "data/data.json"

    # 读取现有数据用于失败时回退（避免临时抓取失败把旧数据清空）
    prev = {}
    if os.path.exists(data_path):
        try:
            with open(data_path, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = {}

    result, trading_days = fetch_multi_day_lhb()
    if not result:
        result = prev.get("data", [])
        trading_days = prev.get("trading_days", [])

    jjyd = parse_jjyd(get_jjyd()) or prev.get("jjyd", [])
    top_volume = parse_top_volume(get_top_volume(20)) or prev.get("top_volume", [])
    capital_signals = compute_capital_signals(top_volume) if top_volume else prev.get("capital_signals", {})

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": now_cn_str(),
            "trading_days": trading_days,
            "data": result,
            "jjyd": jjyd,
            "top_volume": top_volume,
            "capital_signals": capital_signals,
        }, f, ensure_ascii=False, indent=2)
    print(f"saved: lhb={len(result)} jjyd={len(jjyd)} top_volume={len(top_volume)}")
