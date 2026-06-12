#!/usr/bin/env python3
"""
/jingjia 集合竞价资金榜单抓取 + 规则层预筛脚本

数据源：duanxianxia jjzhuli.json（竞价主力净额，9:25 撮合结算），复用 fupan 项目 scraper.py
鉴权：环境变量 DXX_USERNAME/DXX_PASSWORD，或 ~/.claude/duanxianxia_credentials.json

v2（2026-06-12）：把 SKILL.md 里所有**纯规则判定**下沉到脚本，一次调用全部算好——
LLM 只需做"板块共振校验 + 最终三只定稿"，不再逐只人肉算三态/占比档/换手档/级别。
- 每行预算：三态格子 / 占比档 / 换手档 / 预判级别（A/B/C/D/参考龙头/陷阱/观望）
- 头部自带北京时间 + 时段口径（不用再单独跑 date）
- 板块聚类（概念 token 计数 + 一字锚点），辅助共振判定
- 脚本预筛小结：候选清单 / ≥45% 占比榜 / 黑名单建议 / 跨级决胜提示

用法：
    python fetch_jjyd.py              # Markdown（默认 15 只）
    python fetch_jjyd.py -n 20        # 改条数
    python fetch_jjyd.py --json       # JSON（含全部预判 tag）

⚠️ 接口只能返回**当下时刻**实时数据，没有历史。
字段口径（scraper.parse_jjyd）：
    jjzf  → 竞价涨幅 (9:25 撮合价 vs 昨收)
    zhuli → 竞价主力净额 (万元，本脚本换算为元)
    jje   → 竞价成交额 (万元，换算为元后存 cuohe)
    jjhs  → 竞价换手 % (竞价成交/流通股本，数据自带)
    ltsz  → 流通市值 (亿元)
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone, timedelta


def _locate_fupan_dir():
    """定位含 scraper.py 的 fupan 仓库根。
    本文件就在 <repo>/.claude/skills/jingjia/scripts/ 下，相对 __file__ 上溯即可
    （realpath 兼容经 ~/.claude/skills symlink 调用）；FUPAN_DIR 环境变量可覆盖。"""
    env = os.environ.get("FUPAN_DIR")
    repo = os.path.realpath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", ".."))
    for d in (env, repo):
        if d and os.path.isfile(os.path.join(d, "scraper.py")):
            return d
    raise RuntimeError(
        "找不到 fupan/scraper.py。请设置环境变量 FUPAN_DIR 指向含 scraper.py 的目录"
    )


FUPAN_DIR = _locate_fupan_dir()
if FUPAN_DIR not in sys.path:
    sys.path.insert(0, FUPAN_DIR)

import scraper  # noqa: E402

CN_TZ = timezone(timedelta(hours=8))

# D 级换庄候选的竞价换手门槛（新口径=竞价成交/流通股本）。
# 初定 1.0%：落在 SKILL.md 换手分档"0.5~1.5% 真用力"的上半段
# （2026-06-12 初定，旧"竞价成交/昨日成交≥4%"口径作废；样本少，可按实战回测微调）。
D_TURNOVER_MIN = 1.0
# 跨级决胜：平开 A/B/C 候选竞价换手全部低于该值 = "主力没用力"（同上初定）
WEAK_TURNOVER = 0.3


def limit_pct(code):
    """按代码判涨停幅度：科创/创业 20%，北交所 30%（含 920 新段），主板 10%。"""
    c = str(code)
    if c.startswith(("30", "68")):
        return 20.0
    if c.startswith(("8", "4", "92")):
        return 30.0
    return 10.0


def fmt_amount(v):
    """元 → 万/亿 简写"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e8:
        return f"{sign}{v/1e8:.2f}亿"
    if v >= 1e4:
        return f"{sign}{v/1e4:.0f}万"
    return f"{sign}{v:.0f}"


