import requests
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor
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


# 东财龙虎榜：datacenter-web 子域，数据中心 IP 可直连（替代被封的 duanxianxia）。
LHB_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
LHB_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}


def get_lhb(date_str):
    """东财龙虎榜每日明细。date_str 形如 2026-06-05。
    返回 [{"info": {"code","name","zf"}}, ...]，与 fetch_multi_day_lhb 聚合逻辑兼容。
    非交易日 / 无数据返回空列表（上游据此跳过该日）。"""
    try:
        r = requests.get(
            LHB_URL,
            params={
                "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
                "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,CHANGE_RATE",
                "pageNumber": 1, "pageSize": 500,
                "sortColumns": "SECURITY_CODE", "sortTypes": 1,
                "filter": f"(TRADE_DATE='{date_str}')",
            },
            headers=LHB_HEADERS, timeout=10,
        )
        r.raise_for_status()
        rows = ((r.json() or {}).get("result") or {}).get("data") or []
        out = []
        for it in rows:
            code = str(it.get("SECURITY_CODE") or "")
            if not code:
                continue
            out.append({"info": {
                "code": code,
                "name": it.get("SECURITY_NAME_ABBR") or "",
                "zf": _num(it.get("CHANGE_RATE")),
            }})
        return out
    except Exception:
        return []


# 竞价净额：duanxianxia 集合竞价主力净额（9:25 第一时间结算）。
# www.duanxianxia.com 子域（45.125.47.48）数据中心 IP 可直连——裸域/.cn 走被封 CDN(43.141.11.140)。
# 文件 AES-256-CBC 加密，密钥/IV 取自站点 crypto.js decryptData()。
JJ_URL = "https://www.duanxianxia.com/vendor/stockdata/jjzhuli.json"
JJ_KEY = bytes.fromhex("7365637265746b65793332327965732121616161616161616161616161616161")
JJ_IV = bytes.fromhex("666978656469765f313676616c756564")


def get_jjyd():
    """取 duanxianxia 竞价净额（9 字段数组列表）：
    [代码, 名称, 竞价涨幅%, 现价涨幅%, 竞价主力净额(万), 竞额(万), 流通市值(亿), 概念, 竞价换手%]。"""
    try:
        import base64
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        r = requests.get(JJ_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        ct = base64.b64decode(r.text.strip())
        pt = unpad(AES.new(JJ_KEY, AES.MODE_CBC, JJ_IV).decrypt(ct), 16)
        return json.loads(pt.decode("utf-8")).get("list") or []
    except Exception:
        return []


# 新浪财经：沪深A股成交额排行 + 个股主力净流入。数据中心 IP 可直连，比东财稳定。
SINA_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
SINA_RANK_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
SINA_FLOW_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs"


def _num(v):
    """安全转 float，失败返回 None。"""
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


# 东财涨停池：push2ex 子域，数据中心 IP 可直连（与被封的 push2 实时行情子域不同）。
ZTPOOL_URL = "https://push2ex.eastmoney.com/getTopicZTPool"
ZTPOOL_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}


