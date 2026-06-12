#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块归类校验器 —— /fupan 和 /jieli 共用的权威板块归类源

为什么要这个脚本
----------------
解决长期痛点：用 AkShare/东财行业字段做板块归类时，SiC/机器人/PCB 核心股被归到
"自动化设/通用设/专用设/电力"这类杂牌军板块；化工不拆细分；跟风票被误判为龙头。

根因：东财行业字段按"公司主业"归类，而短线龙头按"今日为什么涨"归类——两者不对齐。

数据源（5 个接口，实测全部直连无 cookie）
  选股通 surge_stock/plates     当日涨停热点板块清单 + 催化逻辑（description）
  选股通 surge_stock/stocks     每只涨停股的权威板块归属（plates）+ 涨停原因
  选股通 plate/plate_set        板块细分产业链拆解 + core_flag 核心股标记
  同花顺 get_drawdown_stocks    大面池（涨停后最大回撤）——退场预警
  同花顺 attempt_limit          冲板池（冲击涨停未封）——情绪粘性辅助

核心 API
  classify_stocks(codes, date=None)   返回每只票的权威板块归类（取代东财行业字段）
  fetch_plates(date=None)             当日板块清单 + 热点逻辑
  fetch_surge_stocks(date=None)       涨停股 → 板块绑定
  fetch_plate_detail(plate_id)        板块拆细分 + 核心股
  fetch_drawdown(date)                同花顺大面池
  fetch_attempt_limit(date)           同花顺冲板池

CLI
  python3 plate_classifier.py --plates                # 当日热点板块
  python3 plate_classifier.py --surge                 # 涨停股+板块绑定
  python3 plate_classifier.py --classify 300835,688603  # 给定代码反查板块
  python3 plate_classifier.py --plate 53427377        # 拆某板块的细分
  python3 plate_classifier.py --drawdown --date 20260522   # 大面池（--drawdown 是开关，日期走 --date）
  python3 plate_classifier.py --attempt --date 20260522    # 冲板池
  python3 plate_classifier.py --full --date 20260522       # 一次性产出全部 JSON
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

XGB_BASE = "https://flash-api.xuangubao.cn"
THS_BASE = "https://data.10jqka.com.cn"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

XGB_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://flashbao.xuangubao.cn/",
    "Accept": "application/json, text/plain, */*",
}

THS_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://data.10jqka.com.cn/",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}

MAX_RETRY = 3
DELAY_RANGE = (0.3, 0.8)


def _get(url, headers, params=None, timeout=10):
    """带重试的 GET，遇网络抖动指数退避。"""
    last_err = None
    for i in range(MAX_RETRY):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last_err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
        time.sleep(random.uniform(*DELAY_RANGE) * (i + 1))
    raise RuntimeError(f"GET {url} 失败: {last_err}")


def _date_to_ts(date_str):
    """'20260522' or '2026-05-22' -> unix timestamp (秒)，按当日 00:00 CST。"""
    if not date_str:
        return None
    s = date_str.replace("-", "")
    dt = datetime.strptime(s, "%Y%m%d").replace(tzinfo=timezone(timedelta(hours=8)))
    return int(dt.timestamp())


def _normalize_code(code):
    """统一代码格式为 'XXXXXX.SS/SZ'。接受 600519 / sh600519 / 600519.SS 等。"""
    c = str(code).strip().upper().replace("SH", "").replace("SZ", "")
    if "." in c:
        return c
    pure = c.lstrip(".")
    if pure.startswith(("6", "9")):
        return f"{pure}.SS"
    if pure.startswith(("0", "2", "3")):
        return f"{pure}.SZ"
    if pure.startswith(("4", "8")):
        return f"{pure}.BJ"
    return pure


def _pure_code(code):
    """'600519.SS' -> '600519'。"""
    return str(code).split(".")[0]


# =========================================================================
# 选股通三大接口
# =========================================================================