def fmt_pct(v):
    if v is None or v == "none" or v == "-":
        return "-"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return str(v)


def fmt_ratio(v):
    if v is None:
        return "-"
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return "-"


def fmt_pct_plain(v):
    if v is None or v == "":
        return "-"
    try:
        return f"{float(v):.2f}%"
    except (TypeError, ValueError):
        return "-"


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def session_label(now=None):
    """北京时间 → (时段名, 占比口径说明)。"""
    now = now or datetime.now(CN_TZ)
    hm = now.hour * 100 + now.minute
    if now.weekday() >= 5:
        return "非交易日", "榜单为上一交易日快照，占比=全天主力沉淀，可信度低"
    if 925 <= hm < 930:
        return "9:25-9:30 最佳窗口", "占比=纯竞价坚决度，可信度高"
    if 930 <= hm < 1500:
        return "盘中", "净额/成交为开盘后累计口径，占比按『持续追入力度』解读；三态仍按 9:25 撮合价"
    if hm < 925:
        return "竞价未结束", "9:25 撮合前数据不全，建议 9:25 后再跑"
    return "盘后", "净额/成交为全天累计，占比=全天主力沉淀，非纯竞价坚决度"


def classify_form(jjzf, lim):
    """三态格子。返回 (form_key, 显示名)。"""
    if jjzf is None:
        return "unknown", "—"
    if jjzf >= lim * 0.98:
        return "yizi", "⭐一字涨停"
    if jjzf >= lim * 0.7:
        return "near_limit", "⭐接近涨停"
    if jjzf >= 5:
        return "gaokai", "高开(+5%↑)"
    if jjzf >= 3:
        return "fuzzy", "微高开(+3~5%模糊带)"
    if jjzf >= -2:
        return "pingkai", "平开/微动"
    if jjzf >= -3:
        return "edge", "平开偏弱(-3~-2%)"
    if jjzf >= -7:
        return "shallow_low", "浅水低开(-3~-7%)"
    return "deep_low", "深水低开(≤-7%)"


def ratio_grade(ratio):
    if ratio is None:
        return "—"
    if ratio >= 70:
        return "🔥极坚决(≥70)"
    if ratio >= 50:
        return "✅坚决(50-70)"
    if ratio >= 30:
        return "⚪中等(30-50)"
    return "⚠️分散(<30)"


def turnover_grade(jjhs):
    if jjhs is None:
        return "—"
    if jjhs > 1.5:
        return "⚠️极端(>1.5)"
    if jjhs >= 0.5:
        return "🔥真用力(0.5-1.5)"
    if jjhs >= 0.2:
        return "偏活跃(0.2-0.5)"
    return "⚪常态(<0.2)"


def verdict(form_key, ratio, jjhs, cuohe):
    """预判级别（规则层）。板块共振 / 龙头基本面由 LLM 校验后定稿。"""
    tags = []
    if form_key in ("yizi", "near_limit"):
        tags.append("⭐参考龙头(排除候选,主线锚点)")
    elif form_key == "gaokai":
        tags.append("⚠️高开诱多嫌疑(排除)")
    elif form_key == "fuzzy":
        tags.append("💤模糊带(占比+共振软判定)")
    elif form_key == "pingkai":
        if ratio is None:
            tags.append("⚪平开观望(占比缺失)")
        elif ratio >= 60:
            tags.append("🥇A级候选(占比≥60)")
        elif ratio >= 40:
            tags.append("🥈B级候选(占比≥40)")
        elif ratio >= 30:
            tags.append("🥉C级候选(占比≥30)")
        else:
            tags.append("⚪平开观望(占比<30)")
    elif form_key == "edge":
        tags.append("⚪形态边缘观望(-3~-2%)")
    elif form_key == "shallow_low":
        tags.append("⚠️浅水低开·倒货嫌疑(待分流)")
    elif form_key == "deep_low":
        if (ratio is not None and ratio >= 40) and (jjhs is not None and jjhs >= D_TURNOVER_MIN):
            tags.append(f"🎲D级换庄候选(占比≥40+换手≥{D_TURNOVER_MIN}%,需LLM验龙头/基本面)")
        else:
            tags.append("💀深水低开·力度不足(拉黑)")
    if ratio is not None and ratio < 30 and cuohe is not None and cuohe >= 1e8:
        tags.append("⚠️对倒嫌疑(占比<30+成交大)")
    return tags


