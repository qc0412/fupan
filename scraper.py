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


# 东财 push2：沪深A股成交额排行 + 实时主力净额（f62，盘中即时，非按日结算）。
# 旧实现用新浪排行 + 逐只 MoneyFlow，但其 r0_net 按日结算：盘中拿到的是上一交易日
# 全天净额，错配到当日实时成交额上，会出现"主力净额 > 当日成交额"的假信号。
# 东财 clist 一次取数即得同一实时快照的 成交额(f6) 与 主力净额(f62)，两者自洽。
EM_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
# 主站不通时回退镜像（push2delay 为分钟级延迟，仍同日自洽，远胜旧的跨日错配）
EM_HOSTS = ["push2.eastmoney.com", "82.push2.eastmoney.com", "push2delay.eastmoney.com"]
# 沪深A股：深主板(t:6)+创业板(t:80)+沪主板(t:2)+科创板(t:23)
EM_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
# f12代码 f14名称 f2现价 f3涨幅 f6成交额(元) f8换手% f7振幅% f62主力净额(元) f100行业
EM_FIELDS = "f12,f14,f2,f3,f6,f8,f7,f62,f100"


def _num(v):
    """安全转 float，失败返回 None（东财用 '-' 表示无值）。"""
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def get_top_volume(n=20):
    """东财取沪深A股成交额前 N 的实时快照（含实时主力净额 f62）。"""
    params = {"pn": 1, "pz": n, "po": 1, "np": 1, "fltt": 2, "invt": 2,
              "fid": "f6", "fs": EM_FS, "fields": EM_FIELDS}
    for attempt in range(2):  # 每轮把所有 host 试一遍，再退避重试
        for host in EM_HOSTS:
            try:
                r = requests.get(f"https://{host}/api/qt/clist/get",
                                 params=params, headers=EM_HEADERS, timeout=8)
                r.raise_for_status()
                diff = (r.json().get("data") or {}).get("diff") or []
                if diff:
                    return diff
            except Exception:
                continue
        time.sleep(0.8 * (attempt + 1))
    return []


def parse_top_volume(raw):
    """东财字段映射、过滤 B 股/ST/退市/无成交。f62 为同一快照的实时主力净额(元)。"""
    result = []
    for it in raw:
        code = str(it.get("f12") or "")
        name = it.get("f14") or ""
        if not code or code.startswith(("900", "200")) or "ST" in name.upper() or "退" in name:
            continue
        amount = _num(it.get("f6")) or 0
        if not amount:
            continue  # 成交额为 0 直接丢弃（盘前/休市占位）
        result.append({
            "code": code,
            "name": name,
            "price": _num(it.get("f2")),
            "zf": _num(it.get("f3")),
            "turnover": amount,
            "amp": _num(it.get("f7")),
            "hsl": _num(it.get("f8")),
            "zhuli": _num(it.get("f62")) or 0.0,
            "industry": it.get("f100") or "",
        })
    return _cross_validate(result)


# 交叉验证：东财 f62 是单家黑箱口径，不盲信。用腾讯实时行情核对“客观事实”
# (现价/涨幅/成交额)，再对主力净额做物理护栏。任一不过 → 标记存疑、不喂假值。
TENCENT_Q_URL = "http://qt.gtimg.cn/q="


