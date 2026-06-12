#!/usr/bin/env python3
"""
东方财富妙想数据接口
用于 /fupan skill 获取市场数据
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Optional


def _first(table, key, default=0):
    """安全取 rawTable 中 key 对应列表的首元素（key缺失/值为空列表/首元素为空时返回 default）"""
    v = table.get(key) or [default]
    first = v[0] if v else default
    return default if first in (None, '') else first


class DFCFData:
    """东方财富妙想数据客户端"""

    def __init__(self):
        self.mx_data_script = os.path.expanduser("~/.claude/skills/mx-data/mx_data.py")
        self.python_bin = os.path.expanduser("~/.claude/mcp-servers/astock-data/venv/bin/python3")
        self.output_dir = os.path.expanduser("~/.claude/skills/fupan/mx_data_output")
        self.api_key = os.environ.get("MX_APIKEY")

        if not self.api_key:
            raise ValueError("MX_APIKEY 环境变量未设置")

        if not os.path.exists(self.mx_data_script):
            raise FileNotFoundError(
                f"mx-data 脚本不存在: {self.mx_data_script}。"
                "mx-data 是外部 skill（不随仓库携带），本机未安装则本模块全部功能不可用；"
                "/fupan 主流程不依赖 dfcf_data，可直接降级跳过。")

        if not os.path.exists(self.python_bin):
            raise FileNotFoundError(f"Python 解释器不存在: {self.python_bin}")

        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

    def _call_mx_data(self, query: str) -> Dict:
        """
        调用 mx-data 脚本查询数据

        Args:
            query: 查询语句

        Returns:
            查询结果的 JSON 数据
        """
        try:
            # 调用 mx-data 脚本（使用 astock-data 的虚拟环境，指定输出目录）
            result = subprocess.run(
                [self.python_bin, self.mx_data_script, query, self.output_dir],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "MX_APIKEY": self.api_key}
            )

            if result.returncode != 0:
                print(f"mx-data 查询失败: {result.stderr}", file=sys.stderr)
                return {}

            # 解析输出中的 JSON 数据
            output_lines = result.stdout.strip().split('\n')

            # 查找 JSON 文件路径（格式：📄 原始JSON: /path/to/file.json）
            json_file = None
            for line in output_lines:
                if '原始JSON:' in line or 'raw.json' in line:
                    # 提取路径
                    parts = line.split(':')
                    if len(parts) >= 2:
                        path = ':'.join(parts[1:]).strip()
                        if os.path.exists(path):
                            json_file = path
                            break

            if json_file and os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)

            return {}

        except subprocess.TimeoutExpired:
            print("mx-data 查询超时", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"调用 mx-data 失败: {e}", file=sys.stderr)
            return {}

    def get_index_data(self, date: str = "") -> Dict:
        """
        获取指数数据（上证指数、创业板指数）

        Args:
            date: 日期，格式 YYYY-MM-DD，空表示今天

        Returns:
            {
                'sz_index': {'close': 3000.0, 'change_pct': 0.5},
                'cyb_index': {'close': 2000.0, 'change_pct': 1.2}
            }
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        result = {}

        # 查询上证指数
        sz_query = f"上证指数{date}收盘价 涨跌幅"
        sz_data = self._call_mx_data(sz_query)

        if sz_data and 'data' in sz_data:
            # 正确的数据路径：data.data.searchDataResultDTO.dataTableDTOList
            search_result = sz_data.get('data', {}).get('data', {}).get('searchDataResultDTO', {})
            tables = search_result.get('dataTableDTOList', [])
            if tables:
                table = tables[0].get('rawTable', {})
                if 'f2' in table and table['f2']:  # f2 是最新价/收盘价
                    result['sz_index'] = {
                        'close': float(_first(table, 'f2')),
                        'change_pct': float(_first(table, 'f3'))  # f3 是涨跌幅
                    }

        # 查询创业板指数
        cyb_query = f"创业板指数{date}收盘价 涨跌幅"
        cyb_data = self._call_mx_data(cyb_query)

        if cyb_data and 'data' in cyb_data:
            search_result = cyb_data.get('data', {}).get('data', {}).get('searchDataResultDTO', {})
            tables = search_result.get('dataTableDTOList', [])
            if tables:
                table = tables[0].get('rawTable', {})
                if 'f2' in table and table['f2']:
                    result['cyb_index'] = {
                        'close': float(_first(table, 'f2')),
                        'change_pct': float(_first(table, 'f3'))
                    }

        return result

    def get_stock_history(
        self,
        stock_code: str,
        stock_name: str,
        days: int = 30
    ) -> List[Dict]:
        """
        获取股票历史行情数据

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            days: 查询天数

        Returns:
            [
                {
                    'date': '2026-04-28',
                    'close': 10.5,
                    'change_pct': 10.0,
                    'turnover': 15.5,
                    'volume': 1000000
                },
                ...
            ]
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        query = f"{stock_name}从{start_date.strftime('%Y年%m月%d日')}到{end_date.strftime('%Y年%m月%d日')}每日收盘价 涨跌幅 换手率 成交量"

        data = self._call_mx_data(query)

        result = []

        if data and 'data' in data:
            search_result = data.get('data', {}).get('data', {}).get('searchDataResultDTO', {})
            tables = search_result.get('dataTableDTOList', [])
            if tables:
                table = tables[0].get('rawTable', {})
                dates = table.get('headName', [])
                closes = table.get('f2', [])  # 收盘价
                change_pcts = table.get('f3', [])  # 涨跌幅
                turnovers = table.get('f8', [])  # 换手率
                volumes = table.get('f5', [])  # 成交量

                for i, date in enumerate(dates):
                    result.append({
                        'date': date,
                        'close': float(closes[i]) if i < len(closes) and closes[i] else 0,
                        'change_pct': float(change_pcts[i]) if i < len(change_pcts) and change_pcts[i] else 0,
                        'turnover': float(turnovers[i]) if i < len(turnovers) and turnovers[i] else 0,
                        'volume': float(volumes[i]) if i < len(volumes) and volumes[i] else 0
                    })

        return result

    def get_stock_realtime(self, stock_name: str) -> Dict:
        """
        获取股票实时行情

        Args:
            stock_name: 股票名称

        Returns:
            {
                'name': '东方财富',
                'code': '300059',
                'price': 10.5,
                'change_pct': 2.5,
                'turnover': 5.5,
                'volume': 1000000
            }
        """
        query = f"{stock_name}最新价 涨跌幅 换手率 成交量"

        data = self._call_mx_data(query)

        result = {}

        if data and 'data' in data:
            search_result = data.get('data', {}).get('data', {}).get('searchDataResultDTO', {})
            tables = search_result.get('dataTableDTOList', [])
            if tables:
                table_dto = tables[0]
                table = table_dto.get('rawTable', {})
                entity_tag = table_dto.get('entityTagDTO', {})

                result = {
                    'name': entity_tag.get('fullName', stock_name),
                    'code': entity_tag.get('secuCode', ''),
                    'price': float(_first(table, 'f2')),
                    'change_pct': float(_first(table, 'f3')),
                    'turnover': float(_first(table, 'f8')),  # f8 换手率
                    'volume': float(_first(table, 'f5'))  # f5 成交量
                }

        return result

    def get_sector_stocks(self, sector_name: str, date: str = "") -> List[Dict]:
        """
        获取板块成分股

        Args:
            sector_name: 板块名称
            date: 日期

        Returns:
            [
                {
                    'name': '东方财富',
                    'code': '300059',
                    'change_pct': 2.5
                },
                ...
            ]
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        query = f"{sector_name}板块{date}成分股涨跌幅"

        data = self._call_mx_data(query)

        result = []

        if data and 'data' in data:
            # 与其它方法对齐的正确路径：data.data.searchDataResultDTO.dataTableDTOList + rawTable
            search_result = data.get('data', {}).get('data', {}).get('searchDataResultDTO', {})
            tables = search_result.get('dataTableDTOList', [])
            for table_dto in tables:
                entity_tag = table_dto.get('entityTagDTO', {})
                table = table_dto.get('rawTable', {})

                result.append({
                    'name': entity_tag.get('fullName', ''),
                    'code': entity_tag.get('secuCode', ''),
                    'change_pct': float(_first(table, 'f3'))  # f3 涨跌幅
                })

        return result


def main():
    """测试函数"""
    client = DFCFData()

    # 测试获取指数数据
    print("=== 测试获取指数数据 ===")
    index_data = client.get_index_data()
    print(json.dumps(index_data, ensure_ascii=False, indent=2))

    # 测试获取股票实时行情
    print("\n=== 测试获取股票实时行情 ===")
    stock_data = client.get_stock_realtime("东方财富")
    print(json.dumps(stock_data, ensure_ascii=False, indent=2))

    # 测试获取股票历史数据
    print("\n=== 测试获取股票历史数据 ===")
    history = client.get_stock_history("300059", "东方财富", days=5)
    print(json.dumps(history[:5], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