def fetch_plates(date=None):
    """
    当日涨停热点板块清单 + 催化逻辑。
    返回: [{id, name, description}]
    """
    url = f"{XGB_BASE}/api/surge_stock/plates"
    params = {}
    if date:
        ts = _date_to_ts(date)
        if ts:
            params["date"] = ts
    data = _get(url, XGB_HEADERS, params=params)
    items = data.get("data", {}).get("items", [])
    return [
        {
            "id": it.get("id"),
            "name": it.get("name"),
            "description": it.get("description", ""),
        }
        for it in items
    ]


def fetch_surge_stocks(date=None):
    """
    当日涨停股 + 权威板块归属。
    返回: [{code, name, change_pct, board_count_desc, plates:[{id,name}], reason,
            enter_time, narrative_theme, theme_basis}]
    """
    url = f"{XGB_BASE}/api/surge_stock/stocks"
    params = {"normal": "true", "uplimit": "true"}
    if date:
        params["date"] = date.replace("-", "")
    data = _get(url, XGB_HEADERS, params=params)
    fields = data.get("data", {}).get("fields", [])
    items = data.get("data", {}).get("items", [])

    out = []
    for row in items:
        rec = dict(zip(fields, row))
        plates = rec.get("plates") or []
        out.append({
            "code": _pure_code(rec.get("code", "")),
            "code_full": rec.get("code", ""),
            "name": rec.get("prod_name", ""),
            "change_pct": rec.get("px_change_rate", 0.0),
            "circulation_value": rec.get("circulation_value", 0),
            "board_count_desc": rec.get("m_days_n_boards", ""),
            "plates": [{"id": p.get("id"), "name": p.get("name"),
                        "hot_spot": p.get("hot_spot", 0)} for p in plates],
            "reason": rec.get("description", ""),
            "enter_time": rec.get("enter_time", 0),
            "up_limit": rec.get("up_limit", False),
            "turnover_ratio": rec.get("turnover_ratio", 0.0),
        })
    # 叙事归并层：--surge 是 /jieli 首板跟风统计的底座，必须带 narrative_theme，
    # 否则跟风归堆（物理AI/商业航天等）就成了 LLM 自由发挥的口子（保守规则见 narrative_theme()）
    for rec in out:
        theme, basis = narrative_theme(rec.get("plates"), rec.get("reason"))
        rec["narrative_theme"] = theme
        rec["theme_basis"] = basis
    return out


def fetch_plate_detail(plate_id):
    """
    板块细分拆解 + 核心股标记。
    返回: {id, name, desc, avg_pcp, industrial_chains:[{name, stocks:[{code,name,core_flag,desc}]}], all_stocks}
    """
    url = f"{XGB_BASE}/api/plate/plate_set"
    data = _get(url, XGB_HEADERS, params={"id": plate_id})
    d = data.get("data", {}) or {}

    chains = []
    all_stocks = []
    for ch in d.get("industrial_chains", []) or []:
        stocks = []
        for s in ch.get("stock_premium_infos", []) or []:
            sym = s.get("symbol", "")
            stocks.append({
                "code": _pure_code(sym),
                "code_full": sym,
                "core_flag": s.get("core_flag", 0),
                "desc": s.get("desc", ""),
            })
            all_stocks.append({
                "code": _pure_code(sym),
                "code_full": sym,
                "chain": ch.get("name", ""),
                "core_flag": s.get("core_flag", 0),
                "desc": s.get("desc", ""),
            })
        chains.append({
            "id": ch.get("id"),
            "name": ch.get("name", ""),
            "order": ch.get("order", 0),
            "stocks": stocks,
        })

    return {
        "id": d.get("id"),
        "name": d.get("name", ""),
        "desc": d.get("desc", ""),
        "avg_pcp": d.get("avg_pcp", 0.0),
        "core_avg_pcp": d.get("core_avg_pcp", 0.0),
        "core_stocks_count": d.get("core_stocks_count", 0),
        "fund_flow": d.get("fund_flow", 0.0),
        "industrial_chains": chains,
        "all_stocks": all_stocks,
    }