def fetch(n=15):
    raw = scraper.get_jjyd()
    if not raw:
        raise RuntimeError("接口返回空（鉴权失败或非交易时段）")
    parsed = scraper.parse_jjyd(raw)
    for p in parsed:
        z = _f(p.get("zhuli"))
        p["zhuli"] = z * 1e4 if z is not None else None
        j = _f(p.get("jje"))
        p["cuohe"] = j * 1e4 if j is not None else None
        try:
            p["ratio"] = round(float(p["zhuli"]) / float(p["cuohe"]) * 100, 1) if p.get("cuohe") else None
        except (TypeError, ValueError, ZeroDivisionError):
            p["ratio"] = None
    parsed = [p for p in parsed if p.get("zhuli") is not None]
    parsed.sort(key=lambda x: float(x.get("zhuli") or 0), reverse=True)
    rows = parsed[:n]

    for r in rows:
        jjzf = _f(r.get("jjzf"))
        jjhs = _f(r.get("jjhs"))
        lim = limit_pct(r.get("code"))
        form_key, form_name = classify_form(jjzf, lim)
        r["form_key"] = form_key
        r["form"] = form_name
        r["ratio_grade"] = ratio_grade(r.get("ratio"))
        r["turnover_grade"] = turnover_grade(jjhs)
        r["tags"] = verdict(form_key, r.get("ratio"), jjhs, r.get("cuohe"))
        r["hot45"] = bool(r.get("ratio") is not None and r["ratio"] >= 45)
    return rows


def concept_clusters(rows):
    """概念 token 聚类：token → [(name, form_key)]，只回 ≥2 只的（共振线索）。
    原始 concept 字段以 | 或 / 分隔，两种都拆。"""
    m = {}
    for r in rows:
        for tok in str(r.get("concept") or "").replace("|", "/").split("/"):
            tok = tok.strip()
            if tok:
                m.setdefault(tok, []).append((r["name"], r["form_key"]))
    return {k: v for k, v in m.items() if len(v) >= 2}


def _tag_has(rows, *needles):
    """返回 [(row, 命中的tag)]，按命中 tag 展示，避免误显示首个 tag。"""
    out = []
    for r in rows:
        for t in r.get("tags", []):
            if any(nd in t for nd in needles):
                out.append((r, t))
                break
    return out


