# archive/ — 废弃脚本归档

归档日期：2026-06-10

## 归档原因

| 文件 | 原因 |
|------|------|
| `kailai_api.py` | 开盘啦API 2026-06 实测已死：HTTP 200 但 `list` 恒空、历史日期参数被服务端忽略。涨停板数据已全量迁移至 AkShare `ak.stock_zt_pool_em(date=YYYYMMDD)`，概念题材归类由 plate_classifier（选股通）替代。 |
| `complete_review_helper.py` | V4.0 时代遗留，SKILL.md 已不引用，评分口径（旧框架）已被 V5.x 100分制替代。 |
| `integrated_review.py` | V4.0 整合脚本，SKILL.md 已不引用；其依赖的 `multi_dimension_review.py` 仍在上级目录维护（脚本内有 `sys.path.insert` 绝对路径，如需考古运行仍可工作）。 |

## 注意

- 请勿在 /fupan、/jieli、/jingjia 等活跃流程中 import 本目录任何脚本。
- 涨停板数据唯一来源：AkShare `stock_zt_pool_em`；盘口异动：`stock_changes_em`；强势股池：`stock_zt_pool_strong_em`。