# =========================================================================
# 短线叙事归并层（在权威板块之上，做一层保守的主线归堆）
# =========================================================================
# 痛点：权威板块按"今日为什么涨"归类已经对，但短线叙事常把若干相邻板块
#       归到同一条主线（机器人/具身智能/AI智能制造 → "物理AI"；
#       航天/卫星/北斗/商业航天 → "商业航天"）。这一层只在权威板块 + reason
#       双重命中时才归并，且多主线命中即判歧义、保守不归并，避免过度误伤。
NARRATIVE_THEMES = [
    {
        "name": "物理AI",
        # 板块名命中（强信号）
        "plate_kw": ["机器人", "具身智能", "人形机器人", "智能制造",
                     "工业智能", "机械智能", "机器人数据"],
        # reason 命中（弱信号，做佐证 / reason 驱动）
        "reason_kw": ["具身智能", "人形机器人", "机器人", "AI+智能制造",
                      "AI智能制造", "智能制造", "工业智能", "机器人数据",
                      "机械智能", "动捕", "机器人任务"],
    },
    {
        "name": "商业航天",
        "plate_kw": ["航天", "卫星", "北斗", "商业航天", "航天装备"],
        "reason_kw": ["商业航天", "航天", "卫星", "北斗", "运载火箭",
                      "火箭", "低轨", "星座"],
    },
]


def narrative_theme(plates, reason):
    """
    在权威板块之上做一层保守的短线主线归并。

    输入:  plates = [{id,name}, ...]（权威板块）, reason = 涨停原因文本
    输出:  (theme, basis)
           theme: "物理AI" / "商业航天" / None（保守不归并）
           basis: {theme, rule, matched:[{theme,plate:[kw],reason:[kw]}], candidates}
                  rule: physical_ai_pair（大模型/机器人板块 + AI制造/具身关键词 → 物理AI）
                        plate_hit（板块名唯一命中 → 归并，最高置信）
                        ambiguous_plate（多主线板块名命中 → 歧义，不归并）
                        reason_only_skip（仅 reason 命中、板块名未命中 → 保守不归并）
                        none（未命中）

    决策（保守优先）：优先处理短线明确组合；一般情况下必须"板块名"命中才归并，
    reason 关键词只作佐证 / 依据，不单独触发归并。多条主线的板块名同时命中即判歧义，
    一律不归并。
    """
    plate_names = [p.get("name", "") for p in (plates or [])]
    reason = reason or ""
    hits = {}  # theme -> {"plate": [kw...], "reason": [kw...]}
    for rule in NARRATIVE_THEMES:
        pk = [kw for kw in rule["plate_kw"] if any(kw in pn for pn in plate_names)]
        rk = [kw for kw in rule["reason_kw"] if kw in reason]
        if pk or rk:
            hits[rule["name"]] = {"plate": pk, "reason": rk}

    candidates = list(hits.keys())

    def _basis(theme, rule, themes):
        return {
            "theme": theme,
            "rule": rule,
            "matched": [{"theme": t, **hits[t]} for t in themes],
            "candidates": candidates,
        }

    if not hits:
        return None, {"theme": None, "rule": "none", "matched": [], "candidates": []}

    # 短线特例：权威板块给“人工智能大模型”，但 reason 明确落在 AI+制造/工业/具身/机器人，
    # 盘面通常按“物理AI”合并看。若同时提到商业航天，作为 secondary reason 保留，不抢主线。
    has_ai_model_plate = any("人工智能" in pn or "大模型" in pn for pn in plate_names)
    physical_reason = [kw for kw in ("AI+智能制造", "AI智能制造", "智能制造", "工业智能", "具身智能", "人形机器人", "机器人") if kw in reason]
    if has_ai_model_plate and physical_reason:
        hits.setdefault("物理AI", {"plate": [], "reason": []})
        hits["物理AI"]["plate"] = list(dict.fromkeys(hits["物理AI"]["plate"] + ["人工智能大模型"]))
        hits["物理AI"]["reason"] = list(dict.fromkeys(hits["物理AI"]["reason"] + physical_reason))
        candidates = list(hits.keys())
        return "物理AI", _basis("物理AI", "physical_ai_pair", ["物理AI"])

    plate_themes = [t for t, h in hits.items() if h["plate"]]
    if len(plate_themes) == 1:                        # 板块名唯一命中 → 归并
        t = plate_themes[0]
        return t, _basis(t, "plate_hit", [t])
    if len(plate_themes) >= 2:                        # 多主线板块名命中 → 歧义
        return None, _basis(None, "ambiguous_plate", plate_themes)
    # 仅 reason 命中、板块名未命中 → 保守不归并（只留候选供人工查看）
    return None, _basis(None, "reason_only_skip", candidates)


