# AStock Data 新增功能说明

## 概述

为 `/fupan` 的 akshare 数据引擎新增了4个核心功能，用于支持复盘框架V4.0和周期理论判断。

---

## 1. 个股连板历史分析 (`lianban_history`)

### 功能说明
获取个股的完整连板周期，识别首板日期、炸板记录、连板高度等关键信息。

### 使用方法
```bash
~/.claude/mcp-servers/astock-data/venv/bin/python3 ~/.claude/skills/fupan/scripts/astock_data.py \
  --action lianban_history \
  --code 603318 \
  --start 20260401 \
  --end 20260430 \
  --json
```

### 参数说明
- `--code`: 股票代码（必填）
- `--start`: 开始日期 YYYYMMDD（可选，默认最近30天）
- `--end`: 结束日期 YYYYMMDD（可选，默认今天）

### 返回数据结构
```json
{
  "code": "603318",
  "name": "水发燃气",
  "lianban_cycles": [
    {
      "cycle_id": 1,
      "start_date": "20260410",
      "end_date": "20260418",
      "max_boards": 8,
      "days": 9,
      "daily_records": [
        {
          "date": "20260410",
          "boards": 1,
          "time": "09:32",
          "turnover": 12.5,
          "open_times": 0,
          "sector": "燃气Ⅱ",
          "chg_pct": 10.01
        }
      ],
      "is_broken": false,
      "broken_dates": []
    }
  ],
  "summary": {
    "total_cycles": 2,
    "max_boards_ever": 8,
    "recent_zt_count": 10
  }
}
```

### 应用场景
- 判断当前龙头是首波还是二波
- 识别中途炸板记录
- 分析连板周期规律

---

## 2. 板块龙头时间线分析 (`sector_timeline`)

### 功能说明
分析板块内所有龙头的启动时间，自动识别首波龙头和补涨龙。

### 使用方法
```bash
~/.claude/mcp-servers/astock-data/venv/bin/python3 ~/.claude/skills/fupan/scripts/astock_data.py \
  --action sector_timeline \
  --sector "燃气Ⅱ" \
  --start 20260401 \
  --end 20260430 \
  --json
```

### 参数说明
- `--sector`: 板块名称（必填，如"燃气Ⅱ"、"电池"）
- `--start`: 开始日期 YYYYMMDD（可选，默认最近30天）
- `--end`: 结束日期 YYYYMMDD（可选，默认今天）

### 返回数据结构
```json
{
  "sector": "燃气Ⅱ",
  "leaders": [
    {
      "code": "603318",
      "name": "水发燃气",
      "first_board_date": "20260420",
      "last_board_date": "20260428",
      "max_boards": 8,
      "leader_type": "首波龙头",
      "is_active": true,
      "zt_dates": ["20260420", "20260421", ...]
    },
    {
      "code": "600123",
      "name": "某补涨龙",
      "first_board_date": "20260429",
      "last_board_date": "20260430",
      "max_boards": 2,
      "leader_type": "补涨龙",
      "is_active": true,
      "zt_dates": ["20260429", "20260430"]
    }
  ],
  "timeline": "首波龙头 水发燃气 于 20260420 启动，20260429 开板后出现 1 只补涨龙",
  "first_leader": {
    "code": "603318",
    "name": "水发燃气",
    "start": "20260420"
  }
}
```

### 龙头类型判断逻辑
- **首波龙头**: 板块内最早启动的龙头
- **补涨龙**: 首波龙头开板后1-3天内启动的同板块股票
- **二波龙**: 首波龙头回调10天以上后重新启动

### 应用场景
- 识别首波龙头和补涨龙关系
- 判断板块周期位置
- 决定操作策略（首波等二波，补涨龙立刻清仓）

---

## 3. 概念板块深度分析 (`concept_detail`)

### 功能说明
获取概念板块的成分股、龙头股、资金流向、板块强度等详细信息。

### 使用方法
```bash
~/.claude/mcp-servers/astock-data/venv/bin/python3 ~/.claude/skills/fupan/scripts/astock_data.py \
  --action concept_detail \
  --concept "人工智能" \
  --json
```

### 参数说明
- `--concept`: 概念名称（必填，如"人工智能"、"华为概念"）

