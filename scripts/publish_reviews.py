#!/usr/bin/env python3
"""把 /fupan 和 /jieli 跑完的报告自动发布到 data/reviews/ 并提交+推送到 dev。

链路：
  /fupan 收尾 → ~/claudeCode/fupan_<date>.md          → data/reviews/<date>_fupan.md
  /jieli 收尾 → ~/.claude/skills/jieli/.cache/jieli_pool_<date>.json → data/reviews/<date>_jieli.md（渲染）

特性：
  - 幂等：内容没变不写、不提交，可被 cron 每隔几分钟反复调用。
  - 本机就是线上服务器（fupan.service 直接读这个工作树的 data/reviews/），
    所以文件一落盘就实时生效；git commit/push 仅用于 Render 镜像 + 历史留痕。
  - push 尽力而为：失败不影响本机线上更新，只记日志。
  - 只处理最近 MAX_AGE_DAYS 天的源文件，避免复活早已删除的旧报告。
"""
import os
import re
import glob
import json
import subprocess
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEWS = os.path.join(REPO, "data", "reviews")
HOME = os.path.expanduser("~")
CLAUDECODE = os.path.join(HOME, "claudeCode")
JIELI_CACHE = os.path.join(HOME, ".claude", "skills", "jieli", ".cache")

MAX_AGE_DAYS = 7
TARGET_BRANCH = "dev"


def _recent(path):
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        return datetime.now() - mtime <= timedelta(days=MAX_AGE_DAYS)
    except OSError:
        return False


def write_if_changed(path, content):
    """只有内容真的变了才写，返回是否写入。"""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


# ---------- fupan：直接搬运 skill 写好的完整 markdown ----------

