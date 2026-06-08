#!/usr/bin/env python3
"""
A股实时数据获取脚本
优先从东方财富网API获取，失败则回退到本地MCP服务器
"""

import requests
import json
from datetime import datetime
import sys
import os

# 添加MCP服务器路径
sys.path.insert(0, os.path.expanduser('~/.claude/mcp-servers/astock-data'))

def get_index_data_from_web():
    """从东方财富网获取指数数据"""
    url = 'http://push2.eastmoney.com/api/qt/ulist.np/get'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'http://quote.eastmoney.com/'
    }
    params = {
        'fltt': '2',
        'invt': '2',
        'fields': 'f1,f2,f3,f4,f12,f13,f14',
        'secids': '1.000001,0.399001,0.399006'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        data = response.json()
        result = {}

        if 'data' in data and 'diff' in data['data']:
            for index in data['data']['diff']:
                code = index.get('f12', '')
                change_pct = index.get('f3', 0) / 100

                if code == '000001':
                    result['sh_index'] = change_pct
                elif code == '399006':
                    result['cy_index'] = change_pct

        return result if result else None
    except Exception as e:
        print(f'[Web] 获取指数数据失败: {e}', file=sys.stderr)
        return None

def get_limit_up_from_mcp(date):
    """从本地MCP服务器获取涨停板数据"""
    try:
        from server import get_market_overview, get_limit_up_stocks

        market = get_market_overview(date)
        stocks = get_limit_up_stocks(date)

        return {
            'limit_up_count': market.get('limit_up', 0),
            'failed_rate': market.get('failed_rate', 0),
            'stocks': stocks
        }
    except Exception as e:
        print(f'[MCP] 获取涨停板数据失败: {e}', file=sys.stderr)
        return None

def main():
    """主函数"""
    date = datetime.now().strftime('%Y-%m-%d')

    print(f'正在获取 {date} 的A股市场数据...\n', file=sys.stderr)

    # 1. 优先从网络获取指数数据
    index_data = get_index_data_from_web()

    if index_data:
        print('[Web] 成功获取指数数据', file=sys.stderr)
        sh_index_change = index_data.get('sh_index', 0)
        cy_index_change = index_data.get('cy_index', 0)
    else:
        print('[Web] 指数数据获取失败，使用默认值', file=sys.stderr)
        sh_index_change = 0
        cy_index_change = 0

    # 2. 从MCP服务器获取涨停板数据
    limit_up_data = get_limit_up_from_mcp(date)

    if limit_up_data:
        print('[MCP] 成功获取涨停板数据', file=sys.stderr)
        limit_up_count = limit_up_data['limit_up_count']
        failed_rate = limit_up_data['failed_rate']
        stocks = limit_up_data['stocks']
    else:
        print('[MCP] 涨停板数据获取失败', file=sys.stderr)
        limit_up_count = 0
        failed_rate = 0
        stocks = []

    # 3. 输出结果
    result = {
        'date': date,
        'market': {
            'sh_index_change': sh_index_change,
            'cy_index_change': cy_index_change,
            'limit_up_count': limit_up_count,
            'failed_rate': failed_rate,
        },
        'limit_up_stocks': stocks
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 输出摘要
    print(f'\n=== 数据摘要 ===', file=sys.stderr)
    print(f'日期: {date}', file=sys.stderr)
    print(f'上证指数: {sh_index_change:.2%}', file=sys.stderr)
    print(f'创业板指: {cy_index_change:.2%}', file=sys.stderr)
    print(f'涨停家数: {limit_up_count}', file=sys.stderr)
    print(f'炸板率: {failed_rate}%', file=sys.stderr)

if __name__ == '__main__':
    main()
