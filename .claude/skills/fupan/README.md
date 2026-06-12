# A股短线龙头复盘助手（/fupan）

> ⚠️ 本文件只是入口说明。**唯一权威规范是 [SKILL.md](SKILL.md)（当前 V5.3.1）**——框架、评分、自检、数据源清单全部以它为准；本文件不重复任何会过期的细节。

## 用法

```bash
/fupan                  # 复盘今天的行情
/fupan 2026-06-11       # 复盘指定日期
```

这是 LLM 驱动的分析任务（Claude 按 SKILL.md 框架逐只判定产出报告），不是可独立运行的脚本。

## 文件结构

```
.claude/skills/fupan/          # 仓库内为唯一真相，~/.claude/skills/fupan 是指向这里的 symlink
├── SKILL.md                   # 主规范（Claude 读取，唯一权威）
├── 复盘心法-记忆补充.md         # 心法补充（jieli 也引用）
├── fupan_helper.py            # 辅助脚本（get_data 获取涨跌停/连板天梯）
├── scripts/                   # 数据源脚本（kpl_interval / plate_classifier / premium_ladder / platerotat 等）
├── archive/                   # 已退役脚本归档（勿在活跃流程 import）
└── README*.md                 # 说明文档
```

## 外部依赖（不随仓库携带）

- `~/.claude/mcp-servers/astock-data`：AkShare 实时行情，scripts 内多数脚本用它的 python 解释器跑。
- 实时数据失败时的降级顺序见 SKILL.md「数据获取方式」。

## 已移除功能

- **企业微信推送**（2026-06-12 下线）：webhook key 曾泄露进公开 git 历史，整条推送链已删除，不再恢复。
- **开盘啦实时打板 API**（2026-06 验签失效）：归档于 `archive/kailai_api.py`，涨停池改用 AkShare `stock_zt_pool_em`。
