# A股短线龙头复盘助手 V3.0

## 📋 功能说明

这个 skill 帮助你进行 A股短线龙头复盘，基于"连板+波段双轮驱动"交易体系。

### 核心功能
1. ✅ 自动获取 A股实时数据（通过 AkShare）
2. ✅ 计算市场情绪温度（量化打分）
3. ✅ 识别龙头股票并打分（10分制）
4. ✅ 区分龙头类型（妖股/趋势龙头/先锋龙）
5. ✅ 自动推送复盘报告到企业微信

---

## 🚀 使用方式

### 基本用法
```bash
/fupan                    # 复盘今天的行情
/fupan 2026-04-28        # 复盘指定日期
```

### 工作流程
1. 自动调用 `fupan_helper.py` 获取 A股数据
2. 分析市场情绪、龙头股票、板块共振
3. 生成完整复盘报告
4. 自动推送摘要到企业微信

---

## 📁 文件结构

```
~/.claude/skills/fupan/
├── SKILL.md              # Skill 主文件（Claude 读取）
├── fupan_helper.py       # 辅助脚本（获取数据+推送）
└── README.md             # 使用说明（本文件）
```

---

## 🔧 辅助脚本使用

### 1. 获取市场数据
```bash
~/.claude/mcp-servers/astock-data/venv/bin/python3 \
  ~/.claude/skills/fupan/fupan_helper.py get_data --date 2026-04-28
```

返回 JSON 格式：
```json
{
  "success": true,
  "date": "2026-04-28",
  "market": {
    "index": "上证指数",
    "change": "+0.16",
    "limit_up": 43,
    "limit_down": 0,
    "failed_rate": 34
  },
  "all_stocks": [...],
  "history": [...]
}
```

### 2. 推送到企业微信
```bash
~/.claude/mcp-servers/astock-data/venv/bin/python3 \
  ~/.claude/skills/fupan/fupan_helper.py push --message '{
    "date": "2026-04-28",
    "emotion_score": 35,
    "emotion_status": "冰点期",
    "leader_name": "维科技术",
    "leader_boards": 3,
    "leader_time": "09:40",
    "leader_sector": "电池",
    "leader_score": "5.5",
    "position_limit": "0-10%",
    "suggestion": "空仓观望"
  }'
```

返回：
```json
{
  "success": true,
  "message": "推送成功"
}
```

---

## 📊 复盘报告内容

### 1. 市场概况
- 情绪温度计算（量化打分）
- 市场状态（高温/常温/冰点）
- 仓位上限建议

### 2. 龙头追踪
- 当前龙头股票
- 连板高度、涨停时间
- 龙头分类（妖股/趋势龙头/先锋龙）
- 跟风股数量

### 3. 龙头候选打分表
- V3.0 打分体系（10分制）
- 买入/观察/不买建议

### 4. 二波龙监控池
- 趋势龙头回调监控
- 二波启动信号识别

### 5. 明日计划
- 仓位计划
- 关注标的
- 风险提示

### 6. 今日复盘总结
- 做对的事
- 做错的事
- 今日感悟

---

## 🎯 V3.0 核心理念

### 连板+波段双轮驱动
- **首波连板期**：重仓30-50%，吃连板爆发力
- **连板结束日**：减仓至20%（不清仓！），加入监控池
- **回调期**：保持20%仓位，观察题材热度
- **二波连板期**：重新加仓至30-50%，再吃连板

### 龙头分类决定操作
1. **妖股**：连板结束就跑，不等二波
2. **趋势龙头**：连板结束减至20%，等二波连板
3. **先锋龙**：观察跟风，决定是否切换到正宗龙头

### 情绪温度决定仓位
- 🔥 高温期（≥80分）：激进打板，单票30-50%
- 🌡️ 常温期（40-79分）：精选龙头，单票10-20%
- ❄️ 冰点期（<40分）：空仓观望

---

## 🔗 依赖项

### 1. AkShare 数据源
位置：`~/.claude/mcp-servers/astock-data/`

需要安装：
```bash
pip install akshare requests
```

### 2. 企业微信 Webhook
已配置 Webhook 地址：
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=7a61a49c-2fc9-4d57-bbbb-7e09bb217947
```

---

## 🐛 故障排查

### 问题1：无法获取数据
**原因**：AkShare 模块未安装或网络问题

**解决**：
```bash
cd ~/.claude/mcp-servers/astock-data
source venv/bin/activate
pip install akshare
```

### 问题2：企业微信推送失败
**原因**：Webhook key 失效或网络问题

**解决**：
1. 检查 Webhook 地址是否正确
2. 测试网络连接：`curl https://qyapi.weixin.qq.com`
3. 查看错误信息：`errmsg` 字段

### 问题3：数据不准确
**原因**：AkShare 数据源延迟或接口变更

**解决**：
1. 等待几分钟后重试
2. 检查 AkShare 版本：`pip show akshare`
3. 更新 AkShare：`pip install --upgrade akshare`

---

## 📝 更新日志

### V3.0 (2026-04-28)
- ✅ 添加自动获取 A股数据功能
- ✅ 添加企业微信推送功能
- ✅ 创建 `fupan_helper.py` 辅助脚本
- ✅ 优化数据获取流程（Python 脚本 → 本地文件 → 手动输入）

### V2.1
- 基础复盘功能
- 手动输入数据

---

## 💡 使用技巧

1. **每日复盘时间**：建议在收盘后（15:30-16:00）进行复盘
2. **配合监控池**：将趋势龙头加入监控池，不要错过二波
3. **严格执行纪律**：情绪温度<40分时，坚决空仓观望
4. **关注先锋龙**：冰点期出现的先锋龙，可能是大行情信号

---

## 📞 联系方式

如有问题或建议，请联系：
- 企业微信群：A股短线交流群
- 或通过 Claude Code 反馈
