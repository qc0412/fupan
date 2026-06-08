#!/usr/bin/env python3
import os
"""
全市场涨停股扫描工具
用于复盘时不遗漏任何优质标的
"""

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from astock_data import AStockDataFetcher
import json


def scan_all_limit_up_stocks(date_str="20260429"):
    """
    全市场涨停股扫描

    返回：
    1. 成交额TOP10
    2. 连板天梯（按高度分层）
    3. 板块强度排行
    4. 早盘涨停+封板稳定的首板股
    """
    fetcher = AStockDataFetcher(enable_cache=True)

    # 获取涨停池数据
    zt_data = fetcher.get_zt_dt_summary(date_str)
    all_stocks = zt_data.get('_zt_detail', [])

    # 获取连板天梯
    lianban_data = fetcher.get_lianban_ladder(date_str)
    ladder = lianban_data.get('ladder', {})

    result = {
        'date': date_str,
        'total_count': len(all_stocks),
        'top_by_amount': [],
        'ladder_summary': {},
        'sector_summary': {},
        'quality_first_boards': []
    }

    # 1. 按成交额排序TOP10
    sorted_by_amount = sorted(
        all_stocks,
        key=lambda x: x.get('成交额', 0),
        reverse=True
    )[:10]

    for i, stock in enumerate(sorted_by_amount):
        result['top_by_amount'].append({
            'rank': i + 1,
            'name': stock.get('名称'),
            'code': stock.get('代码'),
            'boards': stock.get('连板数', 1),
            'amount': round(stock.get('成交额', 0) / 1e8, 2),
            'turnover': round(stock.get('换手率', 0), 2),
            'first_seal_time': stock.get('首次封板时间', ''),
            'zab_count': stock.get('炸板次数', 0),
            'sector': stock.get('所属行业', '')
        })

    # 2. 连板天梯汇总
    for height_key, stocks in ladder.items():
        height = int(height_key.replace('板', ''))
        result['ladder_summary'][height_key] = {
            'count': len(stocks),
            'stocks': [
                {
                    'name': s.get('name'),
                    'code': s.get('code'),
                    'first_seal_time': s.get('first_seal_time'),
                    'zab_count': s.get('zab_count'),
                    'turnover': round(s.get('turnover', 0), 2),
                    'board_pattern': s.get('board_pattern'),
                    'sector': s.get('sector')
                }
                for s in stocks
            ]
        }

    # 3. 板块强度统计
    sector_stats = {}
    for stock in all_stocks:
        sector = stock.get('所属行业', '未知')
        if sector not in sector_stats:
            sector_stats[sector] = {
                'count': 0,
                'stocks': [],
                'total_amount': 0
            }
        sector_stats[sector]['count'] += 1
        sector_stats[sector]['stocks'].append(stock.get('名称'))
        sector_stats[sector]['total_amount'] += stock.get('成交额', 0)

    # 按涨停数量排序
    sorted_sectors = sorted(
        sector_stats.items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )[:10]

    for sector, data in sorted_sectors:
        result['sector_summary'][sector] = {
            'count': data['count'],
            'total_amount': round(data['total_amount'] / 1e8, 2),
            'stocks': data['stocks'][:5]  # 只显示前5只
        }

    # 4. 优质首板（早盘涨停+封板稳定）
    quality_first_boards = []
    for stock in all_stocks:
        if stock.get('连板数', 1) == 1:  # 首板
            first_seal_time = stock.get('首次封板时间', '')
            zab_count = stock.get('炸板次数', 0)

            # 早盘涨停（09:25-10:00）且炸板≤1次
            if first_seal_time and first_seal_time <= '100000' and zab_count <= 1:
                quality_first_boards.append({
                    'name': stock.get('名称'),
                    'code': stock.get('代码'),
                    'first_seal_time': first_seal_time,
                    'zab_count': zab_count,
                    'turnover': round(stock.get('换手率', 0), 2),
                    'amount': round(stock.get('成交额', 0) / 1e8, 2),
                    'sector': stock.get('所属行业', '')
                })

    # 按成交额排序
    quality_first_boards.sort(key=lambda x: x['amount'], reverse=True)
    result['quality_first_boards'] = quality_first_boards[:10]

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='全市场涨停股扫描')
    parser.add_argument('--date', default='20260429', help='日期(YYYYMMDD)')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')

    args = parser.parse_args()

    result = scan_all_limit_up_stocks(args.date)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 格式化输出
        print(f"\n{'='*60}")
        print(f"  📊 全市场涨停股扫描 | {args.date}")
        print(f"{'='*60}\n")

        print(f"📈 涨停总数: {result['total_count']}家\n")

        print("💰 成交额TOP10:")
        for stock in result['top_by_amount']:
            print(f"  {stock['rank']}. {stock['name']}({stock['code']}) "
                  f"{stock['boards']}板 | 成交{stock['amount']}亿 | "
                  f"涨停{stock['first_seal_time']} | 炸板{stock['zab_count']}次")

        print("\n🏆 板块强度TOP10:")
        for sector, data in result['sector_summary'].items():
            print(f"  {sector}: {data['count']}只涨停 | 成交{data['total_amount']}亿")
            print(f"    代表股: {', '.join(data['stocks'])}")

        print("\n⭐ 优质首板（早盘涨停+封板稳定）:")
        for stock in result['quality_first_boards']:
            print(f"  {stock['name']}({stock['code']}) | "
                  f"涨停{stock['first_seal_time']} | 炸板{stock['zab_count']}次 | "
                  f"成交{stock['amount']}亿 | {stock['sector']}")
