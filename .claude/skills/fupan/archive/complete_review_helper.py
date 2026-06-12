#!/usr/bin/env python3
import os
"""
完整复盘工具 V4.0
整合5大维度：资金流入、人气股、涨停股、龙虎榜、板块龙头
"""

import sys
sys.path.insert(0, os.path.expanduser('~/.claude/skills/fupan/scripts'))
from astock_data import AStockDataFetcher
import json


def complete_market_review(date_str="20260429"):
    """
    完整市场复盘

    返回：
    1. 资金流入TOP20
    2. 人气股TOP10（按成交额）
    3. 所有涨停股（分层）
    4. 龙虎榜股
    5. 强度前5板块的龙头
    """
    fetcher = AStockDataFetcher(enable_cache=True)

    result = {
        'date': date_str,
        'fund_flow_top20': [],
        'hot_stocks_top10': [],
        'limit_up_summary': {},
        'lhb_stocks': [],
        'sector_leaders': {}
    }

    # 1. 资金流入TOP20
    print("📊 [1/5] 获取资金流向数据...")
    fund_flow = fetcher.get_fund_flow(flow_type="market", date_str=date_str)
    # TODO: 需要获取个股资金流向排行
    # 暂时从涨停池中提取资金流向信息

    # 2. 人气股TOP10（按成交额）
    print("📊 [2/5] 获取人气股数据...")
    zt_data = fetcher.get_zt_dt_summary(date_str)
    all_stocks = zt_data.get('_zt_detail', [])

    # 按成交额排序
    sorted_by_amount = sorted(
        all_stocks,
        key=lambda x: x.get('成交额', 0),
        reverse=True
    )[:10]

    for i, stock in enumerate(sorted_by_amount):
        result['hot_stocks_top10'].append({
            'rank': i + 1,
            'name': stock.get('名称'),
            'code': stock.get('代码'),
            'amount': round(stock.get('成交额', 0) / 1e8, 2),
            'turnover': round(stock.get('换手率', 0), 2),
            'chg_pct': round(stock.get('涨跌幅', 0), 2),
            'boards': stock.get('连板数', 1),
            'first_seal_time': stock.get('首次封板时间', ''),
            'zab_count': stock.get('炸板次数', 0),
            'sector': stock.get('所属行业', '')
        })

    # 3. 所有涨停股（分层）
    print("📊 [3/5] 分析涨停股...")
    lianban_data = fetcher.get_lianban_ladder(date_str)
    ladder = lianban_data.get('ladder', {})

    result['limit_up_summary'] = {
        'total_count': len(all_stocks),
        'lianban_count': zt_data.get('lianban_count', 0),
        'max_height': zt_data.get('max_lianban', 0),
        'zab_rate': zt_data.get('zab_rate', 0),
        'ladder': {}
    }

    # 按连板高度分层，每层只显示关键信息
    for height_key, stocks in ladder.items():
        height = int(height_key.replace('板', ''))

        # 筛选优质股：早盘涨停 + 炸板≤1次
        quality_stocks = []
        for s in stocks:
            first_seal_time = s.get('first_seal_time', '')
            zab_count = s.get('zab_count', 0)

            # 早盘涨停（09:25-10:30）且炸板≤1次
            if first_seal_time and first_seal_time <= '103000' and zab_count <= 1:
                quality_stocks.append({
                    'name': s.get('name'),
                    'code': s.get('code'),
                    'first_seal_time': first_seal_time,
                    'zab_count': zab_count,
                    'turnover': round(s.get('turnover', 0), 2),
                    'amount': round(s.get('amount', 0), 2),
                    'sector': s.get('sector')
                })

        # 按成交额排序
        quality_stocks.sort(key=lambda x: x['amount'], reverse=True)

        result['limit_up_summary']['ladder'][height_key] = {
            'total_count': len(stocks),
            'quality_count': len(quality_stocks),
            'quality_stocks': quality_stocks[:5]  # 只显示前5只
        }

    # 4. 龙虎榜股
    print("📊 [4/5] 获取龙虎榜数据...")
    lhb_data = fetcher.get_lhb_data(date_str)
    lhb_stocks = lhb_data.get('lhb_stocks', [])

    for stock in lhb_stocks[:20]:  # 只取前20只
        result['lhb_stocks'].append({
            'name': stock.get('name'),
            'code': stock.get('code'),
            'chg_pct': round(stock.get('chg_pct', 0), 2),
            'net_buy': round(stock.get('net_buy', 0), 2),
            'reason': stock.get('reason', ''),
            'turnover_pct': round(stock.get('turnover_pct', 0), 2)
        })

    # 5. 强度前5板块的龙头
    print("📊 [5/5] 分析板块强度...")
    sector_data = fetcher.get_sector_ranking(date_str)
    concept_top = sector_data.get('concept_top10', [])[:5]

    # 对每个板块，找出龙头股
    for sector in concept_top:
        sector_name = sector.get('name', '')

        # 从涨停池中找出该板块的股票
        sector_stocks = [
            s for s in all_stocks
            if sector_name in s.get('所属行业', '') or sector_name in s.get('名称', '')
        ]

        # 按连板数和成交额排序
        sector_stocks.sort(
            key=lambda x: (x.get('连板数', 0), x.get('成交额', 0)),
            reverse=True
        )

        leader = None
        if sector_stocks:
            leader_data = sector_stocks[0]
            leader = {
                'name': leader_data.get('名称'),
                'code': leader_data.get('代码'),
                'boards': leader_data.get('连板数', 1),
                'amount': round(leader_data.get('成交额', 0) / 1e8, 2),
                'first_seal_time': leader_data.get('首次封板时间', ''),
                'zab_count': leader_data.get('炸板次数', 0)
            }

        result['sector_leaders'][sector_name] = {
            'rank': sector.get('rank'),
            'chg_pct': round(sector.get('chg_pct', 0), 2),
            'zt_count': sector.get('zt_count', 0),
            'leader': leader,
            'follower_count': len(sector_stocks) - 1 if sector_stocks else 0
        }

    return result


