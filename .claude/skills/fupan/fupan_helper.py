#!/usr/bin/env python3
"""
复盘助手辅助脚本
用于获取A股数据

（企业微信推送链已于 2026-06-12 整体移除：webhook key 曾泄露进公开 git 历史，
用户决定直接废弃推送功能而非轮换 key。）
"""

import os
import sys
import json
from datetime import datetime


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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='复盘助手辅助脚本')
    parser.add_argument('action', choices=['get_data'],
                       help='操作类型：get_data=获取数据')
    parser.add_argument('--date', help='日期 (YYYY-MM-DD)')

    args = parser.parse_args()

    if args.action == 'get_data':
        # 获取市场数据
        result = get_market_data(args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2))