### 返回数据结构
```json
{
  "concept": "人工智能",
  "stocks": [
    {
      "code": "300750",
      "name": "宁德时代",
      "chg_pct": 5.23,
      "price": 180.50,
      "turnover": 3.45
    }
  ],
  "leader": {
    "code": "300750",
    "name": "宁德时代",
    "chg_pct": 5.23,
    "amount": 50.5
  },
  "fund_flow": {
    "main_net": 12.5,
    "main_pct": 8.5,
    "super_large": 8.2,
    "large": 4.3
  },
  "strength": {
    "chg_pct": 3.5,
    "turnover": 5.2,
    "up_count": 45,
    "down_count": 12,
    "zt_count": 5
  }
}
```

### 应用场景
- 分析板块共振情况
- 找出板块龙头股
- 评估板块资金流向

---

## 4. 技术指标分析 (`technical`)

### 功能说明
计算个股的技术指标（均线、MACD、KDJ、量能），用于二波龙判断。

### 使用方法
```bash
~/.claude/mcp-servers/astock-data/venv/bin/python3 ~/.claude/skills/fupan/scripts/astock_data.py \
  --action technical \
  --code 603318 \
  --period 60 \
  --json
```

### 参数说明
- `--code`: 股票代码（必填）
- `--period`: 分析周期天数（可选，默认60天）

### 返回数据结构
```json
{
  "code": "603318",
  "name": "水发燃气",
  "ma": {
    "ma5": 10.5,
    "ma10": 10.2,
    "ma20": 9.8,
    "ma60": 9.5,
    "is_bullish": true
  },
  "macd": {
    "dif": 0.12,
    "dea": 0.08,
    "macd": 0.04,
    "signal": "金叉"
  },
  "kdj": {
    "k": 65,
    "d": 60,
    "j": 75,
    "signal": "超买"
  },
  "volume": {
    "recent_avg": 1000000,
    "today_ratio": 1.5,
    "signal": "放量"
  },
  "pattern": {
    "is_consolidation": true,
    "consolidation_days": 5,
    "pullback_pct": -15.5,
    "signal": "二波启动信号"
  }
}
```

### 二波启动信号判断
满足以下条件时，`pattern.signal` 返回 "二波启动信号"：
1. 缩量企稳 ≥3天（单日波动<3%）
2. 成交量放大（量比>1.5）
3. MACD金叉

满足缩量企稳≥5天时，返回 "企稳待突破"。

### 应用场景
- 判断二波龙启动时机
- 评估技术形态强弱
- 辅助买卖点决策

---

## 在 /fupan 中的应用

### 1. 周期定位分析（必须第一步）

```python
# 查询当前龙头完整连板周期
lianban_data = fetcher.get_stock_lianban_history(
    code="603318",
    start_date="20260401",
    end_date="20260430"
)

# 查询同板块时间线
timeline_data = fetcher.get_sector_timeline_analysis(
    sector_name="燃气Ⅱ",
    start_date="20260401",
    end_date="20260430"
)

# 判断龙头类型
if timeline_data["first_leader"]["code"] == "603318":
    leader_type = "首波龙头"
else:
    for leader in timeline_data["leaders"]:
        if leader["code"] == "603318":
            leader_type = leader["leader_type"]
            break
```

### 2. 板块共振分析

```python
# 获取概念板块详情
concept_data = fetcher.get_concept_detail("人工智能")

# 评估板块强度
if concept_data["strength"]["zt_count"] >= 5:
    print("板块共振强")
```

### 3. 二波龙监控

```python
# 技术指标分析
tech_data = fetcher.get_technical_indicators(code="603318", period=60)

# 判断二波启动信号
if tech_data["pattern"]["signal"] == "二波启动信号":
    print("二波龙启动，重新加仓至30-50%")
elif tech_data["pattern"]["signal"] == "企稳待突破":
    print("继续观察，保持20%仓位")
```

---

## 注意事项

1. **请求频率控制**: 所有接口都有反爬虫保护，自动控制请求间隔（3-7秒）
2. **缓存机制**: 当日数据会自动缓存，避免重复请求
3. **限流保护**: 
   - 每日最大请求100次
   - 连续失败5次会进入1小时冷却期
4. **数据准确性**: 
   - 涨停池数据可能存在延迟
   - 周末和节假日无数据
   - 建议在交易日收盘后使用

---

## 更新日志

### 2026-04-30
- ✅ 新增个股连板历史分析功能
- ✅ 新增板块龙头时间线分析功能
- ✅ 新增概念板块深度分析功能
- ✅ 新增技术指标分析功能
- ✅ 修复 get_stock_info 中均线计算bug

---

## 反馈与建议

如有问题或建议，请在 `/fupan` skill 中反馈。
