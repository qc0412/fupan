# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 2026-06-12 整页重写：旧版描述的 templates/ 渲染、GitHub Actions 主路径、Render 生产、
> duanxianxia 登录链等均已不存在。本文以当前实际架构为准。

## 项目概述

三部分组成：

1. **行情数据网页**（本机即线上服务器）：Flask API + Vue 3 SPA，展示龙虎榜多日聚合、
   竞价异动、大资金情绪、开盘啦区间榜、复盘报告。
2. **A股短线龙头交易知识库**（`myMd/`）：交易体系/评分框架/复盘流程 Markdown。
3. **三个仓库内 skill**（`.claude/skills/`）：`/fupan` 日复盘、`/jieli` 连板接力、
   `/jingjia` 集合竞价，配套自动化链路（OpenClaw cron + hook + crontab 兜底）。

## 线上架构（生产 = 本机）

```
nginx :80
 ├─ /            → /var/www/fupan（Vue SPA 构建产物，deploy_nosudo.sh 发布）
 └─ /api/, /healthz → 127.0.0.1:5002（gunicorn -w 1，systemd fupan.service）
```

- **后端** `app.py`：内存缓存 `_cache` + 各数据源 TTL 刷新（锁内单线程、失败冷却半个 TTL）。
  - LHB（东财，30 交易日聚合）启动后台抓 + APScheduler 周一~五 18:30 兜底；
  - 竞价异动/大资金情绪：`/` 请求按 TTL 刷（交易时段 30s，非交易 10 分钟）；
  - 开盘啦区间榜：TTL 10 分钟/1 小时；空榜不许覆盖缓存/落盘（dict 恒真，判断必须看 stocks/sectors）；
  - `/api/kpl_interval` 自选区间另有 64 槽短 TTL 查询缓存（一次区间查询最多放大成几十次上游调用，不能裸奔公网）；
  - `_save_to_disk` 写 `data/data.json`（运行时产物，工作树常态脏，不要随手提交）；
  - `/healthz` 返回各块条数。时区判断全走 `CN_TZ = UTC+8`（本机本身就是 Asia/Shanghai）。
- **前端** `frontend/`（Vue 3 + Pinia + Vite）：`stores/market.js` 轮询 `/api/data`
  （交易时段 30s/否则 5 分钟）；KPL 区间榜 tab 自管区间与自刷新（轮询不许覆盖用户手选区间）。
  发布：`./deploy_nosudo.sh`（npm build + rsync 到 `/var/www/fupan`）。
- **后端重载**：`./reload_backend.sh`（control socket 不一定真重启 worker；
  必要时 `kill -HUP <gunicorn master pid>`，确认 worker PID 变了才算数）。

## 常用命令

```bash
python scraper.py                # 手动全量抓数据写 data/data.json（gunicorn 运行时勿并发跑）
python app.py                    # 本地调试 Flask（生产走 systemd fupan.service）
./deploy_nosudo.sh               # 构建前端并发布到 /var/www/fupan
./reload_backend.sh              # 后端热重载（见上方注意事项）
pip install -r requirements.txt
```

## 数据源现状（scraper.py / kpl_api.py）

- **龙虎榜**：东财 `datacenter-web.eastmoney.com`，无需鉴权。
  `fetch_multi_day_lhb()` 回溯最多 60 天找 30 个有数据交易日；剔除 `9` 开头、`ST`、`退`；同日同股保留首条。
- **竞价净额**：`www.duanxianxia.com` AES 加密 JSON（IP 直连子域）。
  文件头的 `_login()/_get_session()/DXX_USERNAME` 是 duanxianxia 旧登录链遗留**死代码**，现行路径不用。
- **大资金情绪**：东财成交额榜 + 腾讯行情交叉验证（护栏：计算型指标多源互证）。
- **开盘啦区间榜**：`kpl_api.py` 是**唯一实现**（接口四条脾气、两端工作日对齐、双向回退都在模块头）。
  `/fupan` skill 的 `scripts/kpl_interval.py` 只是引用它的薄 CLI 包装，改逻辑只改 `kpl_api.py`。
  开盘啦实时打板榜已被验签拦截（见 `kpl_sign.py`），区间榜是仅存裸连接口，哪天也失效则整块降级。

## Skill 与自动化

`/fupan`、`/jieli`、`/jingjia` 随仓库版本管理（**仓库为唯一真相**，`~/.claude/skills/*` 是 symlink）。
它们是 LLM 驱动的分析任务，不是可独立运行的脚本。外部依赖：`~/.claude/mcp-servers/astock-data`
（实时行情）。`mx-data` skill 本机未装——`dfcf_data.py` 调用必挂，主流程不依赖它。

自动化链路分工（2026-06-12 起）：
- **agent 定时运行**：OpenClaw cron（`openclaw cron list`）——周一~五 9:25 竞价、17:15 复盘+接力。
  不要再往 crontab 加 agent 调度，会双跑打架。
- **报告发布**：PostToolUse hook（Write/Edit 落 `~/claudeCode/*.md` 触发）+
  crontab 每 10 分钟 `publish_reviews.py` 兜底（源文件 `scripts/fupan.crontab`）。
  publish 提交 `data/reviews/` 并推送 dev，幂等。
- **企业微信推送已整体移除**（2026-06-12：webhook key 曾泄露进公开 git 历史，直接废弃不恢复）。

## 分支与历史遗留

- 仓库**公开**，工作分支 dev；main 冻结于 2026-06-06，是旧静态站点时代的遗物。
- 遗留待清理（勿当现行架构）：根目录 `index.html`（旧静态页）、`.github/workflows/fetch.yml`
  （已停用，手动触发也会因 templates/ 不存在而失败）、`render.yaml`（Render 镜像，未在维护）、
  scraper 登录链死代码、`.cookie_cache`。
- 凭证卫生：任何 key/token 走 `~/.config/fupan/` 或环境变量，明文严禁入库（已经吃过一次亏）。
