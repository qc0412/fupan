#!/usr/bin/env python3
"""
⚠️⚠️⚠️ DEPRECATED（2026-06 实测已失效）⚠️⚠️⚠️
实测症状（2026-06-09/10）：
  - 匿名 POST 返回 HTTP 200，但 result['list'] 恒为空列表；
  - 历史日期参数被服务端忽略（请求 Date=20260609 仍返回 Day=["2026-06-10"]）。
替代方案：请改用 AkShare 的 stock_zt_pool_em（涨停池）等接口获取涨停板数据。
本文件仅保留作参考，调用方收到空列表时会打印醒目警告。

开盘啦 API 接口封装
用于获取A股涨停板数据
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Optional


DEPRECATED_WARNING = (
    "⚠️ 开盘啦接口返回空数据——该接口2026-06实测已失效"
    "（200但list恒空、历史日期参数被忽略），请改用 AkShare stock_zt_pool_em"
)


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
            warned_bad_field = False  # 字段类型异常只警告一次

            if 'list' in result and isinstance(result['list'], list):
                for item in result['list']:
                    if isinstance(item, list) and len(item) > 10:
                        # 类型校验：关键数值字段不是数字则跳过该条，防字段调序静默错数
                        try:
                            change_pct = float(item[6])
                            price = float(item[5])
                        except (TypeError, ValueError):
                            if not warned_bad_field:
                                print(
                                    "⚠️ 开盘啦返回字段类型异常（change_pct/price 非数字），"
                                    "可能字段顺序已变更，已跳过异常条目，请人工核对 FIELD_MAPPING"
                                )
                                warned_bad_field = True
                            continue

                        stock = {
                            'code': item[0],
                            'name': item[1],
                            'boards': item[3],
                            'concept': item[4],
                            'price': price,
                            'change_pct': change_pct,
                            'volume': item[7],
                            'turnover': item[8],
                            'amount': item[10],
                        }
                        stocks.append(stock)

            if not stocks:
                print(DEPRECATED_WARNING)

            return stocks

        except Exception as e:
            print(f"获取数据失败: {e}")
            print(DEPRECATED_WARNING)
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

    @staticmethod
    def _limit_up_threshold(code: str, name: str) -> float:
        """
        按代码前缀/名称返回涨停判定阈值：
        - 30/68 开头（创业板/科创板，20cm）→ 19.5
        - 43/83/87/88/92 开头（北交所，30cm）→ 29.5
        - 名称含 ST（5cm）→ 4.8
        - 其余主板（10cm）→ 9.8
        """
        code = str(code)
        name = str(name)
        if 'ST' in name.upper():
            return 4.8
        if code.startswith(('43', '83', '87', '88', '92')):
            return 29.5
        if code.startswith(('30', '68')):
            return 19.5
        return 9.8

    def get_real_limit_up_stocks(
        self,
        date: str = "",
        start_time: str = "0925",
        end_time: str = "0950",
        min_change_pct: Optional[float] = None
    ) -> List[Dict]:
        """
        获取真正的涨停板股票（按板块分别判定涨停阈值）

        Args:
            date: 日期，格式YYYYMMDD，空表示今天
            start_time: 开始时间，格式HHMM
            end_time: 结束时间，格式HHMM
            min_change_pct: 最小涨幅；None（默认）时按代码前缀/ST自动分阈值
                            （30/68→19.5，43/83/87/88/92→29.5，ST→4.8，其余→9.8）

        Returns:
            涨停板股票列表
        """

        all_stocks = self.get_limit_up_stocks(
            date=date,
            start_time=start_time,
            end_time=end_time
        )

        # 筛选达到涨停阈值的股票（按板块分阈值）
        limit_up_stocks = [
            stock for stock in all_stocks
            if stock.get('change_pct', 0) >= (
                min_change_pct if min_change_pct is not None
                else self._limit_up_threshold(stock.get('code', ''), stock.get('name', ''))
            )
        ]

        if not limit_up_stocks:
            print(DEPRECATED_WARNING)

        return limit_up_stocks


def main():
    """测试函数"""
    api = KaiLaiAPI()

    # 获取今日真正的涨停板股票
    print("=== 今日涨停板股票（按板块分阈值判定）===")
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
