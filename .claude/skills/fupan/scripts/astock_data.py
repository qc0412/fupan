#!/usr/bin/env python3
"""
A股短线数据获取引擎 - 基于akshare
====================================
功能：涨跌停、连板天梯、板块强度、个股信息、资金流向、龙虎榜、北向资金

安全特性：
- 请求频率控制（随机间隔2-5秒）
- 自动重试（3次，指数退避）
- 本地缓存（按日期，当日有效）
- User-Agent轮换
- 错误降级（单源失败不影响整体）

使用方式：
  python3 astock_data.py --action zt_dt_summary --date 20260429
  python3 astock_data.py --action full_review --date 20260429
"""

from __future__ import annotations

import os
import sys
import json
import time
import random
import logging
import argparse
import hashlib
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Any

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("astock")

# ── 反爬虫配置 ──
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]

REQUEST_INTERVAL_MIN = 3.0   # 最小请求间隔(秒) - 从2秒增加到3秒
REQUEST_INTERVAL_MAX = 7.0   # 最大请求间隔(秒) - 从5秒增加到7秒
MAX_RETRIES = 3              # 最大重试次数
RETRY_BASE_DELAY = 8         # 重试基础延迟(秒) - 从5秒增加到8秒
MAX_DAILY_REQUESTS = 100     # 每日最大请求次数
MAX_CONSECUTIVE_FAILURES = 5 # 最大连续失败次数
COOLDOWN_PERIOD = 3600       # 冷却期(秒) - 1小时

# ── 缓存目录 ──
CACHE_DIR = Path(__file__).parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── 请求统计文件 ──
STATS_FILE = CACHE_DIR / "request_stats.json"