def to_markdown(rows):
    now = datetime.now(CN_TZ)
    sess, caliber = session_label(now)
    out = [
        f"日期：{now.strftime('%Y-%m-%d')} ｜ 北京时间 {now.strftime('%H:%M')} ｜ 时段：**{sess}**",
        f"口径：{caliber}",
        "",
        "| 排名 | 股票 | 代码 | 概念 | 竞价涨幅 | 净额 | 成交额 | 占比 | 换手% | 流通市值 | 三态 | 脚本预判 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        ltsz = r.get("ltsz")
        out.append("| {rank} | {name} | {code} | {concept} | {jjzf} | {zhuli} | {cuohe} | {ratio} | {jjhs} | {ltsz} | {form} | {tags} |".format(
            rank=i, name=r.get("name", ""), code=r.get("code", ""),
            concept=(r.get("concept") or "-").replace("|", "/"),
            jjzf=fmt_pct(r.get("jjzf")), zhuli=fmt_amount(r.get("zhuli")),
            cuohe=fmt_amount(r.get("cuohe")), ratio=fmt_ratio(r.get("ratio")),
            jjhs=fmt_pct_plain(r.get("jjhs")),
            ltsz=(f"{float(ltsz):.0f}亿" if ltsz not in (None, "") else "-"),
            form=r["form"], tags=" ".join(r["tags"]) or "-",
        ))

    # 板块聚类（共振线索）
    clusters = concept_clusters(rows)
    out.append("")
    out.append("## 板块聚类（榜内同概念 ≥2 只 = 共振线索；权威归属仍以 plate_classifier 为准）")
    if clusters:
        for tok, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
            names = "、".join(
                f"{nm}{'⭐' if fk in ('yizi', 'near_limit') else ''}" for nm, fk in members)
            out.append(f"- **{tok}** ×{len(members)}：{names}")
        out.append("  （⭐=一字/接近涨停锚点；候选与 ⭐ 同概念 = 板块共振加成）")
    else:
        out.append("- 榜内无 ≥2 只同概念，今日竞价榜板块分散")

    # 预筛小结
    anchors = [r for r in rows if r["form_key"] in ("yizi", "near_limit")]
    abc = _tag_has(rows, "A级候选", "B级候选", "C级候选")
    dlevel = _tag_has(rows, "D级换庄候选")
    hot45 = [r for r in rows if r.get("hot45")]
    # 黑名单只收确定性排除项；"待分流/对倒嫌疑"必须留给 LLM 按 SKILL 规则分流，
    # 不许机械判死（曾把"浅水低开·倒货嫌疑(待分流)"误并入黑名单直接拉黑）
    black = _tag_has(rows, "高开诱多", "拉黑")
    pending = _tag_has(rows, "待分流", "对倒嫌疑")

    out.append("")
    out.append("## 脚本预筛小结（规则层；LLM 仅需校验板块共振/龙头基本面后定稿）")
    out.append("- 参考龙头（主线锚点）：" + ("、".join(
        f"{r['name']}({r.get('concept') or '-'})" for r in anchors) if anchors else "无"))
    out.append("- A/B/C 级候选：" + ("、".join(
        f"{r['name']} {t} 换手{fmt_pct_plain(r.get('jjhs'))}" for r, t in abc) if abc else "无"))
    out.append("- D 级换庄候选：" + ("、".join(
        f"{r['name']}(占比{fmt_ratio(r.get('ratio'))}/换手{fmt_pct_plain(r.get('jjhs'))})" for r, _ in dlevel) if dlevel else "无"))
    out.append("- 净额占比 ≥45%：" + ("、".join(
        f"{r['name']}({fmt_ratio(r.get('ratio'))})" for r in hot45) if hot45 else "无"))
    out.append("- 黑名单建议：" + ("、".join(
        f"{r['name']}({t})" for r, t in black) if black else "无"))
    out.append("- 待分流（LLM 按 SKILL 分流规则定夺，禁止直接拉黑）：" + ("、".join(
        f"{r['name']}({t})" for r, t in pending) if pending else "无"))

    abc_all_weak = abc and all((_f(r.get("jjhs")) or 0) < WEAK_TURNOVER for r, _ in abc)
    if abc_all_weak and dlevel:
        out.append(f"- ⚡ 跨级决胜提示：平开候选竞价换手全部 <{WEAK_TURNOVER}%（主力没用力），"
                   f"场上有合规 D 级 → 按 SKILL 规则 D 级优先占主推位（必带三条标注）")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=15, help="返回条数，默认 15")
    ap.add_argument("-d", "--date", default=None,
                    help="（保留参数，仅兼容旧调用；接口只能拉实时，头部已自带日期）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（含预判 tag）而非 Markdown")
    args = ap.parse_args()

    rows = fetch(n=args.n)

    if args.json:
        now = datetime.now(CN_TZ)
        sess, caliber = session_label(now)
        print(json.dumps({
            "date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"),
            "session": sess, "caliber": caliber, "rows": rows,
        }, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(rows))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
