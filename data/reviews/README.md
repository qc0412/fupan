# 复盘报告目录

网站「复盘」Tab 的数据源。每份报告是一个 markdown 文件，命名约定：

```
<YYYY-MM-DD>_<type>.md
```

- `type` 取值（白名单，见 `app.py` 的 `REVIEW_TYPES`）：
  - `fupan` —— `/fupan` 日复盘
  - `jieli` —— `/jieli` 连板接力盘后分析
- 例：`2026-06-06_fupan.md`、`2026-06-06_jieli.md`

## 怎么发布一份复盘

1. 在 Claude Code 里跑 `/fupan` 或 `/jieli`，让它把报告写成 markdown 存到本目录、按上面命名。
2. 提交到 `dev` 分支。
3. 在云服务器 `git pull`，让 Flask（`fupan.service`）能读到新文件——报告是请求时读盘的，**无需重启**；前端没改时也**无需重新构建**。

## 接口

- `GET /api/reviews` —— 列出有哪些日期/类型，按日期倒序。
- `GET /api/review/<date>/<type>` —— 返回该报告的 markdown 原文。

> 不匹配 `<日期>_<type>.md` 的文件（如本 README）会被接口忽略。
