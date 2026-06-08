# A股数据获取引擎 - 反爬虫保护说明

## 🛡️ 已实现的保护机制

### 1. 请求频率控制
- **随机间隔**: 3-7秒（原2-5秒）
- **额外抖动**: 每次请求额外随机0-1秒
- **自动限流**: 每次请求前自动检查并等待

### 2. 智能重试 + 指数退避
- **最大重试**: 3次
- **触发限流时**: 8秒 → 16秒 → 32秒（指数退避 + 随机0-5秒）
- **普通错误**: 8秒 + 随机0-3秒
- **错误识别**: 自动识别429/503/限流/频繁/timeout/blocked等关键词

### 3. User-Agent 轮换
- **6种常见浏览器UA**: Chrome/Firefox/Safari/Edge，覆盖Mac/Windows/Linux
- **完整请求头**: Accept、Accept-Language、Accept-Encoding等
- **每次请求随机**: 避免被识别为爬虫

### 4. 请求统计与限流
- **每日上限**: 100次请求（可配置）
- **连续失败保护**: 连续失败5次自动进入冷却期
- **冷却期**: 1小时（3600秒）
- **统计持久化**: 保存到 `.cache/request_stats.json`

### 5. 本地缓存
- **按日期缓存**: 当日数据有效，次日自动失效
- **缓存目录**: `~/.claude/skills/fupan/.cache/`
- **避免重复请求**: 相同查询直接返回缓存

### 6. 错误降级
- **单源失败不影响整体**: 某个数据源失败返回None，不中断流程
- **全量复盘容错**: 7个模块独立容错

## 📊 使用方法

### 查看当前统计
```bash
python3 astock_data.py --action stats
```

输出示例：
```json
{
  "date": "2026-04-30",
  "daily_requests": 15,
  "consecutive_failures": 0,
  "last_failure_time": null,
  "cooldown_until": null
}

📊 今日请求: 15/100
⚠️ 连续失败: 0/5
✅ 无冷却限制
```

### 重置统计数据
```bash
python3 astock_data.py --action reset_stats
```

### 正常使用
```bash
# 全量复盘
python3 astock_data.py --action full_review --date 20260429

# 涨跌停统计
python3 astock_data.py --action zt_dt_summary --date 20260429

# 连板天梯
python3 astock_data.py --action lianban_ladder --date 20260429
```

## ⚠️ 触发保护机制时的表现

### 1. 达到每日上限
```
⛔ 今日请求已达上限 (100 次)，请明天再试
```

### 2. 连续失败进入冷却期
```
⛔ 连续失败 5 次，进入冷却期至 15:30:00
⛔ 触发保护机制：连续失败过多，请等待 45.2 分钟后再试
```

### 3. 触发限流重试
```
⚠️ 触发限流(stock_zt_pool_em), 等待 16.3s 后重试 (2/3)
```

## 🔧 配置参数

在 `astock_data.py` 顶部可调整：

```python
REQUEST_INTERVAL_MIN = 3.0   # 最小请求间隔(秒)
REQUEST_INTERVAL_MAX = 7.0   # 最大请求间隔(秒)
MAX_RETRIES = 3              # 最大重试次数
RETRY_BASE_DELAY = 8         # 重试基础延迟(秒)
MAX_DAILY_REQUESTS = 100     # 每日最大请求次数
MAX_CONSECUTIVE_FAILURES = 5 # 最大连续失败次数
COOLDOWN_PERIOD = 3600       # 冷却期(秒) - 1小时
```

## 💡 使用建议

### 1. 避免高峰时段
- **交易时段** (9:30-15:00): 数据源服务器压力大，容易触发限流
- **推荐时段**: 收盘后 (15:30-23:00) 或早盘前 (7:00-9:00)

### 2. 优先使用缓存
- 同一天的数据会自动缓存
- 重复查询不会发起新请求
- 使用 `--no-cache` 参数可禁用缓存（不推荐）

### 3. 避免并发运行
- 不要同时运行多个复盘任务
- 不要在多个终端同时调用

### 4. 监控统计数据
- 定期运行 `--action stats` 查看使用情况
- 接近上限时减少使用频率

### 5. 合理使用全量复盘
- 全量复盘会发起 10+ 次请求
- 每天建议不超过 5-8 次全量复盘
- 单项查询（涨跌停、连板天梯等）更节省配额

## 🚨 紧急情况处理

### IP被封了怎么办？
1. **立即停止所有请求**
2. **等待至少2小时**
3. **运行 `--action reset_stats` 重置统计**
4. **降低请求频率**: 将 `REQUEST_INTERVAL_MIN` 改为 5，`MAX` 改为 10
5. **减少每日上限**: 将 `MAX_DAILY_REQUESTS` 改为 50

### 连续失败怎么办？
1. **检查网络连接**
2. **确认数据源是否正常**: 访问 https://quote.eastmoney.com/
3. **等待冷却期结束**（1小时）
4. **如果持续失败**: 可能是akshare版本问题，运行 `pip3 install --upgrade akshare`

### 如何完全重置？
```bash
# 删除所有缓存和统计
rm -rf ~/.claude/skills/fupan/.cache/
```

## 📈 性能优化建议

### 1. 分时段使用
- **盘后复盘**: 15:30-16:00（数据最新）
- **早盘预习**: 8:00-9:00（查看昨日数据）
- **避免盘中**: 9:30-15:00（数据源压力大）

### 2. 按需查询
```bash
# 只需要涨停数据
python3 astock_data.py --action zt_dt_summary

# 只需要连板天梯
python3 astock_data.py --action lianban_ladder

# 只需要龙虎榜
python3 astock_data.py --action lhb
```

### 3. 利用缓存
- 同一天内重复查询会直接返回缓存
- 缓存在次日0点自动失效
- 缓存文件位置: `~/.claude/skills/fupan/.cache/`

## 🔍 日志说明

### 正常请求
```
📡 [1] 调用 stock_zt_pool_em ...
  ✅ 成功: 85 条记录
```

### 触发限流
```
📡 [2] 调用 stock_zt_pool_dtgc_em ...
  ⚠️ 触发限流(stock_zt_pool_dtgc_em), 等待 8.3s 后重试 (1/3)
```

### 请求失败
```
📡 [3] 调用 stock_zt_pool_zbgc_em ...
  ❌ 异常: HTTPError 503, 8.5s后重试 (1/3)
  ❌ stock_zt_pool_zbgc_em 最终失败: HTTPError 503
```

### 缓存命中
```
💾 缓存命中: 2026-04-30_a3f2...
```

## 📞 技术支持

如果遇到问题：
1. 先查看 `--action stats` 统计信息
2. 检查日志中的错误信息
3. 尝试 `--action reset_stats` 重置
4. 如果持续失败，可能是数据源问题，等待一段时间再试

---

**最后更新**: 2026-04-30  
**版本**: v2.0 - 增强反爬虫保护