def classify_stocks(codes, date=None, with_chain=False):
    """
    主 API：给一组股票代码，返回每只的权威板块归类 + 短线主线归并。

    输入:  codes = ["300835", "688603", ...]  date=YYYYMMDD（可空，默认当天）
    输出:  {code: {name, plates:[{id,name}], reason, board_count_desc, source,
                   narrative_theme, theme_basis}}
           source: "surge_stock"（权威）/ "plate_set"（反查命中）/ None（未找到）
           narrative_theme: 归并后的短线主线名（"物理AI"/"商业航天"/None）
           theme_basis:     归类依据（命中的 plate/reason 关键词 + 判定规则）

    工作流程:
    1) 先从 surge_stock/stocks 拉当日涨停股，建立 code→plates 映射（权威）
    2) 未命中的代码，遍历当日 plates 用 plate_set 反查（用于非涨停股）
    """
    surge = fetch_surge_stocks(date=date)
    surge_map = {s["code"]: s for s in surge}

    pure_codes = [_pure_code(c) for c in codes]
    result = {}

    # 第一遍：surge_stock 命中（权威）
    miss = []
    for c in pure_codes:
        if c in surge_map:
            s = surge_map[c]
            result[c] = {
                "name": s["name"],
                "plates": s["plates"],
                "reason": s["reason"],
                "board_count_desc": s["board_count_desc"],
                "change_pct": s["change_pct"],
                "source": "surge_stock",
            }
        else:
            miss.append(c)

    # 第二遍：未命中的，遍历当日板块用 plate_set 反查（成本高，限速）
    if miss and with_chain:
        plates_today = fetch_plates(date=date)
        # 限制反查范围（最热的 30 个板块）防止接口压力过大
        for p in plates_today[:30]:
            try:
                detail = fetch_plate_detail(p["id"])
            except Exception:
                continue
            time.sleep(random.uniform(*DELAY_RANGE))
            for s in detail["all_stocks"]:
                if s["code"] in miss and s["code"] not in result:
                    result[s["code"]] = {
                        "name": None,
                        "plates": [{"id": p["id"], "name": p["name"]}],
                        "reason": s["desc"],
                        "board_count_desc": "",
                        "chain": s["chain"],
                        "core_flag": s["core_flag"],
                        "source": "plate_set",
                    }
            if not [c for c in miss if c not in result]:
                break

    # 补全未找到的（标 source=None）
    for c in pure_codes:
        if c not in result:
            result[c] = {
                "name": None,
                "plates": [],
                "reason": "",
                "board_count_desc": "",
                "source": None,
            }

    # 叙事归并层：为每只票补 narrative_theme + theme_basis（原始权威板块保留在 plates）
    for r in result.values():
        theme, basis = narrative_theme(r.get("plates"), r.get("reason"))
        r["narrative_theme"] = theme
        r["theme_basis"] = basis
    return result


# =========================================================================
# 同花顺：大面池 + 冲板池
# =========================================================================