def get_zt_pool(date_str=None):
    """取东财涨停池。date_str=None 时从今天往前找最近一个有涨停数据的交易日。
    返回 (pool 原始列表, qdate 字符串)。"""
    if date_str:
        candidates = [date_str]
    else:
        candidates = [(date.today() - timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]
    for d in candidates:
        try:
            r = requests.get(
                ZTPOOL_URL,
                params={"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztzt",
                        "Pageindex": 0, "pagesize": 300, "sort": "zttj:desc", "date": d},
                headers=ZTPOOL_HEADERS, timeout=8,
            )
            r.raise_for_status()
            data = (r.json() or {}).get("data") or {}
            pool = data.get("pool") or []
            if pool:
                return pool, str(data.get("qdate") or d)
        except Exception:
            continue
    return [], ""


def parse_zt_pool(raw):
    """涨停池字段映射：含连板高度(zttj)、封单、炸板次数、题材。剔除 ST/退市。
    按连板高度降序、其次成交额。"""
    result = []
    for it in raw:
        code = str(it.get("c") or "")
        name = it.get("n") or ""
        if not code or "ST" in name.upper() or "退" in name:
            continue
        z = it.get("zttj") or {}
        result.append({
            "code": code,
            "name": name,
            "zf": round(it.get("zdp") or 0, 2),     # 涨幅 %
            "days": z.get("days"),                   # 几天
            "boards": z.get("ct"),                   # 几板（连板高度）
            "hsl": round(it.get("hs") or 0, 2),      # 换手 %
            "turnover": it.get("amount") or 0,       # 成交额 (元)
            "fund": it.get("fund") or 0,             # 封单额 (元)
            "zbc": it.get("zbc") or 0,               # 炸板次数
            "hybk": it.get("hybk") or "",            # 题材/行业板块
            "ltsz": it.get("ltsz") or 0,             # 流通市值 (元)
        })
    result.sort(key=lambda x: (-(x["boards"] or 0), -(x["turnover"] or 0)))
    return result


def get_top_volume(n=20):
    """新浪取沪深A股成交额前 N 的个股快照。"""
    try:
        r = requests.get(
            SINA_RANK_URL,
            params={"page": 1, "num": n, "sort": "amount", "asc": 0, "node": "hs_a"},
            headers=SINA_HEADERS, timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _sina_zhuli(symbol):
    """取单只最新主力净流入(r0_net, 元)。symbol 形如 sz300308。"""
    try:
        r = requests.get(SINA_FLOW_URL, params={"daima": symbol}, headers=SINA_HEADERS, timeout=6)
        arr = r.json()
        if isinstance(arr, list) and arr:
            return float(arr[0].get("r0_net") or 0)
    except Exception:
        pass
    return 0.0


def parse_top_volume(raw):
    """重命名字段、过滤 B 股/ST/退市/无成交，并并发补主力净额。"""
    result = []
    for it in raw:
        code = str(it.get("code") or "")
        name = it.get("name") or ""
        symbol = it.get("symbol") or ""
        if not code or code.startswith(("900", "200")) or "ST" in name.upper() or "退" in name:
            continue
        amount = _num(it.get("amount")) or 0
        if not amount:
            continue  # 成交额为 0 直接丢弃（盘前/休市占位）
        settle, high, low = _num(it.get("settlement")), _num(it.get("high")), _num(it.get("low"))
        amp = round((high - low) / settle * 100, 2) if settle and high is not None and low is not None else None
        result.append({
            "code": code,
            "symbol": symbol,
            "name": name,
            "price": _num(it.get("trade")),
            "zf": _num(it.get("changepercent")),
            "turnover": amount,
            "amp": amp,
            "hsl": _num(it.get("turnoverratio")),
            "zhuli": 0.0,        # 下面并发补
            "industry": "",      # 新浪成交额榜不含行业
        })

    # 并发拉取每只的主力净流入，避免逐只串行拖慢刷新
    if result:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for row, zhuli in zip(result, ex.map(lambda r: _sina_zhuli(r["symbol"]), result)):
                row["zhuli"] = zhuli
    for row in result:
        row.pop("symbol", None)
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
    """竞价净额字段映射。来源 duanxianxia jjzhuli（解密后），每行 9 字段：
    [代码, 名称, 竞价涨幅%, 现价涨幅%, 竞价主力净额(万), 竞额(万), 流通市值(亿), 概念, 竞价换手%]
    """
    result = []
    for it in raw_list:
        if not it or len(it) < 9:
            continue
        code = str(it[0] or "")
        name = it[1]
        if not code or code.startswith("9") or "ST" in str(name).upper() or "退" in str(name):
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
    zt_raw, zt_date = get_zt_pool()
    zt_pool = parse_zt_pool(zt_raw) or prev.get("zt_pool", [])
    zt_date = zt_date or prev.get("zt_date", "")

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": now_cn_str(),
            "trading_days": trading_days,
            "data": result,
            "jjyd": jjyd,
            "top_volume": top_volume,
            "capital_signals": capital_signals,
            "zt_pool": zt_pool,
            "zt_date": zt_date,
        }, f, ensure_ascii=False, indent=2)
    print(f"saved: lhb={len(result)} jjyd={len(jjyd)} top_volume={len(top_volume)} zt={len(zt_pool)}")
