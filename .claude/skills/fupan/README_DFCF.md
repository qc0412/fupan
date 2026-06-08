# 东方财富妙想数据接口使用说明

## 概述

`dfcf_data.py` 是一个封装了东方财富妙想 API 的 Python 模块，用于 `/fupan` skill 获取实时金融数据。

## 功能

### 1. 获取指数数据

```python
from dfcf_data import DFCFData

client = DFCFData()

# 获取今日指数数据
index_data = client.get_index_data()
# 返回：
# {
#     'sz_index': {'close': 4098.62, 'change_pct': 0.49},
#     'cyb_index': {'close': 3676.44, 'change_pct': 2.23}
# }

# 获取指定日期的指数数据
index_data = client.get_index_data(date="2026-04-28")
```

### 2. 获取股票实时行情

```python
# 获取股票实时数据
stock_data = client.get_stock_realtime("东方财富")
# 返回：
# {
#     'name': '东方财富',
#     'code': '300059',
#     'price': 20.13,
#     'change_pct': -0.15,
#     'turnover': 0.88,
#     'volume': 116984344.0
# }
```

### 3. 获取股票历史数据

```python
# 获取股票近30天历史数据
history = client.get_stock_history("300059", "东方财富", days=30)
# 返回：
# [
#     {
#         'date': '2026-04-29',
#         'close': 20.13,
#         'change_pct': -0.15,
#         'turnover': 0.88,
#         'volume': 117010644.0
#     },
#     ...
# ]
```

### 4. 获取板块成分股

```python
# 获取板块成分股
stocks = client.get_sector_stocks("新能源", date="2026-04-29")
# 返回：
# [
#     {
#         'name': '宁德时代',
#         'code': '300750',
#         'change_pct': 2.5
#     },
#     ...
# ]
```

## 数据字段说明

### 指数数据字段
- `close`: 收盘价
- `change_pct`: 涨跌幅（%）

### 股票数据字段
- `name`: 股票名称
- `code`: 股票代码
- `price`: 最新价/收盘价
- `change_pct`: 涨跌幅（%）
- `turnover`: 换手率（%）
- `volume`: 成交量（手）
- `date`: 日期时间

## 环境要求

- Python 3.7+
- 依赖包：pandas, requests, openpyxl
- 环境变量：`MX_APIKEY`（东方财富妙想 API Key）

## 配置

API Key 已配置在 `~/.claude/settings.json` 中：

```json
{
  "env": {
    "MX_APIKEY": "mkt_Bs6sLS9XlMJ021JEXSg-mOIKAD4gsSq9DyppuWyPeN8"
  }
}
```

## 输出文件

查询结果会保存在 `~/.claude/skills/fupan/mx_data_output/` 目录：
- `mx_data_*.xlsx` - Excel 数据文件
- `mx_data_*_description.txt` - 查询描述
- `mx_data_*_raw.json` - 原始 JSON 数据

## 在 /fupan skill 中使用

在 `/fupan` skill 的 SKILL.md 中，可以这样使用：

```bash
# 获取指数数据
~/.claude/mcp-servers/astock-data/venv/bin/python3 << 'EOF'
import sys
sys.path.insert(0, os.path.expanduser('~/.claude/skills/fupan'))
from dfcf_data import DFCFData
import json

client = DFCFData()

# 获取今日指数
index_data = client.get_index_data()
print(json.dumps(index_data, ensure_ascii=False, indent=2))
EOF
```

## 注意事项

1. **API 调用限制**：东方财富妙想 API 有每日调用次数限制
2. **数据延迟**：实时数据可能有几分钟延迟
3. **查询语法**：使用自然语言查询，如"东方财富最新价"、"上证指数收盘价"
4. **数据范围**：避免查询过大范围的历史数据，可能导致超时

## 故障排查

### 问题：ModuleNotFoundError: No module named 'pandas'
**解决**：在 astock-data 虚拟环境中安装依赖
```bash
~/.claude/mcp-servers/astock-data/venv/bin/pip install pandas requests openpyxl
```

### 问题：MX_APIKEY 环境变量未设置
**解决**：检查 `~/.claude/settings.json` 中是否配置了 `MX_APIKEY`

### 问题：查询返回空数据
**解决**：
1. 检查查询语法是否正确
2. 检查 API Key 是否有效
3. 查看 `mx_data_output` 目录中的错误日志