def fetch_drawdown(date):
    """
    大面池：当日涨停后回撤最深的票（max_drawdown<0 越负越糟）。
    返回: [{code, name, change_pct, max_drawdown, industry_block, main_net_amount, turnover_ratio, ...}]
    """
    url = f"{THS_BASE}/mobileapi/hotspot_focus/stock_pool/v1/get_drawdown_stocks"
    params = {
        "date": date.replace("-", ""),
        "cate": "limit_up",
        "sort_field": "max_drawdown",
        "sort_dir": "asc",
        "page": 1,
        "size": 200,
    }
    data = _get(url, THS_HEADERS, params=params)
    items = data.get("data", {}).get("stock_list", []) or []
    out = []
    for it in items:
        out.append({
            "code": it.get("stock_code", ""),
            "name": it.get("stock_name", ""),
            "change_pct": float(it.get("change", 0) or 0),
            "max_drawdown": float(it.get("max_drawdown", 0) or 0),
            "industry_block": it.get("industry_block", ""),
            "main_net_amount": float(it.get("main_net_amount", 0) or 0),
            "turnover_ratio": float(it.get("effective_turnover_ratio", 0) or 0),
            "is_st": it.get("is_st", False),
            "is_new": it.get("is_new", False),
        })
    return out


def fetch_attempt_limit(date):
    """
    冲板池：当日冲击涨停但未封成功的票（冲多次但封不住=情绪粘性差）。
    返回: [{code, name, change_pct, rise_rate, turnover_ratio, turnover, currency_value}]
    """
    url = f"{THS_BASE}/dataapi/limit_up/limit_up"
    params = {
        "page": 1,
        "limit": 200,
        "field": "199112,10,48,1968584,19,3475914,9003,9004",
        "filter": "HS,GEM2STAR",
        "order_field": "199112",
        "order_type": 0,
        "date": date.replace("-", ""),
    }
    data = _get(url, THS_HEADERS, params=params)
    items = (data.get("data") or {}).get("info", []) or []
    out = []
    for it in items:
        out.append({
            "code": it.get("code", ""),
            "name": it.get("name", ""),
            "change_pct": float(it.get("change_rate", 0) or 0),
            "rise_rate": float(it.get("rise_rate", 0) or 0),
            "turnover_ratio": float(it.get("turnover_rate", 0) or 0),
            "turnover": float(it.get("turnover", 0) or 0),
            "currency_value": float(it.get("currency_value", 0) or 0),
        })
    return out


# =========================================================================
# CLI
# =========================================================================

