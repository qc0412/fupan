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

def _fmt_three_std(s):
    if not isinstance(s, dict):
        return ""
    parts = []
    for k in ("板块最高", "带动性", "资金最猛", "明细"):
        if k in s:
            parts.append(f"{k}={s[k]}")
    return " ｜ ".join(str(p) for p in parts)


def _fmt_5q(q):
    if not isinstance(q, dict):
        return ""
    return " / ".join(f"{k}:{v}" for k, v in q.items())


def render_jieli(pool):
    date = pool.get("date", "")
    mk = pool.get("market", {})
    lines = [f"# 🎯 连板接力盯盘池 · {date}", ""]

    if pool.get("baseline"):
        lines.append("> 基准日（无昨日盯盘池对比）。框架：jieli「真龙三标准」逐只判定。")
    else:
        lines.append("> 框架：jieli「真龙三标准」逐只判定（含昨日盯盘池 D2 升降级）。")
    lines.append("")

    if mk:
        lines.append("## 市场格局")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|---|---|")
        for k, v in mk.items():
            lines.append(f"| {k} | {v} |")
        lines.append("")

    pr = pool.get("platerotat_top")
    if isinstance(pr, dict) and pr:
        segs = []
        for name, info in pr.items():
            if isinstance(info, dict):
                bits = [str(info.get(x)) for x in ("rank", "trend", "周期") if info.get(x) is not None]
                segs.append(f"{name}（{'·'.join(bits)}）" if bits else name)
            else:
                segs.append(f"{name}（{info}）")
        lines.append("**板块强度（platerotat）**：" + " ｜ ".join(segs))
        lines.append("")

    stocks = pool.get("stocks", [])
    if stocks:
        lines.append(f"## 连板主体逐只判定（{len(stocks)} 只）")
        lines.append("")
        for s in stocks:
            verdict = s.get("龙头判定", "")
            lines.append(f"### {verdict} {s.get('name','')}({s.get('code','')})")
            meta = []
            for k in ("连板数", "炸板次数", "成交", "换手", "主板块"):
                if s.get(k) not in (None, ""):
                    meta.append(f"{k} {s[k]}")
            if meta:
                lines.append("- " + " ｜ ".join(str(x) for x in meta))
            if s.get("类型"):
                lines.append(f"- 类型：{s['类型']} ｜ 板块周期：{s.get('板块周期','')} ｜ 接力价值：{s.get('接力价值','')}")
            std = _fmt_three_std(s.get("真龙三标准"))
            if std:
                lines.append(f"- 真龙三标准：{std}")
            q5 = _fmt_5q(s.get("分歧日5问"))
            if q5:
                lines.append(f"- 分歧日5问：{q5}")
            if s.get("待验证") and s.get("D2验证日期"):
                lines.append(f"- ⏸️ 待验证 → D2 验证日 **{s['D2验证日期']}**")
            lines.append("")

    if pool.get("summary"):
        lines.append("## 盯盘池结论")
        lines.append("")
        lines.append("> " + pool["summary"])
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
        if not date:
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
    git("commit", "-m", msg)
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
