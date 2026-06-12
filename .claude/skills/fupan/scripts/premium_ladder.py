#!/usr/bin/env python3
"""
V5.1 接力情绪 + 涨停梯队 分析工具
为 /fupan 复盘补齐三块「龙头选手命根子」数据：

  1. 赚钱效应温度计 —— 昨日涨停股今日表现（平均涨幅/红盘率/继续涨停率）
  2. 连板晋级率   —— 首板晋级率 + 各高度晋级率 + 连板晋级率
  3. 涨停梯队结构 —— 按连板数分层 + 断层检测 + 高位股退潮指数

数据源（均为 datacenter-web 接口，IP 封禁风险低，每天一拉即可）：
  - ak.stock_zt_pool_em(date)           今日涨停池        → 梯队
  - ak.stock_zt_pool_previous_em(date)  昨日涨停股今日表现 → 赚钱效应/晋级率/高位退潮

用法：
  ~/.claude/mcp-servers/astock-data/venv/bin/python3 premium_ladder.py --date 20260521 --json
"""
import sys
import json
import argparse
import warnings

warnings.filterwarnings("ignore")


def _zt_threshold(code: str, name: str = "") -> float:
    """该股今日视为『继续涨停』的涨幅阈值
    ST→4.8 / 创业板科创板(30/68)→19.0 / 北交所(43/83/87/88/92)→29.5 / 主板→9.5"""
    if name and "ST" in str(name).upper():
        return 4.8
    c = str(code)
    if c.startswith(("30", "68")):
        return 19.0
    if c.startswith(("43", "83", "87", "88", "92")):
        return 29.5
    return 9.5


