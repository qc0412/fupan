#!/usr/bin/env python3
"""
开盘啦 API 接口封装
用于获取A股涨停板数据
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Optional


class KaiLaiAPI:
    """开盘啦API客户端"""

    BASE_URL = "https://apphwshhq.longhuvip.com/w1/api/index.php"

    HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; V1916A Build/PQ3B.190801.002)',
        'Accept-Encoding': 'gzip',
    }

    # 字段映射（根据返回数据推测）
    FIELD_MAPPING = {
        0: 'code',           # 股票代码
        1: 'name',           # 股票名称
        2: 'unknown1',       # 未知字段
        3: 'boards',         # 连板数
        4: 'concept',        # 概念/题材
        5: 'price',          # 价格
        6: 'change_pct',     # 涨跌幅
        7: 'volume',         # 成交量
        8: 'turnover',       # 换手率
        9: 'unknown2',       # 未知字段
        10: 'amount',        # 成交额
        # ... 更多字段待补充
    }

    def __init__(self, device_id: str = "77cb70bc-fdb9-37a4-a993-4c5764859153"):
        self.device_id = device_id
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def get_limit_up_stocks(
        self,
        date: str = "",
        start_time: str = "0925",
        end_time: str = "0940",
        order: int = 1,
        filter_bjs: int = 1,  # 过滤北交所
        filter_tib: int = 0,  # 过滤科创板
        filter_gem: int = 0,  # 过滤创业板
    ) -> List[Dict]:
        """
        获取涨停股票列表

        Args:
            date: 日期，格式YYYYMMDD，空表示今天
            start_time: 开始时间，格式HHMM
            end_time: 结束时间，格式HHMM
            order: 排序方式
            filter_bjs: 是否过滤北交所（1=过滤）
            filter_tib: 是否过滤科创板（1=过滤）
            filter_gem: 是否过滤创业板（1=过滤）

        Returns:
            股票列表
        """

        data = {
            'Order': str(order),
            'a': 'RealRankingInfo_W8',
            'st': '0',  # 修改为0，获取所有状态的股票
            'c': 'NewStockRanking',
            'PhoneOSNew': '1',
            'RStart': start_time,
            'DeviceID': self.device_id,
            'VerSion': '5.22.0.6',
            'Isst': '0',
            'index': '0',
            'Date': date,
            'REnd': end_time,
            'apiv': 'w43',
            'Type': '1',
            'FilterMotherboard': '0',
            'Filter': '0',
            'Ratio': '6',
            'FilterBJS': str(filter_bjs),
            'FilterTIB': str(filter_tib),
            'FilterGem': str(filter_gem),
        }

        try:
            response = self.session.post(self.BASE_URL, data=data, timeout=10)
            response.raise_for_status()

            result = response.json()
            stocks = []

            if 'list' in result and isinstance(result['list'], list):
                for item in result['list']:
                    if isinstance(item, list) and len(item) > 10:
                        stock = {
                            'code': item[0],
                            'name': item[1],
                            'boards': item[3],
                            'concept': item[4],
                            'price': item[5],
                            'change_pct': item[6],
                            'volume': item[7],
                            'turnover': item[8],
                            'amount': item[10],
                        }
                        stocks.append(stock)

            return stocks

        except Exception as e:
            print(f"获取数据失败: {e}")
            return []

    def get_limit_up_by_time(
        self,
        date: str = "",
        time_ranges: List[tuple] = None
    ) -> Dict[str, List[Dict]]:
        """
        按时间段获取涨停股票

        Args:
            date: 日期
            time_ranges: 时间段列表，例如 [("0925", "0930"), ("0930", "0940")]

        Returns:
            按时间段分组的股票字典
        """

        if time_ranges is None:
            time_ranges = [
                ("0925", "0930"),  # 集合竞价
                ("0930", "0940"),  # 早盘10分钟
                ("0940", "1000"),  # 早盘20分钟
                ("1000", "1030"),  # 早盘30分钟
            ]

        result = {}

        for start, end in time_ranges:
            stocks = self.get_limit_up_stocks(
                date=date,
                start_time=start,
                end_time=end
            )
            key = f"{start}-{end}"
            result[key] = stocks

        return result

    def get_real_limit_up_stocks(
        self,
        date: str = "",
        start_time: str = "0925",
        end_time: str = "0950",
        min_change_pct: float = 9.9
    ) -> List[Dict]:
        """
        获取真正的涨停板股票（涨幅>=9.9%）

        Args:
            date: 日期，格式YYYYMMDD，空表示今天
            start_time: 开始时间，格式HHMM
            end_time: 结束时间，格式HHMM
            min_change_pct: 最小涨幅，默认9.9%

        Returns:
            涨停板股票列表
        """

        all_stocks = self.get_limit_up_stocks(
            date=date,
            start_time=start_time,
            end_time=end_time
        )

        # 筛选涨幅>=min_change_pct的股票
        limit_up_stocks = [
            stock for stock in all_stocks
            if stock.get('change_pct', 0) >= min_change_pct
        ]

        return limit_up_stocks


def main():
    """测试函数"""
    api = KaiLaiAPI()

    # 获取今日真正的涨停板股票
    print("=== 今日涨停板股票（涨幅>=9.9%）===")
    limit_up_stocks = api.get_real_limit_up_stocks(
        start_time="0925",
        end_time="0950"
    )

    print(f"共 {len(limit_up_stocks)} 只涨停板\n")

    for i, stock in enumerate(limit_up_stocks[:20], 1):
        print(f"{i}. {stock['name']}({stock['code']})")
        print(f"   连板数: {stock['boards']}板")
        print(f"   概念: {stock['concept']}")
        print(f"   涨幅: {stock['change_pct']}%")
        print(f"   换手率: {stock['turnover']}%")
        print()

    # 获取所有上涨股票（包括非涨停）
    print("\n=== 今日所有上涨股票（09:25-09:50）===")
    all_stocks = api.get_limit_up_stocks(start_time="0925", end_time="0950")
    print(f"共 {len(all_stocks)} 只上涨股票")


if __name__ == "__main__":
    main()
