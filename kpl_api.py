"""开盘啦「区间榜」接口封装（GetInterviewsByDate 家族）。

接口能力（2026-06-11 实测，全部用真实返回值对照开盘啦 APP 截图坐实）
====================================================================
POST https://apphwshhq.longhuvip.com/w1/api/index.php （无需 Token，当前唯一可裸连的开盘啦接口）

  a=GetInterviewsByDateStock c=StockLineData   区间个股榜
  a=GetInterviewsByDateZS    c=StockLineData   区间板块榜

通用参数：
  DStart/DEnd  交易日区间 YYYY-MM-DD（含两端；多日 = 累计口径：涨幅复利、
               净额/成交额/换手累加，已实测单日+单日≈两日；只支持日期，
               带时刻的 "YYYY-MM-DD HH:MM" 会返回空）
  Type         排行维度，见下方注册表
  Order        1=降序 0=升序（如 Type=2+Order=0 即区间跌幅榜）
  st           页大小（实测 50 可用），Index 偏移量，响应 Count 为总数（全市场约 5200）
  FilterBJS    1=过滤北交所

三条关键脾气（2026-06-11 实测）：
  1. DEnd 落在周末/节假日/今天未开盘 → 个股榜整个区间返回空 List，
     **不会**自动对齐到最近交易日。fetch_interval_all() 已做空榜回退。
     交易日的单日个股榜一定有榜（哪怕数值脱敏）→ 可拿它当交易日历用。
  2. 个股榜数值脱敏：区间不含「最新交易日 T」时，[3]~[8] 等数值字段整体归 0，
     只有排序（排名）仍按真实指标可信。
  3. 板块榜(ZS)数值不脱敏，但只覆盖最近两个交易日：DEnd 必须落在 T 或 T-1
     （实测 06-08~06-09 有值、06-01~06-05 整段空），更早的区间/单日一律空。

⚠️ 盘中时间轴的边界：APP「实时龙虎榜」里的 09:25~15:00 时间滑块走的是
   a=RealRankingInfo_W8 c=NewStockRanking（响应里的 Min/Max 字段就是滑块两端），
   该接口 2026-06-10 起需登录 Token/UserID，匿名返回空（见 kpl_sign.py）。
   本模块的 GetInterviewsByDate* 不认 RStart/REnd 等任何盘中时间参数（实测传了被忽略），
   时间轴只能做到「交易日」粒度——fetch_interval_series() 即按日拆解的时间轴。

Type 注册表（按返回排序键实测反推）：
  个股: 2=区间涨幅 3=主力买入额 5=主力净额 7=区间跌幅 8=成交额 9≈5(净额)
  板块: 1=区间涨幅 3=主力净额 9=区间强度

字段映射（以 2026-06-10 全天榜对照 APP 截图逐项核对：海光信息
涨幅 6.20% / 主力净额 17.45亿 / 成交额 188.8亿，三项全部对上）：
  个股 16 列:
    [0]代码 [1]名称 [2]最新价(区间末收盘价,多日区间不变) [3]区间涨幅%
    [4]主力买入额(元) [5]主力卖出额(元,负值) [6]主力净额(元, 恒等于[4]+[5])
    [7]区间换手% [8]区间成交额(元) [9]实际流通市值(元,开盘啦自有口径,
        茅台≈6900亿≠总市值1.6万亿,即剔除大股东锁仓后的可交易市值)
    [10]概念 [12]主力性质标签(''/'游资'/'基金')
    [11][13]=0/1标志位、[14]=可正可负的资金类数值、[15]恒为0 —— 含义未实证，不输出
  板块 12 列:
    [0]代码 [1]名称 [2]区间涨幅% [3]主力买入额 [4]主力卖出额(负值)
    [5]主力净额(恒等于[3]+[4]) [6]区间成交额 [7]市值(口径未严格核实,不输出)
    [11]区间强度
"""

import json
import time
from datetime import date, datetime, timedelta

import requests

URL = "https://apphwshhq.longhuvip.com/w1/api/index.php"
HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; V1916A Build/PQ3B.190801.002)",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept-Encoding": "gzip",
}
DEVICE_ID = "77cb70bc-fdb9-37a4-a993-4c5764859153"
VERSION = "5.22.0.6"
MAX_RETRY = 3

# 排行维度（Type 参数），键名供调用方使用
STOCK_TYPES = {"rise": 2, "buy": 3, "net": 5, "fall": 7, "amount": 8}
SECTOR_TYPES = {"rise": 1, "net": 3, "strength": 9}