class AStockDataFetcher:
    """A股数据获取器 — 内置反爬虫保护与缓存机制"""

    def __init__(
        self,
        enable_cache: bool = True,
        request_interval: tuple = (REQUEST_INTERVAL_MIN, REQUEST_INTERVAL_MAX),
        max_retries: int = MAX_RETRIES,
    ):
        self.enable_cache = enable_cache
        self.request_interval = request_interval
        self.max_retries = max_retries
        self._request_count = 0
        self._last_request_time = 0.0
        self._consecutive_failures = 0
        self._init_akshare()
        self._load_stats()
        self._check_rate_limits()

    def _init_akshare(self):
        """延迟导入akshare，避免启动时加载过重"""
        try:
            global ak, pd
            import akshare as ak
            import pandas as pd
            log.info(f"✅ akshare v{ak.__version__} 加载成功")
        except ImportError:
            log.error("❌ 请先安装依赖: pip3 install akshare pandas numpy")
            raise

    # ════════════════════════════════════
    #  请求统计与限流保护
    # ════════════════════════════════════

    def _load_stats(self):
        """加载请求统计数据"""
        self._stats = {
            "date": date.today().isoformat(),
            "daily_requests": 0,
            "consecutive_failures": 0,
            "last_failure_time": None,
            "cooldown_until": None,
        }
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE, "r") as f:
                    saved = json.load(f)
                    # 如果是今天的数据，继承计数
                    if saved.get("date") == self._stats["date"]:
                        self._stats = saved
                    else:
                        # 新的一天，重置计数
                        self._save_stats()
            except Exception as e:
                log.warning(f"⚠️ 加载统计数据失败: {e}")

    def _save_stats(self):
        """保存请求统计数据"""
        try:
            with open(STATS_FILE, "w") as f:
                json.dump(self._stats, f, indent=2)
        except Exception as e:
            log.warning(f"⚠️ 保存统计数据失败: {e}")

    def _check_rate_limits(self):
        """检查是否触发限流保护"""
        # 检查冷却期
        if self._stats.get("cooldown_until"):
            cooldown_time = datetime.fromisoformat(self._stats["cooldown_until"])
            if datetime.now() < cooldown_time:
                remaining = (cooldown_time - datetime.now()).total_seconds()
                raise RuntimeError(
                    f"⛔ 触发保护机制：连续失败过多，请等待 {remaining/60:.1f} 分钟后再试"
                )
            else:
                # 冷却期结束，重置
                self._stats["cooldown_until"] = None
                self._stats["consecutive_failures"] = 0
                self._save_stats()

        # 检查每日请求上限
        if self._stats["daily_requests"] >= MAX_DAILY_REQUESTS:
            raise RuntimeError(
                f"⛔ 今日请求已达上限 ({MAX_DAILY_REQUESTS} 次)，请明天再试"
            )

    def _record_request(self, success: bool):
        """记录请求结果"""
        self._stats["daily_requests"] += 1

        if success:
            self._stats["consecutive_failures"] = 0
            self._consecutive_failures = 0
        else:
            self._stats["consecutive_failures"] += 1
            self._consecutive_failures += 1
            self._stats["last_failure_time"] = datetime.now().isoformat()

            # 连续失败过多，进入冷却期
            if self._stats["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                cooldown_until = datetime.now() + timedelta(seconds=COOLDOWN_PERIOD)
                self._stats["cooldown_until"] = cooldown_until.isoformat()
                log.error(
                    f"⛔ 连续失败 {MAX_CONSECUTIVE_FAILURES} 次，"
                    f"进入冷却期至 {cooldown_until.strftime('%H:%M:%S')}"
                )

        self._save_stats()

    # ════════════════════════════════════
    #  反爬虫保护层
    # ════════════════════════════════════

    def _get_random_headers(self) -> dict:
        """生成随机请求头"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _rate_limit(self):
        """请求频率控制"""
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = random.uniform(*self.request_interval)
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed + random.uniform(0, 1)
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _safe_call(self, func_name: str, func, *args, **kwargs) -> Any:
        """
        安全调用akshare API，带重试和错误处理

        Returns:
            DataFrame 或 dict 或 None
        """
        # 检查限流
        self._check_rate_limits()

        self._rate_limit()
        self._request_count += 1

        # 注入随机请求头（如果akshare支持）
        headers = self._get_random_headers()
        if "headers" in kwargs:
            kwargs["headers"].update(headers)

        for attempt in range(self.max_retries):
            try:
                log.info(f"📡 [{self._request_count}] 调用 {func_name} ...")
                result = func(*args, **kwargs)
                if result is not None and len(result) > 0:
                    log.info(f"  ✅ 成功: {len(result)} 条记录")
                    self._record_request(success=True)
                    return result
                else:
                    log.warning(f"  ⚠️ 返回空数据")
                    self._record_request(success=True)  # 空数据也算成功
                    return result
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = any(
                    kw in error_str for kw in ["429", "503", "too many", "限流", "频繁", "timeout", "blocked"]
                )

                if is_rate_limit and attempt < self.max_retries - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 5)
                    log.warning(
                        f"  ⚠️ 触发限流({func_name}), 等待 {delay:.1f}s 后重试 "
                        f"({attempt+1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                elif attempt < self.max_retries - 1:
                    delay = RETRY_BASE_DELAY + random.uniform(0, 3)
                    log.warning(
                        f"  ❌ 异常: {e}, {delay:.1f}s后重试 ({attempt+1}/{self.max_retries})"
                    )
                    time.sleep(delay)
                else:
                    log.error(f"  ❌ {func_name} 最终失败: {e}")
                    self._record_request(success=False)
                    return None

        return None

    # ════════════════════════════════════
    #  缓存层
    # ════════════════════════════════════

    def _cache_key(self, action: str, **params) -> str:
        raw = f"{action}:{json.dumps(params, sort_keys=True)}"
        today_str = date.today().isoformat()
        return f"{today_str}_{hashlib.md5(raw.encode()).hexdigest()[:12]}"

    def _get_cache(self, cache_key: str) -> Optional[dict]:
        if not self.enable_cache:
            return None
        path = CACHE_DIR / f"{cache_key}.json"
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime).date()
            if mtime == date.today():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    log.info(f"💾 缓存命中: {cache_key[:20]}...")
                    return data
        return None

    def _set_cache(self, cache_key: str, data: Any):
        if not self.enable_cache:
            return
        path = CACHE_DIR / f"{cache_key}.json"
        # 转换DataFrame为dict以便JSON序列化
        if hasattr(data, "to_dict"):
            data = {"_type": "dataframe", "data": data.to_dict("records")}
        elif isinstance(data, dict):
            pass
        else:
            data = {"_type": "raw", "data": str(data)}

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        log.info(f"💾 已缓存: {cache_key[:20]}...")

    # ════════════════════════════════════
    #  数据格式化工具
    # ════════════════════════════════════

    @staticmethod
    def _df_to_records(df) -> list[dict]:
        """DataFrame转list of dict"""
        if df is None or (hasattr(df, "__len__") and len(df) == 0):
            return []
        if hasattr(df, "to_dict"):
            return df.to_dict("records")
        return list(df)

    @staticmethod
    def _safe_float(val, default=0.0) -> float:
        """安全转换为float"""
        try:
            v = float(val)
            return v if v == v else default  # 排除NaN
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(val, default=0) -> int:
        """安全转换为int"""
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _format_date(date_input: str | date | None = None) -> str:
        """格式化日期为YYYYMMDD或YYYY-MM-DD"""
        if date_input is None:
            return datetime.now().strftime("%Y%m%d")
        if isinstance(date_input, date):
            return date_input.strftime("%Y%m%d")
        s = str(date_input).replace("-", "")
        return s

    # ════════════════════════════════════
    #  核心：各功能API封装
    # ════════════════════════════════════

    def get_zt_dt_summary(self, date_str: str | None = None) -> dict:
        """
        涨跌停统计汇总
        
        Returns:
            {
                "date", "zt_count", "dt_count", "zab_count",
                "zt_count_yesterday", "lianban_count", "max_lianban",
                "zab_rate", "try_zt_total"
            }
        """
        date_str = self._format_date(date_str)
        cache_key = self._cache_key("zt_dt_summary", date=date_str)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {
            "date": date_str,
            "zt_count": 0,
            "dt_count": 0,
            "zab_count": 0,
            "zt_count_yesterday": 0,
            "lianban_count": 0,
            "max_lianban": 0,
            "zab_rate": 0.0,
            "try_zt_total": 0,
        }

        try:
            # 1. 今日涨停池（不含ST/退市）
            zt_df = self._safe_call(
                "stock_zt_pool_em", ak.stock_zt_pool_em, date=date_str
            )
            if zt_df is not None and len(zt_df) > 0:
                records = self._df_to_records(zt_df)
                result["zt_count"] = len(records)
                # 统计连板
                lianban_list = [r for r in records if self._safe_int(r.get("连板数")) > 1]
                result["lianban_count"] = len(lianban_list)
                heights = [self._safe_int(r.get("连板数")) for r in lianban_list]
                result["max_lianban"] = max(heights) if heights else 0
                # 记录涨停池明细供后续分析
                result["_zt_detail"] = records

            # 2. 今日跌停池
            dt_df = self._safe_call(
                "stock_zt_pool_dtgc_em", ak.stock_zt_pool_dtgc_em, date=date_str
            )
            if dt_df is not None and len(dt_df) > 0:
                result["dt_count"] = len(dt_df)

            # 3. 炸板池
            zab_df = self._safe_call(
                "stock_zt_pool_zbgc_em", ak.stock_zt_pool_zbgc_em, date=date_str
            )
            if zab_df is not None and len(zab_df) > 0:
                result["zab_count"] = len(zab_df)

            # 4. 昨日涨停（用于计算昨日反馈）
            yesterday = (
                datetime.strptime(date_str, "%Y%m%d") - timedelta(days=1)
            ).strftime("%Y%m%d")
            yest_zt_df = self._safe_call(
                "stock_zt_pool_previous_em", ak.stock_zt_pool_previous_em, date=yesterday
            )
            if yest_zt_df is not None and len(yest_zt_df) > 0:
                result["zt_count_yesterday"] = len(yest_zt_df)

            # 计算衍生指标
            result["try_zt_total"] = result["zt_count"] + result["zab_count"]
            if result["try_zt_total"] > 0:
                result["zab_rate"] = round(
                    result["zab_count"] / result["try_zt_total"] * 100, 1
                )

        except Exception as e:
            log.error(f"❌ 涨跌停统计异常: {e}")

        self._set_cache(cache_key, result)
        return result

    def get_lianban_ladder(self, date_str: str | None = None) -> dict:
        """
        连板天梯 - 获取全部连板股并按高度分组
        
        Returns:
            {
                "date", "ladder": {高度: [股票列表]},
                "summary": {total_lianban, max_height, ...}
            }
        """
        date_str = self._format_date(date_str)
        cache_key = self._cache_key("lianban_ladder", date=date_str)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {
            "date": date_str,
            "ladder": {},
            "summary": {},
        }

        try:
            # 使用主涨停池（有连板数字段），强势股池无连板数
            zt_df = self._safe_call(
                "stock_zt_pool_em", ak.stock_zt_pool_em, date=date_str
            )
            if zt_df is not None and len(zt_df) > 0:
                records = self._df_to_records(zt_df)
                ladder = {}
                all_heights = set()

                for r in records:
                    # 优先使用连板数，其次从涨停统计解析（格式如 "2/2"）
                    height = self._safe_int(r.get("连板数"))
                    if height <= 0:
                        stats = str(r.get("涨停统计", "")).strip()
                        if "/" in stats:
                            try:
                                height = int(stats.split("/")[0])
                            except (ValueError, IndexError):
                                height = 0
                    if height >= 1:
                        all_heights.add(height)
                        height_key = f"{height}板"
                        stock_info = {
                            "code": r.get("代码", ""),
                            "name": r.get("名称", ""),
                            "height": height,
                            "chg_pct": self._safe_float(r.get("涨跌幅")),
                            "turnover": self._safe_float(r.get("换手率")),
                            "amount": self._safe_float(r.get("成交额", 0)) / 1e8,
                            "latest_price": self._safe_float(r.get("最新价")),
                            "zt_price": self._safe_float(r.get("最新价", 0)),  # 涨停池无单独涨停价字段，用最新价近似
                            "seal_capital": self._safe_float(r.get("封板资金", 0)) / 1e4,  # 万元→亿
                            "zab_count": self._safe_int(r.get("炸板次数")),
                            "first_seal_time": r.get("首次封板时间", ""),
                            "board_pattern": self._classify_board_pattern_zt(r),
                            "sector": r.get("所属行业", ""),
                        }
                        ladder.setdefault(height_key, []).append(stock_info)

                # 按高度降序排列
                sorted_ladder = dict(
                    sorted(ladder.items(), key=lambda x: int(x[0].replace("板", "")), reverse=True)
                )
                result["ladder"] = sorted_ladder

                # 统计摘要
                total_lianban = sum(1 for stocks in sorted_ladder.values() for s in stocks if s["height"] > 1)
                yizi_count = sum(
                    1 for stocks in sorted_ladder.values() for s in stocks if s["board_pattern"] == "一字板"
                )
                lanban_count = sum(
                    1 for stocks in sorted_ladder.values() for s in stocks if s["board_pattern"] == "烂板"
                )

                result["summary"] = {
                    "total_lianban": total_lianban,
                    "max_height": max(all_heights) if all_heights else 0,
                    "yizi_count": yizi_count,
                    "lanban_count": lanban_count,
                    "height_distribution": {k: len(v) for k, v in sorted_ladder.items()},
                }

        except Exception as e:
            log.error(f"❌ 连板天梯异常: {e}")

        self._set_cache(cache_key, result)
        return result

    def get_sector_ranking(self, date_str: str | None = None) -> dict:
        """
        板块强度排行（概念板块 + 行业板块）
        
        Returns:
            {
                "concept_top10", "industry_top10", "main_theme_analysis"
            }
        """
        date_str = self._format_date(date_str)
        cache_key = self._cache_key("sector_ranking", date=date_str)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {"concept_top10": [], "industry_top10": [], "main_theme_analysis": {}}

        try:
            # 1. 概念板块实时行情
            concept_df = self._safe_call(
                "stock_board_concept_spot_em", ak.stock_board_concept_spot_em
            )
            if concept_df is not None and len(concept_df) > 0:
                records = self._df_to_records(concept_df)
                # 按涨幅排序取前10
                records.sort(key=lambda x: self._safe_float(x.get("涨幅")), reverse=True)
                result["concept_top10"] = [
                    {
                        "rank": i + 1,
                        "name": r.get("板块名称", ""),
                        "chg_pct": self._safe_float(r.get("涨幅")),
                        "turnover": self._safe_float(r.get("换手率")),
                        "zt_count": self._safe_int(r.get("上涨家数", 0)),
                        "dt_count": self._safe_int(r.get("下跌家数", 0)),
                        "lead_stock": r.get("领涨股票", ""),
                        "lead_chg": self._safe_float(r.get("领涨股票-涨跌幅")),
                    }
                    for i, r in enumerate(records[:10])
                ]

            # 2. 行业板块排行（字段: 板块/涨跌幅/总成交额 等）
            industry_df = self._safe_call(
                "stock_sector_spot", ak.stock_sector_spot
            )
            if industry_df is not None and len(industry_df) > 0:
                records = self._df_to_records(industry_df)
                # stock_sector_spot 字段: 板块, 涨跌幅, 总成交额, 公司家数
                records.sort(key=lambda x: self._safe_float(x.get("涨跌幅")), reverse=True)
                result["industry_top10"] = [
                    {
                        "rank": i + 1,
                        "name": r.get("板块", "") or r.get("label", ""),
                        "chg_pct": self._safe_float(r.get("涨跌幅")),
                        "amount": self._safe_float(r.get("总成交额", 0)) / 1e8,
                        "company_count": self._safe_int(r.get("公司家数")),
                        "lead_stock": r.get("股票名称", ""),
                    }
                    for i, r in enumerate(records[:10])
                ]

            # 3. 板块资金流向排名
            fund_rank_df = self._safe_call(
                "stock_sector_fund_flow_rank", ak.stock_sector_fund_flow_rank
            )
            if fund_rank_df is not None and len(fund_rank_df) > 0:
                fund_records = self._df_to_records(fund_rank_df)[:10]
                result["fund_flow_top"] = [
                    {
                        "name": r.get("名称", ""),
                        "net_inflow": self._safe_float(r.get("主力净流入-净额", 0)) / 1e8,
                        "pct_change": self._safe_float(r.get("主力净流入-净占比")),
                    }
                    for r in fund_records
                ]

        except Exception as e:
            log.error(f"❌ 板块排行异常: {e}")

        self._set_cache(cache_key, result)
        return result

    def get_stock_info(self, code: str) -> dict:
        """
        个股深度查询
        
        Args:
            code: 股票代码如 "000001"
        
        Returns:
            个股完整信息字典
        """
        cache_key = self._cache_key("stock_info", code=code)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {
            "code": code,
            "name": "",
            "price": 0.0,
            "chg_pct": 0.0,
            "is_zt": False,
            "consecutive_boards": 0,
        }

        try:
            # 1. 个股基本信息 + 实时行情
            info_df = self._safe_call(
                "stock_individual_info_em",
                ak.stock_individual_info_em,
                symbol=code,
            )
            if info_df is not None and len(info_df) > 0:
                info = self._df_to_records(info_df)[0]
                result.update({
                    "name": info.get("股票名称", ""),
                    "price": self._safe_float(info.get("最新价")),
                    "chg_pct": self._safe_float(info.get("涨跌幅")),
                    "open": self._safe_float(info.get("今开")),
                    "high": self._safe_float(info.get("最高")),
                    "low": self._safe_float(info.get("最低")),
                    "volume": self._safe_float(info.get("成交量")),
                    "amount": self._safe_float(info.get("成交额", 0)) / 1e8,
                    "turnover": self._safe_float(info.get("换手率")),
                    "volume_ratio": self._safe_float(info.get("量比")),
                    "amplitude": self._safe_float(info.get("振幅")),
                    "pe_ttm": self._safe_float(info.get("市盈率-动态")),
                    "pb": self._safe_float(info.get("市净率")),
                    "total_mv": self._safe_float(info.get("总市值", 0)) / 1e8,
                    "circ_mv": self._safe_float(info.get("流通市值", 0)) / 1e8,
                    "sector_industry": info.get("行业", ""),
                    "sector_concept": info.get("概念", ""),
                })
                result["is_zt"] = result["chg_pct"] >= 9.85

            # 2. 历史K线（近30日，用于计算均线）
            hist_df = self._safe_call(
                "stock_zh_a_hist",
                ak.stock_zh_a_hist,
                symbol=code,
                period="daily",
                start_date=(datetime.now() - timedelta(days=60)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq",
            )
            if hist_df is not None and len(hist_df) > 0:
                hist = self._df_to_records(hist_df)
                closes = [self._safe_float(h.get("收盘")) for h in hist]
                result["_hist_close"] = closes[-30:]  # 最近30日

                # 计算均线
                if len(closes) >= 20:
                    result["ma5"] = round(sum(closes[-5:]) / 5, 2)
                    result["ma10"] = round(sum(closes[-10:]) / 10, 2)
                    result["ma20"] = round(sum(closes[-20:]) / 20, 2)
                if len(closes) >= 60:
                    result["ma60"] = round(sum(closes[-60:]) / 60, 2)

                # 近期涨停记录检测
                recent_zt = [
                    h for h in hist[-10:]
                    if self._safe_float(h.get("涨跌幅", h.get("pct_chg", 0))) >= 9.5
                ]
                result["recent_zt_days"] = len(recent_zt)

            # 3. 个股资金流向
            fund_df = self._safe_call(
                "stock_individual_fund_flow",
                ak.stock_individual_fund_flow,
                stock=code,
                market="sh" if code.startswith("6") else "sz",
            )
            if fund_df is not None and len(fund_df) > 0:
                fund = self._df_to_records(fund_df)[0]
                result["fund_flow"] = {
                    "main_net": round(self._safe_float(fund.get("主力净流入-净额", 0)) / 1e4, 2),
                    "super_large_net": round(self._safe_float(fund.get("超大单净流入-净额", 0)) / 1e4, 2),
                    "large_net": round(self._safe_float(fund.get("大单净流入-净额", 0)) / 1e4, 2),
                    "medium_net": round(self._safe_float(fund.get("中单净流入-净额", 0)) / 1e4, 2),
                    "small_net": round(self._safe_float(fund.get("小单净流入-净额", 0)) / 1e4, 2),
                }

        except Exception as e:
            log.error(f"❌ 个股查询异常(code={code}): {e}")

        self._set_cache(cache_key, result)
        return result

    def get_fund_flow(
        self,
        flow_type: str = "individual",
        code: str | None = None,
        date_str: str | None = None,
    ) -> dict:
        """
        资金流向查询
        
        Args:
            flow_type: individual(个股) / concept(概念) / industry(行业) / market(全市场)
            code: 个股代码（individual模式必填）
            date_str: 日期
        """
        date_str = self._format_date(date_str)
        cache_key = self._cache_key("fund_flow", type=flow_type, code=code or "", date=date_str)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {"type": flow_type, "date": date_str}

        try:
            if flow_type == "individual":
                if not code:
                    raise ValueError("个股资金流需要code参数")
                stock_info = self.get_stock_info(code)
                result = stock_info.get("fund_flow", {})
                result["stock_name"] = stock_info.get("name", "")
                result["stock_code"] = code

            elif flow_type == "concept":
                df = self._safe_call(
                    "stock_fund_flow_concept", ak.stock_fund_flow_concept
                )
                if df is not None and len(df) > 0:
                    records = self._df_to_records(df)[:20]
                    result["top_inflow"] = [
                        {
                            "name": r.get("名称", ""),
                            "net_in": round(self._safe_float(r.get("主力净流入-净额", 0)) / 1e8, 2),
                            "pct": round(self._safe_float(r.get("主力净流入-净占比", 0)), 2),
                        }
                        for r in records[:10]
                    ]
                    result["top_outflow"] = sorted(
                        records, key=lambda x: self._safe_float(x.get("主力净流入-净额", 0))
                    )[:10]

            elif flow_type == "industry":
                df = self._safe_call(
                    "stock_fund_flow_industry", ak.stock_fund_flow_industry
                )
                if df is not None and len(df) > 0:
                    records = self._df_to_records(df)[:20]
                    result["ranking"] = [
                        {
                            "name": r.get("名称", ""),
                            "net_in": round(self._safe_float(r.get("主力净流入-净额", 0)) / 1e8, 2),
                            "pct": round(self._safe_float(r.get("主力净流入-净占比", 0)), 2),
                        }
                        for r in records[:15]
                    ]

            elif flow_type == "market":
                df = self._safe_call(
                    "stock_market_fund_flow", ak.stock_market_fund_flow
                )
                if df is not None and len(df) > 0:
                    records = self._df_to_records(df)
                    if records:
                        latest = records[0]
                        result = {
                            "date": latest.get("日期", date_str),
                            "main_net_in": round(self._safe_float(latest.get("主力净流入-净额", 0)) / 1e8, 2),
                            "super_large": round(self._safe_float(latest.get("超大单净流入-净额", 0)) / 1e8, 2),
                            "large": round(self._safe_float(latest.get("大单净流入-净额", 0)) / 1e8, 2),
                            "medium": round(self._safe_float(latest.get("中单净流入-净额", 0)) / 1e8, 2),
                            "small": round(self._safe_float(latest.get("小单净流入-净额", 0)) / 1e8, 2),
                        }

        except Exception as e:
            log.error(f"❌ 资金流向异常: {e}")

        self._set_cache(cache_key, result)
        return result

    def get_lhb_data(self, date_str: str | None = None) -> dict:
        """
        龙虎榜数据
        
        Returns:
            上榜个股、机构买卖汇总、席位统计
        """
        date_str = self._format_date(date_str)
        cache_key = self._cache_key("lhb", date=date_str)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {"date": date_str, "lhb_stocks": [], "institution_summary": {}, "top_seats": {}}

        try:
            # 1. 龙虎榜详情
            lhb_df = self._safe_call(
                "stock_lhb_detail_em", ak.stock_lhb_detail_em, date=date_str
            )
            if lhb_df is not None and len(lhb_df) > 0:
                records = self._df_to_records(lhb_df)
                result["lhb_stocks"] = [
                    {
                        "code": r.get("代码", ""),
                        "name": r.get("名称", ""),
                        "chg_pct": self._safe_float(r.get("涨跌幅", r.get("close_pct"))),
                        "reason": r.get("上榜原因", ""),
                        "buy_total": self._safe_float(r.get("买入总额", 0)) / 1e8,
                        "sell_total": self._safe_float(r.get("卖出总额", 0)) / 1e8,
                        "net_buy": round(
                            self._safe_float(r.get("买入总额", 0))
                            - self._safe_float(r.get("卖出总额", 0)), 2
                        )
                        / 1e8,
                        "turnover_pct": self._safe_float(r.get("成交额", 0))
                        / max(self._safe_float(r.get("总成交额", 0)), 1) * 100
                        if self._safe_float(r.get("总成交额", 0)) > 0
                        else 0,
                    }
                    for r in records
                ]

            # 2. 机构席位统计
            inst_df = self._safe_call(
                "stock_lhb_jgstatistic_em", ak.stock_lhb_jgstatistic_em, date=date_str
            )
            if inst_df is not None and len(inst_df) > 0:
                inst = self._df_to_records(inst_df)[0]
                result["institution_summary"] = {
                    "buy_total": round(self._safe_float(inst.get("机构买入总额", 0)) / 1e8, 2),
                    "sell_total": round(self._safe_float(inst.get("机构卖出总额", 0)) / 1e8, 2),
                    "net_buy": round(
                        self._safe_float(inst.get("机构买入总额", 0))
                        - self._safe_float(inst.get("机构卖出总额", 0)),
                        2,
                    )
                    / 1e8,
                    "buy_count": self._safe_int(inst.get("机构买入家数")),
                    "sell_count": self._safe_int(inst.get("机构卖出家数")),
                }

            # 3. 营业部排名（游资动向）
            yyb_df = self._safe_call(
                "stock_lhb_yybph_em", ak.stock_lhb_yybph_em, date=date_str
            )
            if yyb_df is not None and len(yyb_df) > 0:
                records = self._df_to_records(yyb_df)
                result["top_seats"] = {
                    "top_buy": [
                        {"seat": r.get("营业部名称", ""), "buy_amount": round(self._safe_float(r.get("买入金额", 0)) / 1e8, 2)}
                        for r in records[:5]
                    ],
                    "top_sell": sorted(
                        records,
                        key=lambda x: self._safe_float(x.get("卖出金额", 0)),
                        reverse=True,
                    )[:5],
                }

        except Exception as e:
            log.error(f"❌ 龙虎榜异常: {e}")

        self._set_cache(cache_key, result)
        return result

    def get_north_bound(self, date_str: str | None = None) -> dict:
        """
        北向资金（沪深港通）
        
        Returns:
            净买入、买卖总额、历史趋势
        """
        date_str = self._format_date(date_str)
        cache_key = self._cache_key("north_bound", date=date_str)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {"date": date_str}

        try:
            df = self._safe_call(
                "stock_hsgt_fund_flow_summary_em",
                ak.stock_hsgt_fund_flow_summary_em,
            )
            if df is not None and len(df) > 0:
                records = self._df_to_records(df)
                if records:
                    latest = records[0]  # 最新一天
                    result.update({
                        "date": latest.get("日期", date_str),
                        "net_buy_in": round(self._safe_float(latest.get("当日净流入", 0)) / 1e4, 2),  # 万元→亿元近似
                        "historical_5d": [
                            {
                                "d": r.get("日期", ""),
                                "net": round(self._safe_float(r.get("当日净流入", 0)) / 1e4, 2),
                            }
                            for r in records[:6]
                        ],
                    })

        except Exception as e:
            log.error(f"❌ 北向资金异常: {e}")

        self._set_cache(cache_key, result)
        return result

    def get_stock_lianban_history(
        self, code: str, start_date: str | None = None, end_date: str | None = None
    ) -> dict:
        """
        个股连板历史分析 - 获取个股的完整连板周期

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYYMMDD)，默认最近30天
            end_date: 结束日期 (YYYYMMDD)，默认今天

        Returns:
            {
                "code": "603318",
                "name": "水发燃气",
                "lianban_cycles": [
                    {
                        "cycle_id": 1,
                        "start_date": "20260410",
                        "end_date": "20260418",
                        "max_boards": 8,
                        "days": 9,
                        "daily_records": [
                            {"date": "20260410", "boards": 1, "time": "09:32", "turnover": 12.5, ...},
                            ...
                        ],
                        "is_broken": False,  # 是否中途炸板
                        "broken_dates": []
                    }
                ],
                "summary": {
                    "total_cycles": 2,
                    "max_boards_ever": 8,
                    "recent_zt_count": 10
                }
            }
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        cache_key = self._cache_key("stock_lianban_history", code=code, start=start_date, end=end_date)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {
            "code": code,
            "name": "",
            "lianban_cycles": [],
            "summary": {}
        }

        try:
            # 获取个股基本信息
            stock_info = self.get_stock_info(code)
            result["name"] = stock_info.get("name", "")

            # 遍历日期范围，查询每天的涨停池
            all_zt_records = []
            current = datetime.strptime(start_date, "%Y%m%d")
            end = datetime.strptime(end_date, "%Y%m%d")

            while current <= end:
                date_str = current.strftime("%Y%m%d")
                try:
                    zt_data = self.get_zt_dt_summary(date_str)
                    zt_detail = zt_data.get("_zt_detail", [])

                    # 查找目标股票
                    target = [s for s in zt_detail if s.get("代码") == code]
                    if target:
                        record = target[0]
                        all_zt_records.append({
                            "date": date_str,
                            "boards": self._safe_int(record.get("连板数", 1)),
                            "time": record.get("首次封板时间", ""),
                            "turnover": self._safe_float(record.get("换手率")),
                            "open_times": self._safe_int(record.get("打开次数", 0)),
                            "sector": record.get("所属行业", ""),
                            "chg_pct": self._safe_float(record.get("涨跌幅"))
                        })
                except Exception as e:
                    log.debug(f"查询 {date_str} 数据失败: {e}")

                current += timedelta(days=1)

            # 分析连板周期
            if all_zt_records:
                cycles = []
                current_cycle = None

                for i, record in enumerate(all_zt_records):
                    boards = record["boards"]

                    # 首板或连板中断，开始新周期
                    if boards == 1 or (current_cycle and boards != current_cycle["max_boards"] + 1):
                        if current_cycle:
                            cycles.append(current_cycle)
                        current_cycle = {
                            "cycle_id": len(cycles) + 1,
                            "start_date": record["date"],
                            "end_date": record["date"],
                            "max_boards": boards,
                            "days": 1,
                            "daily_records": [record],
                            "is_broken": False,
                            "broken_dates": []
                        }
                    else:
                        # 连板延续
                        current_cycle["end_date"] = record["date"]
                        current_cycle["max_boards"] = max(current_cycle["max_boards"], boards)
                        current_cycle["days"] += 1
                        current_cycle["daily_records"].append(record)

                        # 检测炸板（打开次数>0）
                        if record["open_times"] > 0:
                            current_cycle["is_broken"] = True
                            current_cycle["broken_dates"].append(record["date"])

                # 添加最后一个周期
                if current_cycle:
                    cycles.append(current_cycle)

                result["lianban_cycles"] = cycles
                result["summary"] = {
                    "total_cycles": len(cycles),
                    "max_boards_ever": max([c["max_boards"] for c in cycles]) if cycles else 0,
                    "recent_zt_count": len(all_zt_records)
                }

        except Exception as e:
            log.error(f"❌ 个股连板历史分析异常(code={code}): {e}")

        self._set_cache(cache_key, result)
        return result

    def get_sector_timeline_analysis(
        self, sector_name: str, start_date: str | None = None, end_date: str | None = None
    ) -> dict:
        """
        板块龙头时间线分析 - 识别首波龙头和补涨龙

        Args:
            sector_name: 板块名称（如"燃气Ⅱ"、"电池"）
            start_date: 开始日期 (YYYYMMDD)，默认最近30天
            end_date: 结束日期 (YYYYMMDD)，默认今天

        Returns:
            {
                "sector": "燃气Ⅱ",
                "leaders": [
                    {
                        "code": "603318",
                        "name": "水发燃气",
                        "first_board_date": "20260420",
                        "last_board_date": "20260428",
                        "max_boards": 8,
                        "leader_type": "首波龙头",  # 首波龙头/补涨龙/二波龙
                        "is_active": True  # 是否仍在连板中
                    }
                ],
                "timeline": "首波龙头开板后，补涨龙启动",
                "first_leader": {"code": "603318", "name": "水发燃气", "start": "20260420"}
            }
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        cache_key = self._cache_key("sector_timeline", sector=sector_name, start=start_date, end=end_date)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {
            "sector": sector_name,
            "leaders": [],
            "timeline": "",
            "first_leader": None
        }

        try:
            # 收集板块内所有涨停股票
            sector_stocks = {}
            current = datetime.strptime(start_date, "%Y%m%d")
            end = datetime.strptime(end_date, "%Y%m%d")

            while current <= end:
                date_str = current.strftime("%Y%m%d")
                try:
                    zt_data = self.get_zt_dt_summary(date_str)
                    zt_detail = zt_data.get("_zt_detail", [])

                    # 筛选同板块股票
                    sector_zt = [s for s in zt_detail if sector_name in s.get("所属行业", "")]

                    for stock in sector_zt:
                        code = stock.get("代码")
                        if code not in sector_stocks:
                            sector_stocks[code] = {
                                "code": code,
                                "name": stock.get("名称"),
                                "first_board_date": date_str,
                                "last_board_date": date_str,
                                "max_boards": self._safe_int(stock.get("连板数", 1)),
                                "zt_dates": [date_str]
                            }
                        else:
                            sector_stocks[code]["last_board_date"] = date_str
                            sector_stocks[code]["max_boards"] = max(
                                sector_stocks[code]["max_boards"],
                                self._safe_int(stock.get("连板数", 1))
                            )
                            sector_stocks[code]["zt_dates"].append(date_str)

                except Exception as e:
                    log.debug(f"查询 {date_str} 数据失败: {e}")

                current += timedelta(days=1)

            # 按首板日期排序
            leaders = sorted(sector_stocks.values(), key=lambda x: x["first_board_date"])

            # 判断龙头类型
            if leaders:
                first_leader = leaders[0]
                result["first_leader"] = {
                    "code": first_leader["code"],
                    "name": first_leader["name"],
                    "start": first_leader["first_board_date"]
                }

                # 推测首波龙头开板日期（最后涨停日期+1天）
                first_end_date = datetime.strptime(first_leader["last_board_date"], "%Y%m%d")
                first_open_date = (first_end_date + timedelta(days=1)).strftime("%Y%m%d")

                for leader in leaders:
                    leader_type = "首波龙头" if leader == first_leader else "未知"

                    # 判断是否为补涨龙（首波龙头开板后1-3天内启动）
                    if leader != first_leader:
                        start_date_obj = datetime.strptime(leader["first_board_date"], "%Y%m%d")
                        open_date_obj = datetime.strptime(first_open_date, "%Y%m%d")
                        days_diff = (start_date_obj - open_date_obj).days

                        if -1 <= days_diff <= 3:
                            leader_type = "补涨龙"
                        elif days_diff > 10:
                            leader_type = "二波龙"

                    # 判断是否仍在连板中
                    last_date = datetime.strptime(leader["last_board_date"], "%Y%m%d")
                    today = datetime.strptime(end_date, "%Y%m%d")
                    is_active = (today - last_date).days <= 1

                    leader["leader_type"] = leader_type
                    leader["is_active"] = is_active
                    result["leaders"].append(leader)

                # 生成时间线描述
                补涨龙_count = len([l for l in leaders if l["leader_type"] == "补涨龙"])
                if 补涨龙_count > 0:
                    result["timeline"] = f"首波龙头 {first_leader['name']} 于 {first_leader['first_board_date']} 启动，{first_open_date} 开板后出现 {补涨龙_count} 只补涨龙"
                else:
                    result["timeline"] = f"首波龙头 {first_leader['name']} 于 {first_leader['first_board_date']} 启动，暂无补涨龙"

        except Exception as e:
            log.error(f"❌ 板块时间线分析异常(sector={sector_name}): {e}")

        self._set_cache(cache_key, result)
        return result

    def get_concept_detail(self, concept_name: str) -> dict:
        """
        概念板块深度分析

        Args:
            concept_name: 概念名称（如"人工智能"、"华为概念"）

        Returns:
            {
                "concept": "人工智能",
                "stocks": [成分股列表],
                "leader": {龙头股信息},
                "fund_flow": {资金流向},
                "strength": {板块强度指标}
            }
        """
        cache_key = self._cache_key("concept_detail", concept=concept_name)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {
            "concept": concept_name,
            "stocks": [],
            "leader": {},
            "fund_flow": {},
            "strength": {}
        }

        try:
            # 1. 获取概念成分股
            cons_df = self._safe_call(
                "stock_board_concept_cons_em",
                ak.stock_board_concept_cons_em,
                symbol=concept_name
            )

            if cons_df is not None and len(cons_df) > 0:
                stocks = self._df_to_records(cons_df)
                result["stocks"] = [
                    {
                        "code": s.get("代码", ""),
                        "name": s.get("名称", ""),
                        "chg_pct": self._safe_float(s.get("涨跌幅")),
                        "price": self._safe_float(s.get("最新价")),
                        "turnover": self._safe_float(s.get("换手率"))
                    }
                    for s in stocks[:50]  # 限制50只
                ]

                # 找出龙头（涨幅最大且成交额靠前）
                if stocks:
                    sorted_stocks = sorted(
                        stocks,
                        key=lambda x: (self._safe_float(x.get("涨跌幅")), self._safe_float(x.get("成交额", 0))),
                        reverse=True
                    )
                    leader = sorted_stocks[0]
                    result["leader"] = {
                        "code": leader.get("代码", ""),
                        "name": leader.get("名称", ""),
                        "chg_pct": self._safe_float(leader.get("涨跌幅")),
                        "amount": self._safe_float(leader.get("成交额", 0)) / 1e8
                    }

            # 2. 获取概念板块资金流向
            fund_df = self._safe_call(
                "stock_fund_flow_concept", ak.stock_fund_flow_concept
            )

            if fund_df is not None and len(fund_df) > 0:
                fund_records = self._df_to_records(fund_df)
                target_fund = [f for f in fund_records if f.get("名称") == concept_name]
                if target_fund:
                    fund = target_fund[0]
                    result["fund_flow"] = {
                        "main_net": round(self._safe_float(fund.get("主力净流入-净额", 0)) / 1e8, 2),
                        "main_pct": round(self._safe_float(fund.get("主力净流入-净占比", 0)), 2),
                        "super_large": round(self._safe_float(fund.get("超大单净流入-净额", 0)) / 1e8, 2),
                        "large": round(self._safe_float(fund.get("大单净流入-净额", 0)) / 1e8, 2)
                    }

            # 3. 板块强度指标
            concept_df = self._safe_call(
                "stock_board_concept_spot_em", ak.stock_board_concept_spot_em
            )

            if concept_df is not None and len(concept_df) > 0:
                concept_records = self._df_to_records(concept_df)
                target_concept = [c for c in concept_records if c.get("板块名称") == concept_name]
                if target_concept:
                    concept = target_concept[0]
                    result["strength"] = {
                        "chg_pct": self._safe_float(concept.get("涨幅")),
                        "turnover": self._safe_float(concept.get("换手率")),
                        "up_count": self._safe_int(concept.get("上涨家数")),
                        "down_count": self._safe_int(concept.get("下跌家数")),
                        "zt_count": self._safe_int(concept.get("涨停家数", 0))
                    }

        except Exception as e:
            log.error(f"❌ 概念板块分析异常(concept={concept_name}): {e}")

        self._set_cache(cache_key, result)
        return result

    def get_technical_indicators(self, code: str, period: int = 60) -> dict:
        """
        技术指标分析 - 用于二波龙判断

        Args:
            code: 股票代码
            period: 分析周期（天数），默认60天

        Returns:
            {
                "code": "603318",
                "name": "水发燃气",
                "ma": {"ma5": 10.5, "ma10": 10.2, "ma20": 9.8, "ma60": 9.5},
                "macd": {"dif": 0.12, "dea": 0.08, "macd": 0.04, "signal": "金叉"},
                "kdj": {"k": 65, "d": 60, "j": 75, "signal": "超买"},
                "volume": {
                    "recent_avg": 1000000,  # 近5日均量
                    "today_ratio": 1.5,  # 今日量比
                    "signal": "放量"
                },
                "pattern": {
                    "is_consolidation": True,  # 是否缩量企稳
                    "consolidation_days": 5,  # 企稳天数
                    "pullback_pct": -15.5,  # 回调幅度
                    "signal": "二波启动信号"
                }
            }
        """
        cache_key = self._cache_key("technical_indicators", code=code, period=period)
        cached = self._get_cache(cache_key)
        if cached:
            return cached.get("data", {})

        result = {
            "code": code,
            "name": "",
            "ma": {},
            "macd": {},
            "kdj": {},
            "volume": {},
            "pattern": {}
        }

        try:
            # 获取历史K线数据
            start_date = (datetime.now() - timedelta(days=period + 30)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")

            hist_df = self._safe_call(
                "stock_zh_a_hist",
                ak.stock_zh_a_hist,
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

            if hist_df is None or len(hist_df) < 20:
                log.warning(f"数据不足，无法计算技术指标")
                return result

            # 获取股票名称
            stock_info = self.get_stock_info(code)
            result["name"] = stock_info.get("name", "")

            hist = self._df_to_records(hist_df)
            closes = [self._safe_float(h.get("收盘")) for h in hist]
            volumes = [self._safe_float(h.get("成交量")) for h in hist]
            highs = [self._safe_float(h.get("最高")) for h in hist]
            lows = [self._safe_float(h.get("最低")) for h in hist]

            # 1. 均线系统
            if len(closes) >= 60:
                result["ma"] = {
                    "ma5": round(sum(closes[-5:]) / 5, 2),
                    "ma10": round(sum(closes[-10:]) / 10, 2),
                    "ma20": round(sum(closes[-20:]) / 20, 2),
                    "ma60": round(sum(closes[-60:]) / 60, 2)
                }

                # 均线多头排列判断
                ma_values = [result["ma"]["ma5"], result["ma"]["ma10"], result["ma"]["ma20"], result["ma"]["ma60"]]
                result["ma"]["is_bullish"] = ma_values == sorted(ma_values, reverse=True)

            # 2. MACD（简化计算）
            if len(closes) >= 26:
                ema12 = self._calculate_ema(closes, 12)
                ema26 = self._calculate_ema(closes, 26)
                dif = ema12 - ema26

                # 计算DEA（DIF的9日EMA）
                dif_list = []
                for i in range(26, len(closes)):
                    ema12_i = self._calculate_ema(closes[:i+1], 12)
                    ema26_i = self._calculate_ema(closes[:i+1], 26)
                    dif_list.append(ema12_i - ema26_i)

                dea = self._calculate_ema(dif_list, 9) if len(dif_list) >= 9 else 0
                macd = (dif - dea) * 2

                result["macd"] = {
                    "dif": round(dif, 3),
                    "dea": round(dea, 3),
                    "macd": round(macd, 3),
                    "signal": "金叉" if dif > dea and macd > 0 else "死叉" if dif < dea else "中性"
                }

            # 3. KDJ（简化计算）
            if len(closes) >= 9:
                recent_high = max(highs[-9:])
                recent_low = min(lows[-9:])
                rsv = ((closes[-1] - recent_low) / (recent_high - recent_low) * 100) if recent_high != recent_low else 50

                # 简化：K=RSV, D=K的3日均值
                k = rsv
                d = (rsv + k) / 2  # 简化计算
                j = 3 * k - 2 * d

                result["kdj"] = {
                    "k": round(k, 2),
                    "d": round(d, 2),
                    "j": round(j, 2),
                    "signal": "超买" if k > 80 else "超卖" if k < 20 else "中性"
                }

            # 4. 量能分析
            if len(volumes) >= 5:
                recent_avg_vol = sum(volumes[-5:]) / 5
                today_vol = volumes[-1]
                vol_ratio = today_vol / recent_avg_vol if recent_avg_vol > 0 else 1

                result["volume"] = {
                    "recent_avg": int(recent_avg_vol),
                    "today_ratio": round(vol_ratio, 2),
                    "signal": "放量" if vol_ratio > 1.5 else "缩量" if vol_ratio < 0.7 else "正常"
                }

            # 5. 形态分析（二波龙判断关键）
            if len(closes) >= 20:
                # 找最近的高点
                max_price = max(closes[-30:]) if len(closes) >= 30 else max(closes)
                current_price = closes[-1]
                pullback_pct = ((current_price - max_price) / max_price * 100)

                # 判断是否缩量企稳（近5日价格波动<5%且量能萎缩）
                recent_prices = closes[-5:]
                price_range = (max(recent_prices) - min(recent_prices)) / min(recent_prices) * 100
                is_consolidation = price_range < 5 and result["volume"].get("signal") == "缩量"

                # 统计企稳天数
                consolidation_days = 0
                for i in range(len(closes) - 1, max(0, len(closes) - 10), -1):
                    if i > 0:
                        chg = abs((closes[i] - closes[i-1]) / closes[i-1] * 100)
                        if chg < 3:  # 单日波动<3%
                            consolidation_days += 1
                        else:
                            break

                # 二波启动信号判断
                signal = "无信号"
                if is_consolidation and consolidation_days >= 3:
                    if result["volume"].get("signal") == "放量" and result["macd"].get("signal") == "金叉":
                        signal = "二波启动信号"
                    elif consolidation_days >= 5:
                        signal = "企稳待突破"

                result["pattern"] = {
                    "is_consolidation": is_consolidation,
                    "consolidation_days": consolidation_days,
                    "pullback_pct": round(pullback_pct, 2),
                    "signal": signal
                }

        except Exception as e:
            log.error(f"❌ 技术指标分析异常(code={code}): {e}")

        self._set_cache(cache_key, result)
        return result

    @staticmethod
    def _calculate_ema(data: list, period: int) -> float:
        """计算EMA指数移动平均"""
        if len(data) < period:
            return sum(data) / len(data) if data else 0

        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period  # 初始SMA

        for price in data[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    # ════════════════════════════════════
    #  全量复盘Pipeline
    # ════════════════════════════════════

    def full_review(self, date_str: str | None = None) -> dict:
        """
        全量短线复盘 — 一键获取所有数据并生成结构化报告

        这是本脚本最核心的方法，依次调用所有数据接口并整合输出。
        """
        date_str = self._format_date(date_str)
        log.info(f"\n{'='*55}")
        log.info(f"  📊 开始全量短线复盘 | {date_str}")
        log.info(f"  📊 今日已请求: {self._stats['daily_requests']}/{MAX_DAILY_REQUESTS}")
        log.info(f"{'='*55}\n")

        report = {"date": date_str, "timestamp": datetime.now().isoformat(), "data_source": "akshare"}

        # Step 1: 涨跌停统计
        log.info("📌 [1/7] 获取涨跌停数据...")
        report["zt_dt"] = self.get_zt_dt_summary(date_str)

        # Step 2: 连板天梯
        log.info("📌 [2/7] 构建连板天梯...")
        report["lianban"] = self.get_lianban_ladder(date_str)

        # Step 3: 板块排行
        log.info("📌 [3/7] 分析板块强度...")
        report["sectors"] = self.get_sector_ranking(date_str)

        # Step 4: 龙虎榜
        log.info("📌 [4/7] 获取龙虎榜...")
        report["lhb"] = self.get_lhb_data(date_str)

        # Step 5: 资金流向
        log.info("📌 [5/7] 查询资金流向...")
        report["fund_flow"] = self.get_fund_flow(flow_type="market")

        # Step 6: 北向资金
        log.info("📌 [6/7] 获取北向资金...")
        report["north_bound"] = self.get_north_bound(date_str)

        # Step 7: 高度龙头股深度诊断（取前3只最高板）
        report["dragon_diagnosis"] = []
        max_height_stocks = []
        for height_key, stocks in report.get("lianban", {}).get("ladder", {}).items():
            max_height_stocks.extend(stocks)
            if len(max_height_stocks) >= 3:
                break

        log.info("📌 [7/7] 龙头股深度诊断...")
        for stock in max_height_stocks[:3]:
            code = stock.get("code", "")
            if code:
                log.info(f"  🔍 诊断: {stock.get('name', '')}({code})")
                detail = self.get_stock_info(code)
                detail["_lianban_context"] = stock
                report["dragon_diagnosis"].append(detail)
                time.sleep(random.uniform(1, 2))

        # 汇总
        report["request_count"] = self._request_count
        report["daily_total"] = self._stats["daily_requests"]
        log.info(f"\n{'='*55}")
        log.info(f"  ✅ 复盘完成! 本次请求 {self._request_count} 次")
        log.info(f"  📊 今日累计: {self._stats['daily_requests']}/{MAX_DAILY_REQUESTS}")
        log.info(f"{'='*55}\n")

        return report

    # ════════════════════════════════════
    #  工具方法
    # ════════════════════════════════════

    @staticmethod
    def _classify_board_pattern(stock_record: dict) -> str:
        """
        根据股票数据判断涨停板形态（强势股池版本）
        一字板 / T字板 / 实体大阳线 / 烂板
        """
        open_p = AStockDataFetcher._safe_float(stock_record.get("今开", stock_record.get("open")))
        high_p = AStockDataFetcher._safe_float(stock_record.get("最高", stock_record.get("high")))
        low_p = AStockDataFetcher._safe_float(stock_record.get("最低", stock_record.get("low")))
        close_p = AStockDataFetcher._safe_float(stock_record.get("最新价", stock_record.get("收盘")))
        zt_price = AStockDataFetcher._safe_float(stock_record.get("涨停价", stock_record.get("zt_price")))
        turnover = AStockDataFetcher._safe_float(stock_record.get("换手率", stock_record.get("turnover")))
        chg_pct = AStockDataFetcher._safe_float(stock_record.get("涨跌幅", stock_record.get("chg_pct")))

        # 断板判断
        if chg_pct < 9.5:
            return "断板"

        # 一字板：开盘=涨停价 且 最低=涨停价
        if abs(open_p - zt_price) < 0.02 and abs(low_p - zt_price) < 0.02:
            return "一字板"

        # T字板：开盘=涨停价 但最低<涨停价 且 收盘=涨停价
        if abs(open_p - zt_price) < 0.02 and low_p < zt_price - 0.01 and abs(close_p - zt_price) < 0.02:
            return "T字板"

        # 烂板：高换手且大幅震荡
        if turnover > 15 and low_p < zt_price * 0.97:
            return "烂板"

        return "实体大阳线"

    @staticmethod
    def _classify_board_pattern_zt(stock_record: dict) -> str:
        """
        根据涨停池数据判断涨停板形态（主池版本，字段不同）
        涨停池字段：炸板次数, 封板资金, 首次封板时间, 最后封板时间, 涨跌幅, 换手率
        """
        zab_count = AStockDataFetcher._safe_int(stock_record.get("炸板次数"))
        seal_capital = AStockDataFetcher._safe_float(stock_record.get("封板资金", 0))
        turnover = AStockDataFetcher._safe_float(stock_record.get("换手率"))
        chg_pct = AStockDataFetcher._safe_float(stock_record.get("涨跌幅"))

        if chg_pct < 9.5:
            return "断板"

        # 有炸板记录
        if zab_count >= 2:
            return "烂板"
        if zab_count == 1:
            # 炸过一次但最终回封
            if turnover > 15:
                return "烂板"
            return "T字板"

        # 无炸板
        if turnover <= 3 and seal_capital > 0:
            # 低换手+有封单 → 一字板或缩量一字
            return "一字板"
        elif turnover > 20:
            # 高换手无炸板 → 实体大阳线（放量换手板）
            return "实体大阳线"

        return "实体大阳线"

    def to_markdown_report(self, review_data: dict) -> str:
        """将全量复盘数据渲染为Markdown报告"""
        lines = []
        d = review_data.get("date", "")
        lines.append(f"\n═══════════════════════════════════════")
        lines.append(f"  📊 A股短线情绪日报 | {d}")
        lines.append(f"═══════════════════════════════════════\n")

        # 涨跌停概览
        zt = review_data.get("zt_dt", {})
        lines.append(f"┌─ 涨跌停概览 ─────────────────────┐")
        lines.append(
            f"│ 涨停 {zt.get('zt_count', 0)}家 │ 跌停 {zt.get('dt_count', 0)}家 │ "
            f"炸板 {zt.get('zab_count', 0)}家 │ 炸板率 {zt.get('zab_rate', 0)}%"
        )
        lines.append(
            f"│ 昨涨停 {zt.get('zt_count_yesterday', 0)}家 │ "
            f"连板 {zt.get('lianban_count', 0)}家 │ 最高 {zt.get('max_lianban', 0)}板"
        )
        lines.append(f"└───────────────────────────────────┘\n")

        # 连板天梯
        lb = review_data.get("lianban", {})
        ladder = lb.get("ladder", {})
        if ladder:
            lines.append("📈 **连板天梯**:")
            for height, stocks in list(ladder.items())[:8]:
                names = ", ".join([s.get("name", "?") for s in stocks[:3]])
                if len(stocks) > 3:
                    names += f" 等{len(stocks)}只"
                lines.append(f"  {height}: {names}")
            lines.append("")

        # 板块TOP5
        sec = review_data.get("sectors", {})
        concepts = sec.get("concept_top10", [])[:5]
        if concepts:
            lines.append("🏆 **板块TOP5**:")
            for c in concepts:
                chg = c.get("chg_pct", 0)
                color = "+" if chg >= 0 else ""
                lines.append(
                    f"  {c['rank']}. {c['name']} ({color}{chg:.1f}%) "
                    f"涨停{c.get('zt_count', 0)}家 | 领涨: {c.get('lead_stock', '')}"
                )
            lines.append("")

        # 龙虎榜
        lhb = review_data.get("lhb", {})
        lhb_stocks = lhb.get("lhb_stocks", [])[:5]
        if lhb_stocks:
            lines.append("🐯 **龙虎榜**:")
            for s in lhb_stocks:
                nb = s.get("net_buy", 0)
                direction = "🟢净买" if nb > 0 else "🔴净卖"
                lines.append(
                    f"  {s['name']}({s['code']}) {s['chg_pct']:+.1f}% "
                    f"| {direction}{abs(nb):.2f}亿 | {s.get('reason', '')}"
                )
            inst = lhb.get("institution_summary", {})
            if inst:
                lines.append(
                    f"  🏦 机构: 买入{inst.get('buy_total', 0)}亿 | "
                    f"卖出{inst.get('sell_total', 0)}亿 | "
                    f"净{inst.get('net_buy', 0):+.2f}亿"
                )
            lines.append("")

        # 资金流向
        ff = review_data.get("fund_flow", {})
        if ff.get("main_net_in") is not None:
            lines.append(f"💰 **全市场资金**: 主力{'净流入' if ff.get('main_net_in', 0) > 0 else '净流出'} {ff.get('main_net_in', 0):+.2f}亿")

        # 北向资金
        nb = review_data.get("north_bound", {})
        if nb.get("net_buy_in") is not None:
            lines.append(
                f"🌏 **北向资金**: {'净买入' if nb.get('net_buy_in', 0) > 0 else '净卖出'} "
                f"{abs(nb.get('net_buy_in', 0)):.2f}亿"
            )
        lines.append("")

        # 龙头诊断
        diag = review_data.get("dragon_diagnosis", [])
        if diag:
            lines.append("🐉 **高度龙头诊断**:")
            for stock in diag:
                name = stock.get("name", "?")
                code = stock.get("code", "?")
                ctx = stock.get("_lianban_context", {})
                chg = stock.get("chg_pct", 0)
                pattern = ctx.get("board_pattern", "?")
                ff_local = stock.get("fund_flow", {})
                main_ff = ff_local.get("main_net", 0) if ff_local else 0
                lines.append(
                    f"  {name}({code}) {chg:+.1f}% | {ctx.get('height', '?')}板 {pattern}"
                    f" | 主力{'流入' if main_ff > 0 else '流出'}{abs(main_ff):.2f}万"
                    f" | 换手{stock.get('turnover', 0):.1f}%"
                )
            lines.append("")

        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"⏰ 报告生成时间: {review_data.get('timestamp', '')}")
        lines.append(f"📡 数据来源: akshare | 请求次数: {review_data.get('request_count', 0)}")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return "\n".join(lines)


# ════════════════════════════════════════════════
#  CLI入口
# ════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="A股短线数据获取引擎")
    parser.add_argument("--action", required=True, choices=[
        "zt_dt_summary",      # 涨跌停统计
        "lianban_ladder",     # 连板天梯
        "sector_ranking",     # 板块排行
        "stock_info",         # 个股查询
        "fund_flow",          # 资金流向
        "lhb",               # 龙虎榜
        "north_bound",       # 北向资金
        "full_review",       # 全量复盘
        "lianban_history",   # 个股连板历史
        "sector_timeline",   # 板块时间线分析
        "concept_detail",    # 概念板块详情
        "technical",         # 技术指标分析
        "stats",             # 查看统计
        "reset_stats",       # 重置统计
    ], help="执行的操作类型")
    parser.add_argument("--date", default=None, help="日期(YYYYMMDD)，默认今日")
    parser.add_argument("--code", default=None, help="股票代码")
    parser.add_argument("--sector", default=None, help="板块名称")
    parser.add_argument("--concept", default=None, help="概念名称")
    parser.add_argument("--start", default=None, help="开始日期(YYYYMMDD)")
    parser.add_argument("--end", default=None, help="结束日期(YYYYMMDD)")
    parser.add_argument("--period", type=int, default=60, help="技术分析周期（天数）")
    parser.add_argument("--type", default="individual", choices=[
        "individual", "concept", "industry", "market"
    ], help="资金流向类型")
    parser.add_argument("--no-cache", action="store_true", help="禁用缓存")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")

    args = parser.parse_args()

    # 统计查询和重置不需要初始化fetcher
    if args.action == "stats":
        if STATS_FILE.exists():
            with open(STATS_FILE, "r") as f:
                stats = json.load(f)
                print(json.dumps(stats, indent=2, ensure_ascii=False))
                print(f"\n📊 今日请求: {stats.get('daily_requests', 0)}/{MAX_DAILY_REQUESTS}")
                print(f"⚠️ 连续失败: {stats.get('consecutive_failures', 0)}/{MAX_CONSECUTIVE_FAILURES}")
                if stats.get('cooldown_until'):
                    cooldown = datetime.fromisoformat(stats['cooldown_until'])
                    if datetime.now() < cooldown:
                        remaining = (cooldown - datetime.now()).total_seconds()
                        print(f"🔒 冷却中，剩余 {remaining/60:.1f} 分钟")
                    else:
                        print("✅ 无冷却限制")
        else:
            print("📊 暂无统计数据")
        return {}

    if args.action == "reset_stats":
        if STATS_FILE.exists():
            STATS_FILE.unlink()
            print("✅ 统计数据已重置")
        else:
            print("📊 无需重置，统计文件不存在")
        return {}

    fetcher = AStockDataFetcher(enable_cache=not args.no_cache)

    action_map = {
        "zt_dt_summary": lambda: fetcher.get_zt_dt_summary(args.date),
        "lianban_ladder": lambda: fetcher.get_lianban_ladder(args.date),
        "sector_ranking": lambda: fetcher.get_sector_ranking(args.date),
        "stock_info": lambda: fetcher.get_stock_info(args.code) if args.code else {"error": "需要--code参数"},
        "fund_flow": lambda: fetcher.get_fund_flow(args.type, args.code, args.date),
        "lhb": lambda: fetcher.get_lhb_data(args.date),
        "north_bound": lambda: fetcher.get_north_bound(args.date),
        "full_review": lambda: fetcher.full_review(args.date),
        "lianban_history": lambda: fetcher.get_stock_lianban_history(args.code, args.start, args.end) if args.code else {"error": "需要--code参数"},
        "sector_timeline": lambda: fetcher.get_sector_timeline_analysis(args.sector, args.start, args.end) if args.sector else {"error": "需要--sector参数"},
        "concept_detail": lambda: fetcher.get_concept_detail(args.concept) if args.concept else {"error": "需要--concept参数"},
        "technical": lambda: fetcher.get_technical_indicators(args.code, args.period) if args.code else {"error": "需要--code参数"},
    }

    result = action_map[args.action]()

    if args.action == "full_review":
        output = fetcher.to_markdown_report(result) if not args.json else json.dumps(result, ensure_ascii=False, default=str, indent=2)
    else:
        output = json.dumps(result, ensure_ascii=False, default=str, indent=2) if args.json else str(result)

    print(output)

    return result


if __name__ == "__main__":
    main()