def _format_summary(data, kind):
    """人读摘要（非 --json 模式）。"""
    lines = []
    if kind == "plates":
        lines.append(f"=== 当日热点板块（共 {len(data)} 个）===")
        for p in data[:25]:
            desc = p["description"][:60] + ("..." if len(p["description"]) > 60 else "")
            lines.append(f"  [{p['id']:>9}] {p['name']:<14} {desc}")
    elif kind == "surge":
        lines.append(f"=== 当日涨停股 + 板块绑定（共 {len(data)} 只）===")
        for s in data[:50]:
            plate_names = " / ".join(p["name"] for p in s["plates"]) or "（无板块）"
            board = s["board_count_desc"] or "首板"
            lines.append(f"  {s['code']} {s['name']:<8} +{s['change_pct']*100:.2f}% {board:<8} [{plate_names}]")
    elif kind == "drawdown":
        lines.append(f"=== 大面池（涨停后回撤排序，共 {len(data)} 只）===")
        for s in data[:20]:
            lines.append(f"  {s['code']} {s['name']:<8} change={s['change_pct']:+.2f}% "
                         f"最大回撤={s['max_drawdown']:.2f}% 主净={s['main_net_amount']/1e8:+.2f}亿 "
                         f"换手={s['turnover_ratio']:.1f}% [{s['industry_block']}]")
    elif kind == "attempt":
        lines.append(f"=== 冲板池（冲击未封，共 {len(data)} 只）===")
        for s in data[:20]:
            lines.append(f"  {s['code']} {s['name']:<8} 当前={s['change_pct']:.2f}% "
                         f"涨速={s['rise_rate']:.2f}% 换手={s['turnover_ratio']:.1f}%")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="板块归类校验器（/fupan 和 /jieli 共用）")
    parser.add_argument("--date", help="日期 YYYYMMDD（默认当日）")
    parser.add_argument("--plates", action="store_true", help="当日热点板块清单")
    parser.add_argument("--surge", action="store_true", help="当日涨停股+板块绑定")
    parser.add_argument("--classify", help="给定代码列表反查板块（逗号分隔）")
    parser.add_argument("--plate", help="拆某板块细分（传 plate id）")
    parser.add_argument("--drawdown", action="store_true", help="同花顺大面池")
    parser.add_argument("--attempt", action="store_true", help="同花顺冲板池")
    parser.add_argument("--full", action="store_true", help="一次性产出全部 JSON")
    parser.add_argument("--json", action="store_true", help="JSON 输出（供 /fupan 程序读取）")
    parser.add_argument("--with-chain", action="store_true",
                        help="--classify 时未命中 surge_stock 的代码做 plate_set 反查（慢）")
    args = parser.parse_args()

    date = args.date

    try:
        if args.full:
            out = {
                "date": date,
                "plates": fetch_plates(date=date),
                "surge_stocks": fetch_surge_stocks(date=date),
                "drawdown": fetch_drawdown(date) if date else [],
                "attempt_limit": fetch_attempt_limit(date) if date else [],
            }
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return

        if args.plate:
            detail = fetch_plate_detail(args.plate)
            if args.json:
                print(json.dumps(detail, ensure_ascii=False, indent=2))
            else:
                print(f"=== {detail['name']}（id={detail['id']}）===")
                print(f"板块均涨: {detail['avg_pcp']*100:+.2f}%  核心均涨: {detail['core_avg_pcp']*100:+.2f}%  "
                      f"核心股: {detail['core_stocks_count']}  资金: {detail['fund_flow']/1e8:+.2f}亿")
                print(f"逻辑: {detail['desc']}")
                for ch in detail["industrial_chains"]:
                    print(f"\n  --- {ch['name']} ---")
                    for s in ch["stocks"]:
                        flag = "★" if s["core_flag"] == 100 else " "
                        d = s["desc"][:80] + ("..." if len(s["desc"]) > 80 else "")
                        print(f"  {flag} {s['code']:<7} {d}")
            return

        if args.classify:
            codes = [c.strip() for c in args.classify.split(",") if c.strip()]
            result = classify_stocks(codes, date=date, with_chain=args.with_chain)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"=== 板块归类反查（{len(codes)} 只）===")
                for c in codes:
                    r = result.get(_pure_code(c), {})
                    plates = " / ".join(p["name"] for p in r.get("plates", [])) or "（未找到）"
                    src = r.get("source") or "N/A"
                    name = r.get("name") or ""
                    board = r.get("board_count_desc") or ""
                    print(f"  {c} {name:<8} [{plates}] {board} <{src}>")
                    theme = r.get("narrative_theme")
                    if theme:
                        basis = r.get("theme_basis") or {}
                        kws = []
                        for m in basis.get("matched", []):
                            kws += m.get("plate", []) + m.get("reason", [])
                        kw_str = "、".join(dict.fromkeys(kws))
                        print(f"      ⇒ 主线: {theme}（{basis.get('rule')}：{kw_str}）")
                    if r.get("reason"):
                        reason = r["reason"][:100] + ("..." if len(r["reason"]) > 100 else "")
                        print(f"      ↳ {reason}")
            return

        if args.plates:
            data = fetch_plates(date=date)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(_format_summary(data, "plates"))
            return

        if args.surge:
            data = fetch_surge_stocks(date=date)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(_format_summary(data, "surge"))
            return

        if args.drawdown:
            if not date:
                print("ERROR: --drawdown 需要 --date 参数", file=sys.stderr)
                sys.exit(1)
            data = fetch_drawdown(date)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(_format_summary(data, "drawdown"))
            return

        if args.attempt:
            if not date:
                print("ERROR: --attempt 需要 --date 参数", file=sys.stderr)
                sys.exit(1)
            data = fetch_attempt_limit(date)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(_format_summary(data, "attempt"))
            return

        parser.print_help()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
