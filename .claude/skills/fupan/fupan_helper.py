#!/usr/bin/env python3
import os
"""
复盘助手辅助脚本
用于获取A股数据和推送企业微信
"""

import sys
import json
import requests
from datetime import datetime, timedelta


def get_market_data(date_str=None):
    """获取市场数据 - 使用 akshare"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')

    try:
        # 使用 akshare 获取数据
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
        from astock_data import AStockDataFetcher

        fetcher = AStockDataFetcher(enable_cache=True)
        date_param = date_str.replace('-', '')

        # 获取涨跌停数据
        zt_data = fetcher.get_zt_dt_summary(date_param)

        # 获取连板天梯
        lianban_data = fetcher.get_lianban_ladder(date_param)

        return {
            'success': True,
            'date': date_str,
            'zt_data': zt_data,
            'lianban_data': lianban_data
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def send_to_wecom(content):
    """推送到企业微信"""
    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=7a61a49c-2fc9-4d57-bbbb-7e09bb217947"

    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    try:
        response = requests.post(webhook_url, json=data, timeout=10)
        result = response.json()

        if result.get('errcode') == 0:
            return {'success': True, 'message': '推送成功'}
        else:
            return {
                'success': False,
                'error': f"推送失败: {result.get('errmsg', '未知错误')}"
            }
    except Exception as e:
        return {
            'success': False,
            'error': f"推送异常: {str(e)}"
        }


def format_wecom_message(report_data):
    """格式化企业微信消息 - 完整版"""

    # 根据情绪温度选择颜色
    emotion_score = report_data.get('emotion_score', 0)
    if emotion_score >= 80:
        color = "info"  # 蓝色
        emoji = "🔥"
    elif emotion_score >= 40:
        color = "comment"  # 灰色
        emoji = "🌡️"
    else:
        color = "warning"  # 橙色
        emoji = "❄️"

    # 构建完整报告
    content = f"""# 📊 A股复盘 {report_data['date']}

## 📈 市场概况

**情绪温度：<font color=\"{color}\">{emotion_score}分</font> {emoji}{report_data['emotion_status']}**

- 龙头高度得分：{report_data.get('leader_height_score', 0)}分（当前龙头：{report_data.get('max_boards', 0)}板）
- 涨停家数得分：{report_data.get('limit_up_score', 0)}分（今日{report_data.get('limit_up_count', 0)}家，近5日中位数{report_data.get('median_limit_up', 0)}家）
- 炸板率得分：{report_data.get('failed_rate_score', 0)}分（今日炸板率{report_data.get('failed_rate', 0)}%）
- 指数走势得分：{report_data.get('index_score', 0)}分（上证{report_data.get('index_change', '0')}%）

**🎯 仓位上限：{report_data['position_limit']}**
**⚠️ 强制空仓信号：{report_data.get('force_empty', '否')}**

---

## 🏆 当前龙头

**{report_data['leader_name']}** ({report_data['leader_code']})
- 连板高度：{report_data['leader_boards']}连板（今日第{report_data['leader_boards']}板）
- 涨停时间：{report_data['leader_time']}
- 所属板块：{report_data['leader_sector']}
- 换手率：{report_data.get('leader_turnover', 0)}%
- 封板强度：{report_data.get('leader_seal', '强')}
- 龙头分类：{report_data.get('leader_type', '未知')}

**跟风股数量：{report_data.get('follower_count', 0)}只**

{report_data.get('top_followers', '')}

---

## 📊 龙头候选打分

{report_data.get('candidates_table', '暂无候选')}

---

## 💡 操作建议

**明日仓位计划：{report_data['position_limit']}**

<font color=\"{color}\">**{report_data['suggestion']}**</font>

{report_data.get('operation_reason', '')}

---

## ⚠️ 风险提示

{report_data.get('risk_tips', '- 无特殊风险')}

---

## 📝 今日感悟

{report_data.get('summary', '市场情绪观察中...')}"""

    return content


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='复盘助手辅助脚本')
    parser.add_argument('action', choices=['get_data', 'push'],
                       help='操作类型：get_data=获取数据, push=推送企业微信')
    parser.add_argument('--date', help='日期 (YYYY-MM-DD)')
    parser.add_argument('--message', help='推送消息内容（JSON格式）')

    args = parser.parse_args()

    if args.action == 'get_data':
        # 获取市场数据
        result = get_market_data(args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == 'push':
        # 推送到企业微信
        if args.message:
            msg_data = json.loads(args.message)
            content = format_wecom_message(msg_data)
            result = send_to_wecom(content)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({
                'success': False,
                'error': '缺少 --message 参数'
            }, ensure_ascii=False, indent=2))