def _num(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _call(a, c, type_, dstart, dend, order=1, st=30, index=0):
    data = {
        "Order": str(order),
        "st": str(st),
        "a": a,
        "c": c,
        "PhoneOSNew": "1",
        "DeviceID": DEVICE_ID,
        "VerSion": VERSION,
        "DEnd": dend,
        "Index": str(index),
        "DStart": dstart,
        "apiv": "w43",
        "Type": str(type_),
        "FilterBJS": "1",
    }
    last = None
    for attempt in range(MAX_RETRY):
        if attempt:
            time.sleep(0.8 * attempt)
        try:
            r = requests.post(URL, data=data, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json().get("List") or []
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(
        f"KaiPanLa request failed for a={a} type={type_}: {type(last).__name__}: {last}"
    )


def _is_junk(code, name):
    code, name = str(code), str(name or "")
    return (not code) or code.startswith(("9", "200")) or "ST" in name.upper() or "退" in name


def _parse_stock(row):
    return {
        "code": str(row[0]),
        "name": row[1],
        "price": _num(row[2]),               # 最新价（区间末收盘价）
        "zf_interval": _num(row[3]),         # 区间涨幅 %（多日为累计复利）
        "buy_interval": _num(row[4]),        # 区间主力买入额（元）
        "sell_interval": _num(row[5]),       # 区间主力卖出额（元，负值）
        "net_interval": _num(row[6]),        # 区间主力净额（元）= 买入 + 卖出
        "hsl_interval": _num(row[7]),        # 区间换手 %
        "amount_interval": _num(row[8]),     # 区间成交额（元）
        "float_mv": _num(row[9]),            # 实际流通市值（元，开盘啦口径）
        "concept": row[10] if len(row) > 10 else "",
        "main_tag": (row[12] or "") if len(row) > 12 else "",  # 主力性质：游资/基金
    }


def _parse_sector(row):
    return {
        "code": str(row[0]),
        "name": row[1],
        "zf_interval": _num(row[2]),         # 区间涨幅 %
        "buy_interval": _num(row[3]),        # 区间主力买入额（元）
        "sell_interval": _num(row[4]),       # 区间主力卖出额（元，负值）
        "net_interval": _num(row[5]),        # 区间主力净额（元）
        "amount_interval": _num(row[6]),     # 区间成交额（元）
        "strength": _num(row[11]) if len(row) > 11 else None,  # 区间强度
    }


def _dedup(rows):
    seen, out = set(), []
    for row in rows:
        if row["code"] in seen:
            continue
        seen.add(row["code"])
        out.append(row)
    return out


def fetch_interval_stock(dstart, dend, top_rise=9, top_net=9):
    """区间个股：涨幅榜前 top_rise + 主力净额榜前 top_net，去重合并。"""
    rise = [
        _parse_stock(r)
        for r in _call("GetInterviewsByDateStock", "StockLineData", STOCK_TYPES["rise"], dstart, dend)
        if isinstance(r, list) and len(r) >= 11 and not _is_junk(r[0], r[1])
    ]
    net = [
        _parse_stock(r)
        for r in _call("GetInterviewsByDateStock", "StockLineData", STOCK_TYPES["net"], dstart, dend)
        if isinstance(r, list) and len(r) >= 11 and not _is_junk(r[0], r[1])
    ]
    for i, row in enumerate(rise[:top_rise]):
        row["rank_rise"] = i + 1
    for i, row in enumerate(net[:top_net]):
        row["rank_net"] = i + 1
    return _dedup(rise[:top_rise] + net[:top_net])


def fetch_interval_sector(dstart, dend, top=6):
    """区间板块：强度榜 + 涨幅榜 + 净额榜各前 top，去重合并。"""
    def pull(type_, key):
        out = []
        for i, row in enumerate(_call("GetInterviewsByDateZS", "StockLineData", type_, dstart, dend)[:top]):
            if not (isinstance(row, list) and len(row) >= 12):
                continue
            item = _parse_sector(row)
            item[key] = i + 1
            out.append(item)
        return out

    merged = (
        pull(SECTOR_TYPES["strength"], "rank_strength")
        + pull(SECTOR_TYPES["rise"], "rank_rise")
        + pull(SECTOR_TYPES["net"], "rank_net")
    )
    return _dedup(merged)


def default_range(today=None):
    """默认近一周，DEnd=今天：盘中含当日实时累计；今天没数据（未开盘/
    周末节假日）时由 fetch_interval_all 的回退逻辑自动落到最近交易日。
    不能用「昨天」当终点——开盘后最新交易日变成今天，不含今天的区间
    个股数值会被服务端脱敏（脾气 #2）。"""
    end = today or date.today()
    return (end - timedelta(days=6)).isoformat(), end.isoformat()


def fetch_interval_all(dstart=None, dend=None):
    if not dstart or not dend:
        dstart, dend = default_range()
    stocks = fetch_interval_stock(dstart, dend)
    sectors = fetch_interval_sector(dstart, dend)
    # DEnd 落在非交易日（周末/节假日/今天未开盘）时接口整段返回空，
    # 不自动对齐——把 DEnd 往前回退（最多 7 天）找到最近有数据的交易日。
    d0 = datetime.strptime(dstart, "%Y-%m-%d").date()
    d1 = datetime.strptime(dend, "%Y-%m-%d").date()
    fallback = 0
    while not stocks and not sectors and fallback < 7:
        fallback += 1
        d1 -= timedelta(days=1)
        if d1 < d0:
            d0 = d1
        dstart, dend = d0.isoformat(), d1.isoformat()
        stocks = fetch_interval_stock(dstart, dend)
        sectors = fetch_interval_sector(dstart, dend)
    # 区间不含最新交易日时个股数值被服务端脱敏为 0（脾气 #2）：
    # 置 None 并打标，避免下游把 0 当真实数值用。
    masked = bool(stocks) and all(not s["net_interval"] for s in stocks)
    if masked:
        for s in stocks:
            for k in ("zf_interval", "buy_interval", "sell_interval",
                      "net_interval", "hsl_interval", "amount_interval"):
                s[k] = None
    return {
        "source": "开盘啦区间榜(GetInterviewsByDate)",
        "range": {"start": dstart, "end": dend},
        "stocks_masked": masked,
        "stocks": stocks,
        "sectors": sectors,
    }


MAX_SERIES_DAYS = 14


def fetch_interval_series(dstart, dend, top_stock=5, top_sector=5):
    """逐日时间轴：把区间按交易日拆开，每天各拉一次主力净额榜（个股）和强度榜（板块）。

    接口只支持日粒度（盘中分时轴属于被验签拦截的 RealRankingInfo_W8），
    这是当前能做到的最细时间轴。每天 2 次请求，区间限 MAX_SERIES_DAYS 个自然日。

    口径注意（见模块头「三条关键脾气」）：
      - 以个股榜是否有榜判定交易日（交易日必有榜，周末/节假日为空）；
      - 历史日的个股榜数值被服务端脱敏为 0 → 这里把 0 值置 None 并标
        stocks_masked=True，排名（榜单顺序）仍然可信；
        只有「最新交易日」那天 stocks_masked=False、数值齐全；
      - 板块榜只覆盖最近两个交易日，更早的日子 strength_sectors 为空列表。
    """
    d0 = datetime.strptime(dstart, "%Y-%m-%d").date()
    d1 = datetime.strptime(dend, "%Y-%m-%d").date()
    if d0 > d1:
        raise ValueError("dstart must not be later than dend")
    if (d1 - d0).days >= MAX_SERIES_DAYS:
        raise ValueError(f"series 区间最长支持 {MAX_SERIES_DAYS} 个自然日")
    value_keys = ("zf_interval", "buy_interval", "sell_interval", "net_interval",
                  "hsl_interval", "amount_interval")
    days = []
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:  # 周六日直接跳过，省请求
            day = cur.isoformat()
            stocks = [
                _parse_stock(r)
                for r in _call("GetInterviewsByDateStock", "StockLineData",
                               STOCK_TYPES["net"], day, day, st=top_stock + 6)
                if isinstance(r, list) and len(r) >= 11 and not _is_junk(r[0], r[1])
            ][:top_stock]
            if not stocks:  # 个股榜空 = 非交易日（节假日），剔除
                cur += timedelta(days=1)
                continue
            masked = all(not s["net_interval"] for s in stocks)
            if masked:
                for s in stocks:
                    for k in value_keys:
                        s[k] = None
            sectors = [
                _parse_sector(r)
                for r in _call("GetInterviewsByDateZS", "StockLineData",
                               SECTOR_TYPES["strength"], day, day, st=top_sector)
                if isinstance(r, list) and len(r) >= 12
            ][:top_sector]
            days.append({
                "date": day,
                "stocks_masked": masked,
                "net_stocks": stocks,
                "strength_sectors": sectors,  # 仅最近两个交易日有值（脾气 #3）
            })
        cur += timedelta(days=1)
    return {
        "source": "开盘啦区间榜·逐日(GetInterviewsByDate)",
        "range": {"start": dstart, "end": dend},
        "note": "stocks_masked=true 的历史日个股仅排名可信(数值被接口脱敏)；板块榜只覆盖最近两个交易日",
        "days": days,
    }


def dump_interval_all(dstart=None, dend=None):
    return json.dumps(fetch_interval_all(dstart, dend), ensure_ascii=False, indent=2)
