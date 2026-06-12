#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开盘啦「区间榜」数据 —— /fupan 第零步数据源之一
来源: 开盘啦(龙虎榜版) https://apphwshhq.longhuvip.com/w1/api/index.php

作用
----
拉取开盘啦自有口径的【区间个股榜】和【区间板块榜】，给定一个交易日区间
(DStart~DEnd)，返回：
  - 区间个股: 区间涨幅龙头 + 区间净额吸金王（两榜去重合并）
  - 区间板块: 区间强度榜 + 涨幅榜 + 净额榜（三榜去重合并）
直接服务【第四步:板块生命周期】(谁在加速/吸金) 与【周龙头评选】(区间涨幅/净额龙头)。
与 platerotat.py 互补: platerotat 给"短线侠板块排名矩阵走势", 本模块给
"开盘啦口径的区间真实净额(元) + 区间强度 + 个股区间龙头", 是 platerotat 拿不到的维度。

接口(POST, 无 token/cookie, 但有两条关键经验)
  a=GetInterviewsByDateStock c=StockLineData  Type=2 区间涨幅榜 / Type=5 区间净额榜
  a=GetInterviewsByDateZS    c=StockLineData  Type=9 区间强度榜 / Type=1 涨幅榜 / Type=3 净额榜

⚠️ 重要区别(2026-06-10 实测)
  - 同源的实时打板榜 a=RealRankingInfo_W8 已被服务端验签拦截(Count:0, 需 libsockSign.so
    签名, 见 ~/fupan/kpl_sign.py, arg1/2/3 尚未逆出)。涨停板请继续用 AkShare zt_pool。
  - 本模块这两个"区间榜"接口【无需签名仍可用】, 是当前开盘啦唯一还能裸连的有效数据。
    若哪天这两个也返回 Count:0/List 空 → 同样被验签, 需补签名后才能用。

字段映射(2026-06-11 用 APP「实时龙虎榜」截图逐项核对坐实: 海光信息 2026-06-10
涨幅 6.20%/主力净额 17.45亿/成交额 188.8亿 三项全对上; [4]+[5] 恒等于 [6]):
  个股 List[i] 16列: [0]代码 [1]名称 [2]最新价(区间末收盘价) [3]区间涨幅%
                      [4]主力买入额(元) [5]主力卖出额(元,负值) [6]主力净额(元)
                      [7]区间换手% [8]区间成交额(元) [9]实际流通市值(元,开盘啦口径)
                      [10]概念 [12]主力性质(''/'游资'/'基金')
                      ⚠️ 旧版曾把 [4] 当成交额、漏掉 [8], 已纠正
  板块 List[i] 12列: [0]代码 [1]名称 [2]区间涨幅% [3]主力买入额 [4]主力卖出额(负值)
                      [5]区间净额(元) [6]区间成交额(元) [11]区间强度

⚠️ 三条接口脾气(2026-06-11 实测, 详见 ~/fupan/kpl_api.py 模块头):
  1. DEnd 落在周末/节假日/今天未开盘 → 整段返回空, 不自动对齐到最近交易日;
  2. 区间不含「最新交易日」时个股榜数值整体脱敏为 0(排名仍可信), 本脚本会把
     0 值置 None 并在输出标 stocks_masked;
  3. 板块榜数值不脱敏, 但只覆盖最近两个交易日(DEnd 须为 T 或 T-1), 更早区间为空。

用法
  python3 kpl_interval.py                          # 默认近一周, 人读摘要
  python3 kpl_interval.py --start 2026-06-05 --end 2026-06-09
  python3 kpl_interval.py --json                   # JSON 到 stdout (供 /fupan 读取)
