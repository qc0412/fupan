#!/usr/bin/env python3
import os
"""
整合复盘脚本 - 结合多维度分析和V4.0框架
"""

import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.expanduser('~/.claude/skills/fupan'))
from multi_dimension_review import MultiDimensionReview


def main():
    """主函数 - 整合复盘流程"""
    import argparse

    parser = argparse.ArgumentParser(description='整合复盘助手')
    parser.add_argument('--date', help='日期 (YYYY-MM-DD)', default=None)

    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime('%Y-%m-%d')

    print("=" * 80)
    print(f"📊 A股多维度复盘 - {date_str}")
    print("=" * 80)

    # 第一步：多维度股票池构建
    print("\n" + "=" * 80)
    print("第一步：构建多维度股票池")
    print("=" * 80)

    reviewer = MultiDimensionReview(date_str)
    all_stocks = reviewer.get_all_stocks_to_review()

    # 第二步：8维度评分
    print("\n" + "=" * 80)
    print("第二步：8维度量化评分")
    print("=" * 80)

    scored_stocks = []
    for stock in all_stocks:
        score_result = reviewer.score_stock(stock)
        stock['score'] = score_result
        scored_stocks.append(stock)

    # 按总分排序
    scored_stocks.sort(key=lambda x: x['score']['total_score'], reverse=True)

    # 第三步：输出结果
    print("\n" + "=" * 80)
    print("第三步：复盘结果汇总")
    print("=" * 80)

    # 3.1 重点关注股票（>=9分）
    high_score_stocks = [s for s in scored_stocks if s['score']['total_score'] >= 9]
    print(f"\n🔥 重点关注（>=9分）：{len(high_score_stocks)} 只")
    print("-" * 80)

    for i, stock in enumerate(high_score_stocks[:10], 1):
        score = stock['score']
        print(f"\n{i}. {stock['name']}({stock['code']}) - 总分: {score['total_score']}/13分")
        print(f"   来源: {', '.join(stock['sources'][:3])}")

        if 'boards' in stock:
            print(f"   连板: {stock['boards']}板", end='')
        if 'limit_up_time' in stock:
            print(f" | 涨停时间: {stock['limit_up_time']}", end='')
        if 'concept' in stock:
            print(f" | 概念: {stock['concept'][:20]}", end='')
        print()

        print(f"   评分详情: {score['details']}")

    # 3.2 观察股票（6-8分）
    medium_score_stocks = [s for s in scored_stocks if 6 <= s['score']['total_score'] < 9]
    print(f"\n⚠️ 观察股票（6-8分）：{len(medium_score_stocks)} 只")
    print("-" * 80)

    for i, stock in enumerate(medium_score_stocks[:10], 1):
        score = stock['score']
        print(f"{i}. {stock['name']}({stock['code']}) - {score['total_score']}/13分")

    # 3.3 统计信息
    print("\n" + "=" * 80)
    print("📈 统计信息")
    print("=" * 80)

    print(f"\n总股票池: {len(all_stocks)} 只")
    print(f"重点关注（>=9分）: {len(high_score_stocks)} 只")
    print(f"观察股票（6-8分）: {len(medium_score_stocks)} 只")
    print(f"不关注（<6分）: {len(scored_stocks) - len(high_score_stocks) - len(medium_score_stocks)} 只")

    # 统计来源分布
    print("\n来源分布:")
    source_count = {}
    for stock in all_stocks:
        for source in stock['sources']:
            source_count[source] = source_count.get(source, 0) + 1

    for source, count in sorted(source_count.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {source}: {count} 只")

    # 3.4 输出JSON格式（供Claude使用）
    output_data = {
        'date': date_str,
        'total_stocks': len(all_stocks),
        'high_score_stocks': [
            {
                'code': s['code'],
                'name': s['name'],
                'score': s['score']['total_score'],
                'details': s['score']['details'],
                'sources': s['sources'],
                'boards': s.get('boards', 0),
                'limit_up_time': s.get('limit_up_time', ''),
                'concept': s.get('concept', ''),
                'turnover': s.get('turnover', 0),
                'volume': s.get('volume', 0)
            }
            for s in high_score_stocks[:20]
        ],
        'medium_score_stocks': [
            {
                'code': s['code'],
                'name': s['name'],
                'score': s['score']['total_score'],
                'boards': s.get('boards', 0)
            }
            for s in medium_score_stocks[:20]
        ]
    }

    # 保存到临时文件
    output_file = f"/tmp/fupan_multi_dimension_{date_str.replace('-', '')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 结果已保存到: {output_file}")

    return output_data


if __name__ == '__main__':
    main()
