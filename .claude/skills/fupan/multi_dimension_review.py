#!/usr/bin/env python3
"""
多维度复盘助手 - 多源数据（全AkShare）
基于用户的8维度选股标准
"""

# ⚠️ 本脚本为V4.0时代遗留：
#   - 数据源共5个（资金流/人气/涨停/龙虎榜/板块龙头），全部走 AkShare；
#     原第6/7数据源（开盘啦多日叠加/异动提醒）随开盘啦接口2026-06实测失效已删除；
#   - "跟风数"为近似估算（按来源数量推测），禁止用于 /jieli 的跟风判定（/jieli 要求实数）；
#   - 评分口径13分制已废弃（现行为V5.x框架100分制）。
# 请勿将本脚本输出当作权威数据源。

import os
import sys
import json
from datetime import datetime, timedelta


class MultiDimensionReview:
    """多维度复盘分析器"""

    def __init__(self, date_str=None):
        self.date = date_str or datetime.now().strftime('%Y-%m-%d')
        self.date_param = self.date.replace('-', '')

    def get_all_stocks_to_review(self):
        """
        获取所有需要复盘的股票（去重）

        来源：
        1. 资金流入top20
        2. 人气股前10
        3. 所有涨停股
        4. 龙虎榜股
        5. 强度前5板块的分别前5个股
        """
        all_stocks = {}  # 用字典去重，key=股票代码

        print("=" * 60)
        print(f"📊 多维度股票池构建 - {self.date}")
        print("=" * 60)

        # 1. 资金流入top20
        print("\n1️⃣ 获取资金流入TOP20...")
        capital_flow = self._get_capital_flow_top20()
        for stock in capital_flow:
            code = stock['code']
            if code not in all_stocks:
                all_stocks[code] = {
                    'code': code,
                    'name': stock['name'],
                    'sources': ['资金流入TOP20'],
                    'capital_rank': stock['rank']
                }
            else:
                all_stocks[code]['sources'].append('资金流入TOP20')
                all_stocks[code]['capital_rank'] = stock['rank']

        # 2. 人气股前10（按成交额）
        print("\n2️⃣ 获取人气股TOP10...")
        popular_stocks = self._get_popular_stocks_top10()
        for stock in popular_stocks:
            code = stock['code']
            if code not in all_stocks:
                all_stocks[code] = {
                    'code': code,
                    'name': stock['name'],
                    'sources': ['人气股TOP10'],
                    'volume_rank': stock['rank'],
                    'volume': stock['volume']
                }
            else:
                all_stocks[code]['sources'].append('人气股TOP10')
                all_stocks[code]['volume_rank'] = stock['rank']
                all_stocks[code]['volume'] = stock['volume']

        # 3. 所有涨停股
        print("\n3️⃣ 获取所有涨停股...")
        limit_up_stocks = self._get_all_limit_up()
        for stock in limit_up_stocks:
            code = stock['code']
            if code not in all_stocks:
                all_stocks[code] = {
                    'code': code,
                    'name': stock['name'],
                    'sources': ['涨停股'],
                    'limit_up_time': stock['time'],
                    'boards': stock['boards']
                }
            else:
                all_stocks[code]['sources'].append('涨停股')
                all_stocks[code]['limit_up_time'] = stock['time']
                all_stocks[code]['boards'] = stock['boards']

        # 4. 龙虎榜股
        print("\n4️⃣ 获取龙虎榜股...")
        lhb_stocks = self._get_lhb_stocks()
        for stock in lhb_stocks:
            code = stock['code']
            if code not in all_stocks:
                all_stocks[code] = {
                    'code': code,
                    'name': stock['name'],
                    'sources': ['龙虎榜'],
                    'lhb_reason': stock.get('reason', '')
                }
            else:
                all_stocks[code]['sources'].append('龙虎榜')
                all_stocks[code]['lhb_reason'] = stock.get('reason', '')

        # 5. 强度前5板块的前5个股
        print("\n5️⃣ 获取强度前5板块的龙头股...")
        sector_leaders = self._get_top_sectors_leaders()
        for stock in sector_leaders:
            code = stock['code']
            if code not in all_stocks:
                all_stocks[code] = {
                    'code': code,
                    'name': stock['name'],
                    'sources': [f"{stock['sector']}板块龙头"],
                    'sector': stock['sector'],
                    'sector_rank': stock['rank_in_sector']
                }
            else:
                all_stocks[code]['sources'].append(f"{stock['sector']}板块龙头")
                all_stocks[code]['sector'] = stock['sector']
                all_stocks[code]['sector_rank'] = stock['rank_in_sector']

        # 统计
        print("\n" + "=" * 60)
        print(f"✅ 股票池构建完成：共 {len(all_stocks)} 只股票")
        print("=" * 60)

        # 按来源数量排序（来源越多，越值得关注）
        sorted_stocks = sorted(
            all_stocks.values(),
            key=lambda x: len(x['sources']),
            reverse=True
        )

        return sorted_stocks

    def score_stock(self, stock_data):
        """
        8维度评分系统

        1. 是否有逻辑（0-3分）
        2. 走的主动的（0-2分）
        3. 带动板块的（0-1分）
        4. 是否是龙1（0-2分）
        5. 最好有跟风股（0-1分）
        6. 最好还没有开始加速（0-1分）
        7. 转弱之后是否转强（0-2分）
        8. 最好有点容量（0-1分）

        总分13分，>=9分重点关注
        """
        score = 0
        details = {}

        # 1. 是否有逻辑（0-3分）
        logic_score = self._score_logic(stock_data)
        score += logic_score
        details['逻辑'] = f"{logic_score}/3分"

        # 2. 走的主动的（0-2分）
        initiative_score = self._score_initiative(stock_data)
        score += initiative_score
        details['主动性'] = f"{initiative_score}/2分"

        # 3. 带动板块的（0-1分）
        sector_lead_score = self._score_sector_lead(stock_data)
        score += sector_lead_score
        details['带动板块'] = f"{sector_lead_score}/1分"

        # 4. 是否是龙1（0-2分）
        leader_score = self._score_leader_position(stock_data)
        score += leader_score
        details['龙头地位'] = f"{leader_score}/2分"

        # 5. 最好有跟风股（0-1分）
        follower_score = self._score_followers(stock_data)
        score += follower_score
        details['跟风股'] = f"{follower_score}/1分"

        # 6. 最好还没有开始加速（0-1分）
        acceleration_score = self._score_acceleration(stock_data)
        score += acceleration_score
        details['加速状态'] = f"{acceleration_score}/1分"

        # 7. 转弱之后是否转强（0-2分）
        reversal_score = self._score_reversal(stock_data)
        score += reversal_score
        details['反包'] = f"{reversal_score}/2分"

        # 8. 最好有点容量（0-1分）
        volume_score = self._score_volume(stock_data)
        score += volume_score
        details['容量'] = f"{volume_score}/1分"

        return {
            'total_score': score,
            'max_score': 13,
            'details': details,
            'conclusion': '🔥重点关注' if score >= 9 else '⚠️观察' if score >= 6 else '❌不关注'
        }

    # ========== 私有方法：数据获取 ==========

    def _get_capital_flow_top20(self):
        """获取资金流入TOP20"""
        try:
            import akshare as ak
            import warnings
            warnings.filterwarnings('ignore')

            # 使用AkShare获取资金流向
            df = ak.stock_individual_fund_flow_rank(indicator="今日")

            # 取前20名
            top20 = df.head(20)

            result = []
            for idx, row in top20.iterrows():
                result.append({
                    'code': str(row['代码']),
                    'name': row['名称'],
                    'rank': idx + 1,
                    'net_inflow': row.get('主力净流入-净额', 0),
                    'net_inflow_pct': row.get('主力净流入-净占比', 0)
                })

            print(f"   ✅ 获取到 {len(result)} 只资金流入股")
            return result

        except Exception as e:
            print(f"   ⚠️ 资金流入数据获取失败: {e}")
            return []

    def _get_popular_stocks_top10(self):
        """获取人气股TOP10（按成交额）"""
        try:
            import akshare as ak
            import warnings
            warnings.filterwarnings('ignore')

            # 获取实时行情
            df = ak.stock_zh_a_spot_em()

            # 按成交额排序，取前10
            df_sorted = df.sort_values(by='成交额', ascending=False)

            result = []
            # 注意：sort_values 后原始行号不等于名次，必须用 enumerate 计排名
            for rank, (_, row) in enumerate(df_sorted.head(10).iterrows(), 1):
                result.append({
                    'code': str(row['代码']),
                    'name': row['名称'],
                    'rank': rank,
                    'volume': row['成交额'] / 100000000,  # 转换为亿
                    'change_pct': row.get('涨跌幅', 0)
                })

            print(f"   ✅ 获取到 {len(result)} 只人气股")
            return result

        except Exception as e:
            print(f"   ⚠️ 人气股数据获取失败: {e}")
            return []

    def _get_all_limit_up(self):
        """获取所有涨停股（AkShare 涨停池，原开盘啦接口2026-06实测失效已迁移）"""
        try:
            import akshare as ak
            import warnings
            warnings.filterwarnings('ignore')

            # 实测列名（2026-06-10）：序号/代码/名称/涨跌幅/最新价/成交额/流通市值/
            # 总市值/换手率/封板资金/首次封板时间/最后封板时间/炸板次数/涨停统计/连板数/所属行业
            df = ak.stock_zt_pool_em(date=self.date_param)

            result = []
            for _, row in df.iterrows():
                result.append({
                    'code': str(row['代码']),
                    'name': row['名称'],
                    'change_pct': float(row['涨跌幅']),
                    'time': self._format_time(str(row['首次封板时间'])),
                    'boards': int(row['连板数']) if '连板数' in row else 1,
                    # 开盘啦的题材概念字段已不可得，用东财"所属行业"近似
                    # （行业≠题材，主线归类仍须走 plate_classifier）
                    'concept': row.get('所属行业', ''),
                    'sector': row.get('所属行业', ''),
                    'seal_amount': float(row.get('封板资金', 0)),
                    'open_times': int(row.get('炸板次数', 0)),
                    'turnover': float(row.get('换手率', 0)),
                    # 成交额原始单位为元，转为万元（_score_volume 按万元口径换算亿）
                    'amount': float(row.get('成交额', 0)) / 10000
                })

            print(f"   ✅ 获取到 {len(result)} 只涨停股")
            return result

        except Exception as e:
            print(f"   ⚠️ 涨停股数据获取失败: {e}")
            return []

    def _get_lhb_stocks(self):
        """获取龙虎榜股"""
        try:
            import akshare as ak
            import warnings
            warnings.filterwarnings('ignore')

            # 获取龙虎榜数据
            df = ak.stock_lhb_detail_em(start_date=self.date_param, end_date=self.date_param)

            result = []
            for idx, row in df.iterrows():
                result.append({
                    'code': str(row['代码']),
                    'name': row['名称'],
                    'reason': row.get('上榜原因', ''),
                    'net_buy': row.get('龙虎榜净买额', 0),
                    'change_pct': row.get('涨跌幅', 0)
                })

            print(f"   ✅ 获取到 {len(result)} 只龙虎榜股")
            return result

        except Exception as e:
            print(f"   ⚠️ 龙虎榜数据获取失败: {e}")
            return []

    def _get_top_sectors_leaders(self):
        """获取强度前5板块的前5个股"""
        try:
            import akshare as ak
            import warnings
            warnings.filterwarnings('ignore')

            # 获取板块行情
            sectors_df = ak.stock_board_industry_name_em()

            # 按涨跌幅排序，取前5个板块
            sectors_df_sorted = sectors_df.sort_values(by='涨跌幅', ascending=False)
            top5_sectors = sectors_df_sorted.head(5)

            result = []

            for _, sector_row in top5_sectors.iterrows():
                sector_name = sector_row['板块名称']

                # 获取该板块的成分股
                try:
                    stocks_df = ak.stock_board_industry_cons_em(symbol=sector_name)

                    # 按涨跌幅排序，取前5只
                    # 注意：sort_values 后原始行号不等于名次，必须用 enumerate 计板块内排名
                    stocks_df_sorted = stocks_df.sort_values(by='涨跌幅', ascending=False)

                    for rank_in_sector, (_, stock_row) in enumerate(
                            stocks_df_sorted.head(5).iterrows(), 1):
                        result.append({
                            'code': str(stock_row['代码']),
                            'name': stock_row['名称'],
                            'sector': sector_name,
                            'rank_in_sector': rank_in_sector,
                            'change_pct': stock_row.get('涨跌幅', 0)
                        })
                except Exception as e:
                    print(f"   ⚠️ 获取板块 {sector_name} 成分股失败: {e}")
                    continue

            print(f"   ✅ 获取到 {len(result)} 只板块龙头股")
            return result

        except Exception as e:
            print(f"   ⚠️ 板块龙头数据获取失败: {e}")
            return []

    def _format_time(self, time_str):
        """格式化时间字符串"""
        if not time_str:
            return ''
        # 6位数字（AkShare首次封板时间，HHMMSS）→ HH:MM（丢秒，兼容评分解析）
        if len(time_str) == 6 and time_str.isdigit():
            return f"{time_str[:2]}:{time_str[2:4]}"
        # 4位数字，转换为HH:MM格式
        if len(time_str) == 4 and time_str.isdigit():
            return f"{time_str[:2]}:{time_str[2:]}"
        return time_str

    # ========== 私有方法：评分逻辑 ==========

    def _score_logic(self, stock):
        """评分：是否有逻辑（0-3分）"""
        # 强逻辑：政策、涨价、业绩暴增
        # 中逻辑：概念题材、行业利好
        # 弱逻辑：跟风、情绪
        # 无逻辑：不明原因

        concept = stock.get('concept', '')

        # 强逻辑关键词
        strong_keywords = ['政策', '涨价', '业绩', '重组', '并购', '国资', '央企']
        # 中逻辑关键词
        medium_keywords = ['AI', '机器人', '新能源', '芯片', '半导体', '华为', '鸿蒙',
                          '光伏', '锂电', '储能', '算力', '数据中心']

        if any(kw in concept for kw in strong_keywords):
            return 3
        elif any(kw in concept for kw in medium_keywords):
            return 2
        elif concept:
            return 1
        return 0

    def _score_initiative(self, stock):
        """评分：走的主动的（0-2分）"""
        # 主动：早盘涨停，带动板块
        # 中性：跟随板块涨停
        # 被动：尾盘跟风涨停

        time = stock.get('limit_up_time', '')
        if not time:
            return 0

        # 转换为分钟数
        try:
            if ':' in time:
                h, m = time.split(':')
                minutes = int(h) * 60 + int(m)
            else:
                minutes = 0
        except:
            return 0

        # 早盘涨停（9:25-10:00）
        if 9 * 60 + 25 <= minutes <= 10 * 60:
            return 2
        # 上午涨停（10:00-11:30）
        elif 10 * 60 < minutes <= 11 * 60 + 30:
            return 1
        # 下午涨停
        else:
            return 0

    def _score_sector_lead(self, stock):
        """评分：带动板块的（0-1分）"""
        # 判断：是否是板块最早涨停的
        sector_rank = stock.get('sector_rank', 999)
        return 1 if sector_rank == 1 else 0

    def _score_leader_position(self, stock):
        """评分：是否是龙1（0-2分）"""
        # 总龙头：2分
        # 细分龙头：1分
        # 跟风：0分

        boards = stock.get('boards', 0)
        sector_rank = stock.get('sector_rank', 999)

        # 连板数>=3且是板块第一
        if boards >= 3 and sector_rank == 1:
            return 2
        # 板块前2名
        elif sector_rank <= 2:
            return 1
        # 连板数>=2
        elif boards >= 2:
            return 1
        return 0

    def _score_followers(self, stock):
        """评分：最好有跟风股（0-1分）"""
        # 查询同板块同概念的涨停股数量
        concept = stock.get('concept', '')
        if not concept:
            return 0

        # TODO: 需要查询同概念的其他涨停股
        # 暂时根据来源数量判断
        sources_count = len(stock.get('sources', []))

        # 如果出现在多个数据源，说明关注度高，可能有跟风
        if sources_count >= 3:
            return 1
        return 0

    def _score_acceleration(self, stock):
        """评分：最好还没有开始加速（0-1分）"""
        # 连续3天缩量加速 = 0分
        # 否则 = 1分

        boards = stock.get('boards', 0)

        # 6板以上认为已经加速
        if boards >= 6:
            return 0
        # 3-5板是主升期，还可以
        elif boards >= 3:
            return 0.5
        # 1-2板是启动期，最佳
        else:
            return 1

    def _score_reversal(self, stock):
        """评分：转弱之后是否转强（0-2分）"""
        # 二次反包：2分
        # 一次反包：1分
        # 无反包：0分

        # TODO: 需要查询历史K线数据判断是否反包
        # 暂时根据连板数和换手率判断
        boards = stock.get('boards', 0)
        turnover = stock.get('turnover', 0)

        # 如果是2板以上且换手率较高（>10%），可能是反包
        if boards >= 2 and turnover > 10:
            return 1

        return 0

    def _score_volume(self, stock):
        """评分：最好有点容量（0-1分）"""
        # 成交额 > 10亿：1分
        # 否则：0分

        # 从不同字段获取成交额
        volume = stock.get('volume', 0)  # 人气股的成交额（亿）
        amount = stock.get('amount', 0)  # 涨停股的成交额（可能是万元）

        # 统一转换为亿
        if volume > 0:
            volume_yi = volume
        elif amount > 0:
            # 假设amount单位是万元
            volume_yi = amount / 10000
        else:
            volume_yi = 0

        return 1 if volume_yi >= 10 else 0


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='多维度复盘助手')
    parser.add_argument('--date', help='日期 (YYYY-MM-DD)', default=None)
    parser.add_argument('--action', choices=['pool', 'score', 'full'],
                       default='full',
                       help='pool=构建股票池, score=评分, full=完整复盘')
    parser.add_argument('--force', action='store_true',
                       help='指定历史日期时强制继续（数据源大部分为实时，历史结果不可信）')

    args = parser.parse_args()

    # --date 跨日防护：除龙虎榜/涨停池外其余数据源全是实时数据，历史日期混拼结果不可信
    today = datetime.now().strftime('%Y-%m-%d')
    if args.date and args.date != today:
        print("⚠️ 仅龙虎榜/涨停池支持历史日期，其余数据源（资金流/人气/板块）均为实时数据，"
              "历史复盘结果不可信")
        if not args.force:
            print("如确认要继续，请加 --force 参数。已退出。")
            sys.exit(1)

    reviewer = MultiDimensionReview(args.date)

    # 股票池只构建一次，pool/score/full 复用同一结果（避免 full 双倍请求）
    stocks = reviewer.get_all_stocks_to_review()

    if args.action in ['pool', 'full']:
        print("\n" + "=" * 60)
        print("📋 股票池详情（按来源数量排序）")
        print("=" * 60)

        for i, stock in enumerate(stocks[:30], 1):  # 只显示前30个
            sources = ', '.join(stock['sources'])
            print(f"\n{i}. {stock['name']}({stock['code']})")
            print(f"   来源数量: {len(stock['sources'])}个")
            print(f"   来源: {sources}")

            if 'boards' in stock:
                print(f"   连板: {stock['boards']}板")
            if 'limit_up_time' in stock:
                print(f"   涨停时间: {stock['limit_up_time']}")
            if 'volume' in stock:
                print(f"   成交额: {stock['volume']:.2f}亿")

    if args.action in ['score', 'full']:
        # 评分（复用上面已构建的股票池，不重复请求）
        print("\n" + "=" * 60)
        print("🎯 8维度评分（>=9分重点关注）")
        print("=" * 60)

        scored_stocks = []
        for stock in stocks:
            score_result = reviewer.score_stock(stock)
            stock['score'] = score_result
            scored_stocks.append(stock)

        # 按总分排序
        scored_stocks.sort(key=lambda x: x['score']['total_score'], reverse=True)

        for i, stock in enumerate(scored_stocks[:20], 1):
            score = stock['score']
            print(f"\n{i}. {stock['name']}({stock['code']}) - {score['conclusion']}")
            print(f"   总分: {score['total_score']}/{score['max_score']}分")
            print(f"   详情: {score['details']}")


if __name__ == '__main__':
    main()
