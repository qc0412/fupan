#!/usr/bin/env python3
"""
复盘助手辅助脚本
用于获取A股数据和推送企业微信

推送链 V5.2（2026-06-10 重写）：只推今日事实。
禁止字段：明日预测 / 仓位建议 / 操作建议 / 监控池（违反「复盘只看今天」硬规则）。
webhook key 来源：环境变量 WECOM_WEBHOOK_KEY，或 ~/.config/fupan/wecom_key 文件，明文勿入代码/文档。
"""

import os
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


def get_webhook_key():
    """获取企业微信 webhook key：env WECOM_WEBHOOK_KEY → ~/.config/fupan/wecom_key 文件 → None"""
    key = os.environ.get("WECOM_WEBHOOK_KEY")
    if key and key.strip():
        return key.strip()

    key_file = os.path.expanduser("~/.config/fupan/wecom_key")
    try:
        with open(key_file, 'r', encoding='utf-8') as f:
            key = f.read().strip()
        if key:
            return key
    except OSError:
        pass

    return None


def send_to_wecom(content):
    """推送到企业微信（key 未配置时打印警告并跳过推送）"""
    key = get_webhook_key()
    if not key:
        print("⚠️ 未配置企业微信 webhook key（环境变量 WECOM_WEBHOOK_KEY 或 ~/.config/fupan/wecom_key），跳过推送")
        return {'success': False, 'skipped': True, 'error': '未配置 webhook key，已跳过推送'}

    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + key

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


def classify_emotion(score):
    """情绪温度档位（V5口径，边界以 SKILL.md「第一步：计算情绪温度」分级为准）：
    >60 过热 / 40-60 高温 / 20-40 回暖 / <20 冰点
    """
    try:
        score = float(score)
    except (TypeError, ValueError):
        return ("未知", "🌡️", "comment")
    if score > 60:
        return ("过热", "🌋", "warning")
    if score >= 40:
        return ("高温", "🔥", "info")
    if score >= 20:
        return ("回暖", "🌡️", "comment")
    return ("冰点", "❄️", "warning")


def format_wecom_message(report_data):
    """格式化企业微信消息 — V5.2 只推今日事实。

    字段（全部为今日事实，缺失字段自动省略）：
    - date: 日期
    - emotion_score: 情绪温度分（档位自动计算）
    - limit_up_count / limit_down_count / failed_rate: 涨停家数 / 跌停家数 / 炸板率%
    - max_boards / space_board_name: 最高板高度 / 空间板名称
    - first_board_promotion_rate / lianban_promotion_rate: 首板晋级率% / 连板晋级率%
    - top_sectors: 主线板块Top3，[{"name": 板块名, "limit_up_count": 涨停家数}, ...]
    - leaders: 龙头表（最多5行），[{"name": 名称, "boards": 连板数, "sector": 板块}, ...]
    """
    date = report_data.get('date', datetime.now().strftime('%Y-%m-%d'))
    lines = [f"# 📊 A股复盘 {date}（今日事实）", ""]

    # 情绪温度
    emotion_score = report_data.get('emotion_score')
    if emotion_score is not None:
        level, emoji, color = classify_emotion(emotion_score)
        lines.append(f"**情绪温度：<font color=\"{color}\">{emotion_score}分</font> {emoji}{level}**")
        lines.append("")

    # 涨停/跌停/炸板率
    facts = []
    if report_data.get('limit_up_count') is not None:
        facts.append(f"涨停 {report_data['limit_up_count']} 家")
    if report_data.get('limit_down_count') is not None:
        facts.append(f"跌停 {report_data['limit_down_count']} 家")
    if report_data.get('failed_rate') is not None:
        facts.append(f"炸板率 {report_data['failed_rate']}%")
    if facts:
        lines.append("- " + " / ".join(facts))

    # 最高板 + 空间板名称
    if report_data.get('max_boards') is not None:
        space_name = report_data.get('space_board_name', '')
        suffix = f"（{space_name}）" if space_name else ""
        lines.append(f"- 最高板：{report_data['max_boards']}板{suffix}")

    # 晋级率
    rates = []
    if report_data.get('first_board_promotion_rate') is not None:
        rates.append(f"首板晋级率 {report_data['first_board_promotion_rate']}%")
    if report_data.get('lianban_promotion_rate') is not None:
        rates.append(f"连板晋级率 {report_data['lianban_promotion_rate']}%")
    if rates:
        lines.append("- " + " / ".join(rates))

    # 主线板块 Top3
    top_sectors = report_data.get('top_sectors') or []
    if top_sectors:
        lines.append("")
        lines.append("**主线板块 Top3**")
        for i, sector in enumerate(top_sectors[:3], 1):
            lines.append(f"{i}. {sector.get('name', '?')}（涨停{sector.get('limit_up_count', '?')}家）")

    # 龙头表（最多5行）
    leaders = report_data.get('leaders') or []
    if leaders:
        lines.append("")
        lines.append("**龙头表**")
        for leader in leaders[:5]:
            lines.append(f"- {leader.get('name', '?')}：{leader.get('boards', '?')}连板（{leader.get('sector', '?')}）")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='复盘助手辅助脚本')
    parser.add_argument('action', choices=['get_data', 'push'],
                       help='操作类型：get_data=获取数据, push=推送企业微信（V5.2只推今日事实）')
    parser.add_argument('--date', help='日期 (YYYY-MM-DD)')
    parser.add_argument('--message', help='推送消息内容（JSON格式，字段见 format_wecom_message 注释）')

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