def format_review_report(data):
    """格式化输出复盘报告"""
    lines = []

    lines.append(f"\n{'='*70}")
    lines.append(f"  📊 完整市场复盘 V4.0 | {data['date']}")
    lines.append(f"{'='*70}\n")

    # 1. 人气股TOP10
    lines.append("🔥 人气股TOP10（按成交额）:")
    lines.append("-" * 70)
    for stock in data['hot_stocks_top10']:
        lines.append(
            f"  {stock['rank']}. {stock['name']}({stock['code']}) "
            f"{stock['boards']}板 | 成交{stock['amount']}亿 | "
            f"涨停{stock['first_seal_time']} | 炸板{stock['zab_count']}次 | "
            f"{stock['sector']}"
        )
    lines.append("")

    # 2. 涨停股分层（只显示优质股）
    lines.append("📈 涨停股分层（优质股：早盘涨停+炸板≤1次）:")
    lines.append("-" * 70)
    summary = data['limit_up_summary']
    lines.append(f"  总涨停: {summary['total_count']}家 | "
                f"连板: {summary['lianban_count']}家 | "
                f"最高: {summary['max_height']}板 | "
                f"炸板率: {summary['zab_rate']}%\n")

    for height_key in sorted(summary['ladder'].keys(),
                            key=lambda x: int(x.replace('板', '')),
                            reverse=True):
        layer = summary['ladder'][height_key]
        lines.append(f"  【{height_key}】共{layer['total_count']}只，"
                    f"优质{layer['quality_count']}只:")

        for stock in layer['quality_stocks']:
            lines.append(
                f"    • {stock['name']}({stock['code']}) | "
                f"涨停{stock['first_seal_time']} | 炸板{stock['zab_count']}次 | "
                f"成交{stock['amount']}亿 | {stock['sector']}"
            )
        lines.append("")

    # 3. 龙虎榜TOP10
    lines.append("🐯 龙虎榜TOP10:")
    lines.append("-" * 70)
    for i, stock in enumerate(data['lhb_stocks'][:10]):
        net_buy = stock['net_buy']
        direction = "🟢净买" if net_buy > 0 else "🔴净卖"
        lines.append(
            f"  {i+1}. {stock['name']}({stock['code']}) "
            f"{stock['chg_pct']:+.2f}% | {direction}{abs(net_buy):.2f}亿 | "
            f"{stock['reason']}"
        )
    lines.append("")

    # 4. 强度前5板块的龙头
    lines.append("🏆 强度前5板块的龙头:")
    lines.append("-" * 70)
    for sector_name, sector_data in data['sector_leaders'].items():
        leader = sector_data['leader']
        lines.append(
            f"  {sector_data['rank']}. {sector_name} "
            f"({sector_data['chg_pct']:+.2f}%) | "
            f"涨停{sector_data['zt_count']}只"
        )
        if leader:
            lines.append(
                f"     龙头: {leader['name']}({leader['code']}) "
                f"{leader['boards']}板 | 成交{leader['amount']}亿 | "
                f"涨停{leader['first_seal_time']} | 炸板{leader['zab_count']}次"
            )
            lines.append(
                f"     跟风: {sector_data['follower_count']}只"
            )
        else:
            lines.append("     龙头: 未找到")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='完整市场复盘 V4.0')
    parser.add_argument('--date', default='20260429', help='日期(YYYYMMDD)')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')

    args = parser.parse_args()

    print(f"\n🚀 开始完整市场复盘...")
    result = complete_market_review(args.date)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_review_report(result))
