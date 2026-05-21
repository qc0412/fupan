# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

两部分组成：

1. **龙虎榜数据爬虫 + 静态展示页** — 抓取 `duanxianxia.cn` 龙虎榜数据，聚合近 30 个交易日多次上榜个股，渲染为单页 `index.html`。
2. **A股短线龙头交易知识库** (`myMd/`) — Markdown 文档，配合 `fupan` / `fupan-week` 等 skill 使用。

## 常用命令

```bash
# 本地跑爬虫（生成 data/data.json）
python scraper.py

# 本地起 Flask（端口 5002，启动时刷新一次，每天 18:00 定时刷新）
python app.py

# 安装依赖
pip install -r requirements.txt
```

爬虫鉴权：从环境变量 `DXX_USERNAME` / `DXX_PASSWORD` 读取，或回退到 `~/.claude/duanxianxia_credentials.json`。Cookie 缓存在仓库根的 `.cookie_cache`（已 gitignore）。

## 架构关键点

### 数据流与分支策略

`fetch.yml` 工作流是生产路径，本地 `app.py` 主要用于调试：

1. **dev 分支**（GitHub Actions 周一~周五 18:00 北京时间运行）：
   - `python scraper.py` 写 `data/data.json`
   - 内联 Python 用 `templates/index.html` 模板渲染成根目录 `index.html`
   - 提交 `data/data.json` + `index.html` 到 dev
2. **main 分支**：workflow 只把 dev 的 `index.html` cherry-pick 过来，作为对外静态站点。

**修改模板/数据逻辑时**：在 dev 上改 `templates/index.html` 和 `scraper.py`，让 workflow 重新渲染；不要手动改根目录 `index.html`（它会被覆盖）。

### scraper.py 设计

- `_get_session()` 优先使用磁盘 cookie；`get_lhb()` 在响应为空时自动 `_login()` 重试一次，处理 cookie 失效。
- `fetch_multi_day_lhb()` 向前回溯最多 60 天找出 30 个有数据的交易日（跳过周末和无数据日）。
- 过滤规则：剔除以 `9` 开头的代码（B股）和名称含 `ST` 的个股；同一日同股票只保留首条记录。
- 输出按上榜次数倒序排序。

### 展示页过滤

`templates/index.html` 内置 JS 按"近 N 交易日上榜 ≥2 次"动态过滤，N 由按钮切换（3/7/10）。`trading_days` 数组由后端给定，前端只做切片。

## MCP 与 Skill

- `.claude/settings.local.json` 启用 `astock-data` MCP，提供实时 A 股行情查询。
- 复盘任务调用 skill：日复盘 `fupan`、周复盘 `fupan-week`、龙头识别 `earlyLeader`。
- 知识库文档：
  - `myMd/短线交易系统.md` — 交易体系（最强票选股逻辑、买卖条件、仓位管理）
  - `myMd/A股短线龙头复盘框架 V1.0（优化版）.md` — 评分框架
  - `myMd/复盘.md` — 每日复盘流程清单

## 部署

**响应式生产 (Render.com)**：[render.yaml](render.yaml) 部署 Flask 服务，绑定 `dev` 分支（`data/data.json` 提交在 dev）。需在 Render 后台配置 `DXX_USERNAME` / `DXX_PASSWORD`。

[app.py](app.py) 的刷新策略：
- 启动优先 `_load_from_disk()` 读 `data/data.json`，没有数据才阻塞抓 LHB。
- 竞价异动按 TTL 在 `/` 请求时刷新：交易时段 30 秒，非交易时段 10 分钟，锁内单线程。
- LHB 由 `APScheduler` 在北京时间周一~周五 18:30 兜底刷新（主路径仍是 GitHub Actions 18:00 抓数据 → 推 dev → 触发 Render 自动部署）。
- `/healthz` 返回 LHB/竞价条数。
- 时区：所有时间判断走 `CN_TZ = UTC+8`，容器跑在 UTC 也不会算错。

**静态镜像**：`fetch.yml` workflow 把渲染好的 `index.html` cherry-pick 到 main 分支。竞价数据会冻结在 18:00 那一刻的快照，仅适合无后端的镜像部署。