"""

import argparse
import json
import sys
import time
from datetime import date, timedelta

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

BLOCKED_HINT = (
    "⚠️ 开盘啦区间榜返回空(List 为空)——此接口可能也已被验签拦截。"
    "请改用 AkShare/短线侠 platerotat.py 兜底, 并核对是否需补 kpl_sign 签名。"
)


def _num(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _call(a, c, type_, dstart, dend):
    """单次开盘啦区间榜请求, 返回 List(二维数组)。失败/空返回 []。"""
    data = {
        "Order": "1", "st": "30", "a": a, "c": c,
        "PhoneOSNew": "1", "DeviceID": DEVICE_ID, "VerSion": VERSION,
        "DEnd": dend, "Index": "0", "DStart": dstart,
        "apiv": "w43", "Type": str(type_), "FilterBJS": "1",
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
    print(f"[kpl_interval] {a} Type={type_} 请求失败: "
          f"{type(last).__name__}: {last}", file=sys.stderr)
    return []


def _is_junk(code, name):
    code, name = str(code), str(name or "")
    return (not code) or code.startswith(("9", "200")) or \
        "ST" in name.upper() or "退" in name


def _parse_stock(row):
    return {
        "code": str(row[0]),
        "name": row[1],
        "price": _num(row[2]),             # 最新价(区间末收盘价)
        "zf_interval": _num(row[3]),       # 区间涨幅 %
        "buy_interval": _num(row[4]),      # 主力买入额 (元)
        "sell_interval": _num(row[5]),     # 主力卖出额 (元, 负值)
        "net_interval": _num(row[6]),      # 主力净额 (元) = [4]+[5]
        "hsl_interval": _num(row[7]),      # 区间换手 %
        "amount_interval": _num(row[8]),   # 区间成交额 (元) ←旧版误用[4](主力买入额)
        "float_mv": _num(row[9]),          # 实际流通市值 (元, 开盘啦口径)
        "concept": row[10] if len(row) > 10 else "",
        "main_tag": (row[12] or "") if len(row) > 12 else "",  # 主力性质: 游资/基金
    }


def _parse_sector(row):
    return {
        "code": str(row[0]),
        "name": row[1],
        "zf_interval": _num(row[2]),       # 区间涨幅 %
        "buy_interval": _num(row[3]),      # 主力买入额 (元)
        "sell_interval": _num(row[4]),     # 主力卖出额 (元, 负值)
        "net_interval": _num(row[5]),      # 区间净额 (元)
        "amount_interval": _num(row[6]),   # 区间成交额 (元)
        "strength": _num(row[11]) if len(row) > 11 else None,  # 区间强度
    }


def _dedup(rows):
    """按 code 保序去重(先到先得, 保留更靠前榜单的排名语义)。"""
    seen, out = set(), []
    for r in rows:
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        out.append(r)
    return out


def fetch_interval_stock(dstart, dend, top_rise=9, top_net=9):
    """区间个股: 涨幅榜前 top_rise + 净额榜前 top_net, 去重合并。
    返回 list[dict]; 每条标 from_rise / from_net 标记来自哪个榜(便于排序展示)。"""
    rise = [_parse_stock(r) for r in _call(
        "GetInterviewsByDateStock", "StockLineData", 2, dstart, dend)
        if isinstance(r, list) and len(r) >= 11 and not _is_junk(r[0], r[1])]
    net = [_parse_stock(r) for r in _call(
        "GetInterviewsByDateStock", "StockLineData", 5, dstart, dend)
        if isinstance(r, list) and len(r) >= 11 and not _is_junk(r[0], r[1])]
    for i, r in enumerate(rise[:top_rise]):
        r["rank_rise"] = i + 1
    for i, r in enumerate(net[:top_net]):
        r["rank_net"] = i + 1
    return _dedup(rise[:top_rise] + net[:top_net])


def fetch_interval_sector(dstart, dend, top=6):
    """区间板块: 强度榜 + 涨幅榜 + 净额榜 各前 top, 去重合并。"""
    def pull(type_, key):
        out = []
        for i, r in enumerate(_call("GetInterviewsByDateZS", "StockLineData",
                                    type_, dstart, dend)[:top]):
            if not (isinstance(r, list) and len(r) >= 12):
                continue
            d = _parse_sector(r)
            d[key] = i + 1
            out.append(d)
        return out
    merged = pull(9, "rank_strength") + pull(1, "rank_rise") + pull(3, "rank_net")
    return _dedup(merged)


def _snap_back_weekday(d):
    """d 若落在周末则回退到最近的周五（区间端点必须是交易日，否则接口整段返回空）。"""
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _prev_weekday(d):
    d -= timedelta(days=1)
    return _snap_back_weekday(d)


def _next_weekday(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def default_range(today=None, days=5):
    """默认区间: 近 days 个工作日（end=最近工作日, start=往前数第 days 个工作日）。
    ⚠️ 脾气#4(2026-06-12 实测): 不只 DEnd——【DStart 落在周末/节假日同样整段返回空】，
    所以两端都按工作日取；节假日(工作日休市)由 fetch_all() 的回退逻辑兜底。"""
    end = _snap_back_weekday(today or date.today())
    start = end
    for _ in range(max(days, 1) - 1):
        start = _prev_weekday(start)
    return start.isoformat(), end.isoformat()


def fetch_all(dstart=None, dend=None, days=5):
    if not dstart or not dend:
        dstart, dend = default_range(days=days)
    from datetime import datetime as _dt
    # 两端先对齐到工作日（脾气#4：任一端落在周末 → 整段空）
    d0 = _snap_back_weekday(_dt.strptime(dstart, "%Y-%m-%d").date())
    d1 = _snap_back_weekday(_dt.strptime(dend, "%Y-%m-%d").date())
    if d0 > d1:
        d0 = d1
    dstart, dend = d0.isoformat(), d1.isoformat()
    stocks = fetch_interval_stock(dstart, dend)
    sectors = fetch_interval_sector(dstart, dend)
    # 脾气#1: DEnd 节假日/今天未开盘 → 整段空, DEnd 往前回退找最近交易日
    fallback = 0
    while not stocks and not sectors and fallback < 5:
        fallback += 1
        d1 = _prev_weekday(d1)
        if d1 < d0:
            d0 = d1
        dstart, dend = d0.isoformat(), d1.isoformat()
        stocks = fetch_interval_stock(dstart, dend)
        sectors = fetch_interval_sector(dstart, dend)
    # 脾气#4 补充: DStart 节假日(工作日休市)也整段空 → DStart 往后挪找交易日
    fallback = 0
    while not stocks and not sectors and fallback < 5 and d0 < d1:
        fallback += 1
        d0 = _next_weekday(d0)
        if d0 > d1:
            d0 = d1
        dstart, dend = d0.isoformat(), d1.isoformat()
        stocks = fetch_interval_stock(dstart, dend)
        sectors = fetch_interval_sector(dstart, dend)
    # 脾气#2: 区间不含最新交易日 → 个股数值脱敏为 0, 置 None 防止当真数据用
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


def _fmt_money(yuan):
    if yuan is None:
        return "-"
    a = abs(yuan)
    if a >= 1e8:
        return f"{yuan / 1e8:.2f}亿"
    if a >= 1e4:
        return f"{yuan / 1e4:.2f}万"
    return f"{yuan:.0f}"


def _print_human(d):
    r = d["range"]
    print(f"=== 开盘啦区间榜 {r['start']} ~ {r['end']} ===\n")
    if d.get("stocks_masked"):
        print("⚠️ 区间不含最新交易日, 个股榜数值被接口脱敏(置 None), 仅排名可信\n")
    print(f"【区间板块榜】(强度/涨幅/净额去重, 共 {len(d['sectors'])} 个)")
    for s in sorted(d["sectors"], key=lambda x: -(x.get("strength") or 0)):
        tags = []
        if s.get("rank_strength"):
            tags.append(f"强度#{s['rank_strength']}")
        if s.get("rank_rise"):
            tags.append(f"涨幅#{s['rank_rise']}")
        if s.get("rank_net"):
            tags.append(f"净额#{s['rank_net']}")
        print(f"  {s['name']:<8} 涨幅{s['zf_interval']}% 净额{_fmt_money(s['net_interval'])} "
              f"强度{s.get('strength')} [{'/'.join(tags)}]")
    print(f"\n【区间个股榜】(涨幅龙头/净额吸金, 共 {len(d['stocks'])} 只)")
    for s in d["stocks"]:
        tags = []
        if s.get("rank_rise"):
            tags.append(f"涨幅#{s['rank_rise']}")
        if s.get("rank_net"):
            tags.append(f"净额#{s['rank_net']}")
        print(f"  {s['name']:<7}({s['code']}) 区间涨幅{s['zf_interval']}% "
              f"净额{_fmt_money(s['net_interval'])} 换手{s['hsl_interval']}% "
              f"[{'/'.join(tags)}] {s['concept']}")
    if not d["sectors"] and not d["stocks"]:
        print(BLOCKED_HINT)


def main():
    ap = argparse.ArgumentParser(description="开盘啦区间榜(个股/板块)数据")
    ap.add_argument("--start", help="区间开始 YYYY-MM-DD(默认按 --days 推算)")
    ap.add_argument("--end", help="区间结束 YYYY-MM-DD(默认最近工作日)")
    ap.add_argument("--days", type=int, default=5,
                    help="未给 start/end 时取近 N 个工作日，默认 5；/fupan 近3天用 --days 3")
    ap.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = ap.parse_args()
    d = fetch_all(args.start, args.end, days=args.days)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        _print_human(d)


if __name__ == "__main__":
    main()