def _safe_float(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _safe_int(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def analyze(date_str: str) -> dict:
    import akshare as ak

    out = {"date": date_str, "errors": []}

    # ============ 1. 今日涨停梯队 ============
    ladder = {}
    try:
        zt = ak.stock_zt_pool_em(date=date_str)
        if zt is not None and len(zt) > 0:
            for _, r in zt.iterrows():
                h = _safe_int(r.get("连板数"), 1) or 1
                ladder.setdefault(h, []).append({
                    "name": r.get("名称", ""),
                    "code": str(r.get("代码", "")),
                    "amount": round(_safe_float(r.get("成交额")) / 1e8, 2),
                    "first_seal": str(r.get("首次封板时间", "")),
                    "zab": _safe_int(r.get("炸板次数")),
                    "sector": r.get("所属行业", ""),
                })
        out["zt_count"] = sum(len(v) for v in ladder.values())
    except Exception as e:
        out["errors"].append(f"涨停池抓取失败: {e}")
        out["zt_count"] = 0

    heights = sorted(ladder.keys(), reverse=True)
    out["max_height"] = heights[0] if heights else 0
    out["ladder"] = [
        {
            "height": h,
            "count": len(ladder[h]),
            "stocks": sorted(
                [{"name": s["name"], "code": s["code"], "amount": s["amount"]}
                 for s in ladder[h]],
                key=lambda x: -x["amount"],
            ),
        }
        for h in heights
    ]
    # 断层：从最高板往下到 2 板，缺哪几层
    gaps = [h for h in range(heights[0], 1, -1) if h not in ladder] if heights else []
    out["ladder_gaps"] = gaps
    # 顶部连续性 & 是否独苗高标
    if len(heights) >= 2:
        out["top_continuous"] = (heights[0] - heights[1] == 1)
    else:
        out["top_continuous"] = bool(heights)
    out["is_solo_top"] = bool(heights and len(ladder.get(heights[0], [])) == 1)

    # ============ 2. 昨日涨停今日表现 → 赚钱效应 + 晋级率 + 高位退潮 ============
    try:
        prev = ak.stock_zt_pool_previous_em(date=date_str)
        if prev is not None and len(prev) > 0:
            rows = []
            for _, r in prev.iterrows():
                code = str(r.get("代码", ""))
                name = str(r.get("名称", ""))
                chg = _safe_float(r.get("涨跌幅"))
                yb = _safe_int(r.get("昨日连板数"), 1) or 1
                # 优先用涨停价比价判晋级（最可靠），缺涨停价/最新价时退回阈值法
                ztp = _safe_float(r.get("涨停价"))
                last = _safe_float(r.get("最新价"))
                if ztp > 0 and last > 0:
                    zt_today = last >= ztp * 0.999
                else:
                    zt_today = chg >= _zt_threshold(code, name)
                rows.append({
                    "code": code,
                    "name": name,
                    "chg": chg,
                    "yb": yb,
                    "zt_today": zt_today,
                })
            n = len(rows)
            up = sum(1 for x in rows if x["chg"] > 0)
            avg = round(sum(x["chg"] for x in rows) / n, 2)
            zt_again = sum(1 for x in rows if x["zt_today"])
            if avg >= 3:
                lvl = "强赚钱效应"
            elif avg >= 0:
                lvl = "弱赚钱效应"
            elif avg >= -3:
                lvl = "弱亏钱效应"
            else:
                lvl = "强亏钱效应"
            out["premium"] = {
                "sample": n,
                "avg_chg": avg,
                "red_rate": round(up / n * 100, 1),
                "zt_again": zt_again,
                "zt_again_rate": round(zt_again / n * 100, 1),
                "level": lvl,
            }

            # 晋级率：按昨日连板数分组
            promo = {}
            for h in sorted(set(x["yb"] for x in rows)):
                grp = [x for x in rows if x["yb"] == h]
                g_zt = sum(1 for x in grp if x["zt_today"])
                promo[str(h)] = {
                    "base": len(grp),
                    "promoted": g_zt,
                    "rate": round(g_zt / len(grp) * 100, 1) if grp else 0,
                }
            out["promotion"] = promo
            out["first_board_promo"] = promo.get("1", {}).get("rate", 0)
            lb = [x for x in rows if x["yb"] >= 2]
            out["lianban_promo"] = (
                round(sum(1 for x in lb if x["zt_today"]) / len(lb) * 100, 1) if lb else 0
            )

            # 高位股退潮指数（昨日 ≥3 板）
            hi = [x for x in rows if x["yb"] >= 3]
            if hi:
                out["high_tide"] = {
                    "sample": len(hi),
                    "red_rate": round(sum(1 for x in hi if x["chg"] > 0) / len(hi) * 100, 1),
                    "avg_chg": round(sum(x["chg"] for x in hi) / len(hi), 2),
                    "zt_again": sum(1 for x in hi if x["zt_today"]),
                    "broken": sorted(
                        [{"name": x["name"], "code": x["code"], "chg": round(x["chg"], 2)}
                         for x in hi if x["chg"] <= 0],
                        key=lambda x: x["chg"],
                    ),
                }
            else:
                out["high_tide"] = {"sample": 0}
        else:
            out["errors"].append("昨日涨停池为空（可能上一日为非交易日）")
    except Exception as e:
        out["errors"].append(f"昨日涨停池抓取失败: {e}")

    return out


def render_text(d: dict) -> str:
    L = []
    L.append(f"\n{'='*60}")
    L.append(f"  📊 V5.1 接力情绪 + 涨停梯队 | {d['date']}")
    L.append(f"{'='*60}\n")

    p = d.get("premium")
    if p:
        L.append("💰 赚钱效应温度计（昨日涨停股今日表现）")
        L.append(f"  样本 {p['sample']} 只 | 平均涨幅 {p['avg_chg']:+.2f}% | "
                 f"红盘率 {p['red_rate']}% | 继续涨停 {p['zt_again']}只({p['zt_again_rate']}%)")
        L.append(f"  → {p['level']}\n")

    if "first_board_promo" in d:
        L.append("🪜 连板晋级率")
        L.append(f"  首板晋级率：{d['first_board_promo']}%（昨日首板今日封板比例）")
        L.append(f"  连板晋级率：{d['lianban_promo']}%（昨日≥2板今日继续涨停比例）")
        for h, v in sorted(d.get("promotion", {}).items(), key=lambda x: int(x[0])):
            L.append(f"    昨日{h}板→今日晋级：{v['promoted']}/{v['base']} = {v['rate']}%")
        L.append("")

    ht = d.get("high_tide", {})
    if ht.get("sample", 0) > 0:
        L.append("🌊 高位股退潮指数（昨日≥3板个股今日表现）")
        L.append(f"  样本 {ht['sample']} 只 | 红盘率 {ht['red_rate']}% | "
                 f"平均涨幅 {ht['avg_chg']:+.2f}% | 继续涨停 {ht['zt_again']}只")
        if ht.get("broken"):
            bad = "，".join(f"{x['name']}{x['chg']:+.1f}%" for x in ht["broken"][:8])
            L.append(f"  ⚠️ 高位走弱：{bad}")
        L.append("")

    L.append("📈 涨停梯队结构")
    L.append(f"  今日涨停 {d.get('zt_count', 0)} 家 | 最高 {d.get('max_height', 0)} 板")
    for tier in d.get("ladder", []):
        names = "、".join(f"{s['name']}({s['amount']}亿)" for s in tier["stocks"][:6])
        L.append(f"  {tier['height']:>2}板 ×{tier['count']:<2} {names}")
    if d.get("ladder_gaps"):
        L.append(f"  ⚠️ 梯队断层：缺 {'、'.join(str(g)+'板' for g in d['ladder_gaps'])}")
    if not d.get("top_continuous"):
        L.append("  ⚠️ 顶部不连续：最高板与次高板之间断层，高度龙头悬空")
    if d.get("is_solo_top"):
        L.append("  ⚠️ 最高板为独苗（仅1只），缺梯队支撑")
    L.append("")

    if d.get("errors"):
        L.append("❗ 数据告警：")
        for e in d["errors"]:
            L.append(f"  - {e}")
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="V5.1 接力情绪 + 涨停梯队 分析")
    ap.add_argument("--date", required=True, help="复盘日期 YYYYMMDD")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    result = analyze(args.date)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))