def publish_fupan():
    changed = []
    pattern = os.path.join(CLAUDECODE, "fupan_20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].md")
    for src in sorted(glob.glob(pattern)):
        if not _recent(src):
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(src))
        if not m:
            continue
        date = m.group(1)
        with open(src, encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            continue  # 跳过空占位文件
        dst = os.path.join(REVIEWS, f"{date}_fupan.md")
        if write_if_changed(dst, content):
            changed.append(f"{date}_fupan.md")
    return changed


# ---------- jingjia：直接搬运 skill 写好的完整 markdown（同 fupan）----------

def publish_jingjia():
    changed = []
    pattern = os.path.join(CLAUDECODE, "jingjia_20[0-9][0-9]-[0-9][0-9]-[0-9][0-9].md")
    for src in sorted(glob.glob(pattern)):
        if not _recent(src):
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(src))
        if not m:
            continue
        date = m.group(1)
        with open(src, encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            continue  # 跳过空占位文件
        dst = os.path.join(REVIEWS, f"{date}_jingjia.md")
        if write_if_changed(dst, content):
            changed.append(f"{date}_jingjia.md")
    return changed


# ---------- jieli：从盯盘池 JSON 渲染 markdown ----------

def _cell(x):
    """安全写进 markdown 表格单元格：转字符串、去换行、转义竖线。"""
    s = "" if x is None else str(x)
    return s.replace("\n", " ").replace("|", "\\|").strip()


def _count(v):
    """把跟风条目数化：list→长度，数字→自身，纯数字串→int，
    含数字的描述串→取首个数字，非数字描述串→None（未知）。"""
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, (list, tuple)):
        return len(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return 0
        if re.fullmatch(r"\d+", s):
            return int(s)
        m = re.search(r"\d+", s)
        return int(m.group()) if m else None
    return None


def _follower_counts(gf):
    """从跟风清单导出 (连板跟风数, 首板跟风数, 合计)，鲁棒处理串/表/数。"""
    if not isinstance(gf, dict):
        return None, None, None
    lb = _count(gf.get("连板跟风"))
    sb_raw = gf.get("首板跟风")
    if sb_raw is None and "首板跟风数" in gf:
        sb_raw = gf.get("首板跟风数")
    sb = _count(sb_raw)
    total = gf.get("合计")
    if isinstance(total, bool):
        total = None
    if isinstance(total, (int, float)):
        tot = int(total)
    elif isinstance(total, str) and re.fullmatch(r"\s*\d+\s*", total):
        tot = int(total)
    elif lb is not None and sb is not None:
        tot = lb + sb
    else:
        tot = None
    return lb, sb, tot


def _board_height(v):
    """从连板数字段抽取连板高度：'6天6板'→6，'4板'→4，'连续2板(...)'→2。"""
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        m = re.search(r"(\d+)\s*板", v)
        if m:
            return int(m.group(1))
        m = re.search(r"\d+", v)
        if m:
            return int(m.group())
    return 0


def _amount(v):
    """成交额化为可比较的数值（统一到“亿”量级），无法解析返回 None。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"(\d+(?:\.\d+)?)", v)
        if m:
            x = float(m.group(1))
            if "万" in v and "亿" not in v:
                x /= 10000.0
            return x
    return None


def _fc(x):
    return "?" if x is None else str(x)


def _stock_name(s):
    return s.get("name") or s.get("名称") or s.get("股票") or ""


def _stock_code(s):
    return s.get("code") or s.get("代码") or s.get("symbol") or ""


def _stock_evidence(s):
    return s.get("核心证据") or s.get("一句话证据") or s.get("证据") or ""


def _stock_amount(s):
    return s.get("成交") if s.get("成交") is not None else s.get("成交额")


def render_jieli(pool):
    date = pool.get("date", "")
    mk = pool.get("market", {}) or {}
    lines = [f"# 🎯 连板接力盯盘池 · {date}", ""]

    if pool.get("baseline"):
        lines.append("> 基准日（无昨日盯盘池对比）。框架：jieli「真龙三标准」逐只判定。")
    else:
        lines.append("> 框架：jieli「真龙三标准」逐只判定（含昨日盯盘池 D2 升降级）。")
    lines.append("")

    # --- 市场格局：精简表，昨日待验证闭环单独成行 ---
    d2 = mk.get("昨日待验证闭环")
    if mk:
        lines.append("## 市场格局")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|---|---|")
        for k, v in mk.items():
            if k == "昨日待验证闭环":
                continue
            lines.append(f"| {_cell(k)} | {_cell(v)} |")
        lines.append("")
    if d2:
        lines.append(f"**昨日待验证闭环（D2）**：{_cell(d2)}")
        lines.append("")

    # --- 预计算每只 2板+ 个股的派生量 ---
    raw_stocks = pool.get("stocks", []) or []
    items = []
    for s in raw_stocks:
        height = _board_height(s.get("连板数"))
        if height < 2:
            continue
        lb, sb, tot = _follower_counts(s.get("跟风清单"))
        sector = (s.get("主板块") or "").strip() or "未分类"
        theme = (s.get("主线") or "").strip()
        items.append({
            "s": s,
            "height": height,
            "lb": lb, "sb": sb, "tot": tot,
            "amt": _amount(_stock_amount(s)),
            "sector": sector,
            "theme": theme,
            # 板块内地位/归堆按"主线"（短线叙事归并）优先，无主线回退权威板块
            "group": theme or sector,
        })

    # 板块内每只最高连板高度（按主线归堆）
    sector_max = {}
    for it in items:
        sector_max[it["group"]] = max(sector_max.get(it["group"], 0), it["height"])
    sector_max_cnt = {}
    for it in items:
        if it["height"] == sector_max[it["group"]]:
            sector_max_cnt[it["group"]] = sector_max_cnt.get(it["group"], 0) + 1

    def _status(it):
        if it["height"] == sector_max[it["group"]]:
            return "并列最高" if sector_max_cnt[it["group"]] > 1 else "最高板"
        if it["tot"] == 0:
            return "独苗"
        return "跟风"

    # --- 主表：每只 2板+ 一行 ---
    if items:
        lines.append(f"## 连板主体一览（{len(items)} 只 · 2板+）")
        lines.append("")
        lines.append("| 票 | 连板 | 主板块 | 板块内地位 | 跟风(连板/首板/合计) | 龙头判定 | 核心证据 |")
        lines.append("|---|---|---|---|---|---|---|")
        for it in items:
            s = it["s"]
            evid = ""
            std = s.get("真龙三标准")
            if isinstance(std, dict) and std.get("明细"):
                evid = std["明细"]
            else:
                fallback_evid = _stock_evidence(s)
                bits = [b for b in (fallback_evid, _stock_amount(s), s.get("炸板次数") is not None and f"炸板{s['炸板次数']}次") if b]
                evid = " ｜ ".join(str(b) for b in bits)
            flw = f"{_fc(it['lb'])}/{_fc(it['sb'])}/{_fc(it['tot'])}"
            # 权威板块 + 主线归并（主线与权威板块不同才追加，避免冗余）
            sector_disp = it["sector"]
            if it["theme"] and it["theme"] != it["sector"]:
                sector_disp = f"{it['sector']}›{it['theme']}"
            lines.append(
                f"| {_cell(_stock_name(s))}({_cell(_stock_code(s))}) "
                f"| {_cell(s.get('连板数',''))} | {_cell(sector_disp)} "
                f"| {_cell(_status(it))} | {flw} "
                f"| {_cell(s.get('龙头判定',''))} | {_cell(evid)} |"
            )
        lines.append("")

    # --- 板块龙头小结：每条主线/板块一行（按主线归堆） ---
    sectors = []
    for it in items:
        if it["group"] not in sectors:
            sectors.append(it["group"])
    if sectors:
        lines.append("## 板块龙头小结")
        lines.append("")
        lines.append("| 板块 | 龙头 | 高度 | 跟风(连板/首板/合计) | 板块结论 |")
        lines.append("|---|---|---|---|---|")
        for sec in sectors:
            members = [it for it in items if it["group"] == sec]
            leader = sorted(
                members,
                key=lambda it: (
                    it["height"],
                    it["tot"] if it["tot"] is not None else -1,
                    it["amt"] if it["amt"] is not None else -1,
                ),
                reverse=True,
            )[0]
            ls = leader["s"]
            tot = leader["tot"]
            if tot is None:
                concl = "跟风数据不全·待确认"
            elif tot == 0:
                concl = "独苗/事件驱动·无板块共振"
            elif tot >= 3:
                concl = "板块共振成立·龙头确立"
            else:
                concl = "弱共振·龙头待确认"
            flw = f"{_fc(leader['lb'])}/{_fc(leader['sb'])}/{_fc(leader['tot'])}"
            lines.append(
                f"| {_cell(sec)} | {_cell(_stock_name(ls))}({_cell(_stock_code(ls))}) "
                f"| {leader['height']}板 | {flw} | {_cell(concl)} |"
            )
        lines.append("")

    # --- 结论：summary 作为精炼收口 ---
    if pool.get("summary"):
        lines.append("## 盯盘池结论")
        lines.append("")
        lines.append("> " + _cell(pool["summary"]))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def publish_jieli():
    changed = []
    pattern = os.path.join(JIELI_CACHE, "jieli_pool_20*.json")
    for src in sorted(glob.glob(pattern)):
        if not _recent(src):
            continue
        try:
            with open(src, encoding="utf-8") as f:
                pool = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        date = pool.get("date")
        # 严格校验 YYYY-MM-DD：app.py 只认这个格式，曾因 "20260609" 产出
        # 20260609_jieli.md（无连字符），发布"成功"但网站永远不显示。
        if not date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
            print(f"[publish_jieli] 日期格式非法（{date!r}），跳过 {os.path.basename(src)}")
            continue
        md = render_jieli(pool)
        dst = os.path.join(REVIEWS, f"{date}_jieli.md")
        if write_if_changed(dst, md):
            changed.append(f"{date}_jieli.md")
    return changed


# ---------- git ----------

def git(*args, timeout=60):
    return subprocess.run(
        ["git", "-C", REPO, *args],
        capture_output=True, text=True, timeout=timeout,
    )


def current_branch():
    r = git("rev-parse", "--abbrev-ref", "HEAD")
    return r.stdout.strip()


def commit_and_push(changed):
    git("add", "data/reviews")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return "nothing staged"
    branch = current_branch()
    msg = "复盘模块：自动发布 " + ", ".join(changed)
    rc = git("commit", "-m", msg)
    if rc.returncode != 0:
        # commit 失败（如 index.lock 残留）不能继续 push，否则推的是旧 HEAD
        return f"commit failed: {(rc.stderr or rc.stdout).strip()[:200]}，跳过 push"
    if branch != TARGET_BRANCH:
        return f"committed on {branch} (≠{TARGET_BRANCH})，跳过 push"
    try:
        r = git("push", "origin", TARGET_BRANCH, timeout=90)
        return "pushed" if r.returncode == 0 else f"push failed: {r.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        return "push timeout"


def main():
    os.makedirs(REVIEWS, exist_ok=True)
    changed = publish_fupan() + publish_jingjia() + publish_jieli()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not changed:
        print(f"[{stamp}] no change")
        return
    status = commit_and_push(changed)
    print(f"[{stamp}] published {changed} -> {status}")


if __name__ == "__main__":
    main()