def _tencent_quotes(codes):
    """批量取腾讯实时行情。返回 {code: {price, pct, amount(元)}}。失败返回 {}。"""
    if not codes:
        return {}
    syms = ",".join((("sh" if c.startswith("6") else "sz") + c) for c in codes)
    try:
        r = requests.get(TENCENT_Q_URL + syms, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        r.encoding = "gbk"
    except Exception:
        return {}
    out = {}
    for line in r.text.strip().split("\n"):
        if '="' not in line:
            continue
        try:
            parts = line.split('"')[1].split("~")
            code = parts[2]
            ti = next((i for i, v in enumerate(parts) if len(v) == 14 and v.isdigit()), None)
            comb = next((v for v in parts if v.count("/") == 2), "")  # 现价/量/额
            out[code] = {
                "price": _num(parts[3]),
                "pct": _num(parts[ti + 2]) if ti else None,
                "amount": _num(comb.split("/")[2]) if comb else None,
            }
        except Exception:
            continue
    return out


def _cross_validate(rows):
    """逐行用腾讯行情交叉核对 + 主力净额物理护栏。给每行打 verified / zhuli 护栏。"""
    tq = _tencent_quotes([r["code"] for r in rows])
    for r in rows:
        t = tq.get(r["code"]) or {}
        flags = []
        # 1) 客观事实交叉核对（不同源快照有时差，给宽松容差）
        if t.get("price") and r.get("price"):
            if abs(r["price"] - t["price"]) / t["price"] > 0.02:
                flags.append(f"现价分歧 东财{r['price']}/腾讯{t['price']}")
        if t.get("amount") and r.get("turnover"):
            if abs(r["turnover"] - t["amount"]) / t["amount"] > 0.15:
                flags.append(f"成交额分歧 东财{r['turnover']/1e8:.1f}/腾讯{t['amount']/1e8:.1f}亿")
        if t.get("pct") is not None and r.get("zf") is not None:
            if abs(r["zf"] - t["pct"]) > 1.0:
                flags.append(f"涨幅分歧 东财{r['zf']}/腾讯{t['pct']}")
        # 2) 主力净额物理护栏：净额是买卖差，绝不可能超过当日成交额
        z, turn = r.get("zhuli"), r.get("turnover") or 0
        if z is not None and turn and abs(z) > turn:
            flags.append(f"净额>成交额 判废({z/1e8:.1f}>{turn/1e8:.1f}亿)")
            r["zhuli"] = None          # 物理不可能 → 置空，不计入聚合
        elif z is not None and turn and abs(z) > turn * 0.6:
            flags.append(f"净额占比偏高{abs(z)/turn*100:.0f}%")  # 软标记，保留
        r["verified"] = not flags
        r["flags"] = flags
    return rows


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

    # 主力净额只统计「通过交叉验证 且 通过物理护栏」的行；存疑/判废行不喂假值
    valid_z = [s for s in parsed if s.get("zhuli") is not None and s.get("verified")]
    sum_zhuli = sum((s.get("zhuli") or 0) for s in valid_z)
    z_turnover = sum((s.get("turnover") or 0) for s in valid_z) or 1
    verified_cnt = sum(1 for s in parsed if s.get("verified"))

    # 情绪温度 0-100：红绿比 + 平均涨幅 + 主力净额占比 三因子加权
    # 主力净额占比按“有效净额行”的成交额归一，避免被判废行稀释
    rg_score = max(-25, min(25, (up / max(down, 1) - 1) * 15))
    avg_score = max(-25, min(25, avg_zf * 5))
    zhuli_pct = sum_zhuli / z_turnover * 100
    zhuli_score = max(-25, min(25, zhuli_pct * 5))
    temp = round(50 + rg_score + avg_score + zhuli_score)
    temp = max(0, min(100, temp))

    signals = []
    # 数据质量：交叉验证未全过 → 显式提示存疑，不让脏数据冒充信号
    if verified_cnt < n:
        signals.append({"type": "warn", "label": "数据存疑",
                        "tip": f"{n}只中仅 {verified_cnt} 只通过东财×腾讯交叉验证"})
    # 泛绿出逃：下跌数显著多于上涨数
    if down > 0 and down >= up * 2 and n >= 15:
        signals.append({"type": "warn", "label": "泛绿出逃",
                        "tip": f"前{n}中 {down} 只下跌"})
    # 放量滞涨：平均涨幅平平 + 多空分歧不明显（没有压倒性方向）
    if -1 <= avg_zf <= 3 and n >= 15 and abs(up - down) <= n // 3:
        signals.append({"type": "warn", "label": "放量滞涨",
                        "tip": f"成交额前列但平均仅 {avg_zf:.2f}%，{up}红{down}绿无明显方向"})
    # 主力出货：净流出超(有效净额行)成交额 2%
    if sum_zhuli < 0 and abs(sum_zhuli) > z_turnover * 0.02:
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
        "verified_count": verified_cnt,
        "total_count": n,
        "zhuli_valid_count": len(valid_z),
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
