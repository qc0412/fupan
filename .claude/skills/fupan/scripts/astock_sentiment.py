#!/usr/bin/env python3
"""
A股短线情绪分析算法引擎 v3.0
================================
基于《龙头战法》《顿悟渐修》+ 养家心法 + 一瞬流光 + 短线之道

功能：
- 六维加权情绪评分 (0-10分)
- 周期阶段映射（冰点→弱修复→修复期→亢奋前期→亢奋高潮）
- 龙头三要素量化（带领性/突破性/唯一性）
- 渡劫识别算法（炸板/巨量/低开/核按钮反包）
- 板块梯队构建与健康度评估
- 主线判断（主流/支流/次主流三级）
- 策略生成引擎（含T+1约束与置信度）

数据来源: astock_data.py (akshare)

TODO: 接入 premium_ladder.py 的真实晋级率/昨日涨停平均涨幅(avg_chg)，
      替代 _build_sentiment_input 中置 None 的 yest_zt_avg_chg / yest_lianban_promote_rate /
      yest_duanban_nuclear（当前为 None 时相关维度跳过判定、不参与评分）。
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


def zt_threshold(code: str, name: str = "") -> float:
    """
    按市场/ST属性返回"视为涨停"的涨跌幅判定阈值(%)（与 astock_data.zt_threshold 同款）
    - name含ST/*ST → 4.8；30/68开头 → 19.5；43/83/87/88/92开头(北交所) → 29.5；其余 → 9.8
    """
    if name and "ST" in str(name).upper():
        return 4.8
    c = str(code)
    if c.startswith(("30", "68")):
        return 19.5
    if c.startswith(("43", "83", "87", "88", "92")):
        return 29.5
    return 9.8


# ════════════════════════════════════
#  数据结构定义
# ════════════════════════════════════

@dataclass
class SentimentInput:
    """每日收盘后需要采集的基础数据"""
    # 涨停相关
    zt_count: int = 0
    zt_count_yesterday: int = 0
    lianban_count: int = 0
    max_lianban: int = 0

    # 炸板相关
    zab_count: int = 0
    try_zt_total: int = 0
    zab_rate: float = 0.0

    # 昨日反馈（核心！）None = 数据缺失，相关判定跳过、不参与评分
    yest_zt_avg_chg: Optional[float] = None
    yest_lianban_promote_rate: Optional[float] = None
    yest_duanban_nuclear: Optional[int] = None

    # 跌停相关
    dt_count: int = 0

    # 高度趋势（近5日）
    height_history: list[int] = field(default_factory=list)

    # 主线判断辅助
    main_theme_clear: bool = False
    main_theme_strength: str = "无"
    theme_rotation_freq: int = 0

    # 特殊事件标志
    has_tiandiban: bool = False
    has_ditianban: bool = False
    has_waipan_shock: bool = False
    is_weekend_ahead: bool = False

    def validate(self) -> list[str]:
        errors = []
        if self.try_zt_total == 0 and (self.zt_count > 0 or self.zab_count > 0):
            errors.append("try_zt_total应为zt_count+zab_count之和")
        if len(self.height_history) != 5:
            errors.append(f"height_history需要5个值，当前{len(self.height_history)}个")
        if self.zt_count < 0 or self.dt_count < 0:
            errors.append("涨停/跌停数不能为负")
        return errors


class BoardPattern(Enum):
    YIZI = "一字板"
    TZI = "T字板"
    SHITI = "实体大阳线"
    LANBAN = "烂板"
    DUANBAN = "断板"


class LifeCyclePhase(Enum):
    STARTUP = ("启动期", (1, 2))
    ACCELERATION = ("加速期", (3, 4))
    DIVERGENCE = ("分歧期", (5, None))
    CLIMAX = ("见顶期", (None, None))
    DECLINE = ("退潮期", (None, None))


class ThemeLevel(Enum):
    MAINSTREAM = ("主流", "国策长线")
    SUB_STREAM = ("支流", "中线")
    MINOR_STREAM = ("次主流", "隔日超短")
    NO_THEME = ("无主题", "")


@dataclass
class DoujieResult:
    is_doujie: bool = False
    doujie_type: str = ""
    doujie_level: int = 0
    survival_prob: float = 1.0
    advice: str = "持有"


@dataclass
class DragonScore:
    leading_score: float = 0.0
    breakthrough_score: float = 0.0
    uniqueness_score: float = 0.0
    overall: float = 0.0
    grade: str = "D"
    is_real_dragon: bool = False
    god_form_analysis: dict = field(default_factory=dict)


# ════════════════════════════════════
#  模块①：六维情绪评分
# ════════════════════════════════════

def calc_sentiment_score(d: SentimentInput) -> dict:
    """
    六维加权评分 → 综合分(0-10) → 映射周期阶段
    
    Returns:
        {score, phase, dim_scores, warnings, confidence}
    """
    scores = {}

    # 维度1：涨停数量热度（权重20%）
    scores['zt_heat'] = _score_zt_heat(d.zt_count, d.zt_count_yesterday)

    # 维度2：昨日赚钱效应（权重25%，最核心）
    # 数据缺失(None)时返回None → 该维度不参与评分（权重重新归一），不按0触发假信号
    scores['money_effect'] = _score_money_effect(d.yest_zt_avg_chg, d.yest_lianban_promote_rate)

    # 维度3：连板梯队健康度（权重20%）
    scores['lianban_health'] = _score_lianban_health(d.lianban_count, d.max_lianban, d.height_history)

    # 维度4：负反馈强度（权重15%）
    scores['negative'] = _score_negative_feedback(d.zab_count, d.zab_rate, d.yest_duanban_nuclear, d.dt_count)

    # 维度5：主线清晰度（权重10%）
    scores['theme_clarity'] = _score_theme(d.main_theme_clear, d.main_theme_strength, d.theme_rotation_freq)

    # 维度6：崩溃前兆链检测（权重10%，扣分项）
    scores['collapse_chain'] = _score_collapse_chain(d)

    # 所有维度安全clamp到[0,10]（None=数据缺失，跳过）
    for key in scores:
        if scores[key] is not None:
            scores[key] = max(0.0, min(10.0, scores[key]))

    # 加权综合分
    weights = {
        'zt_heat': 0.20,
        'money_effect': 0.25,
        'lianban_health': 0.20,
        'negative': 0.15,
        'theme_clarity': 0.10,
        'collapse_chain': 0.10,
    }

    # 数据缺失维度不参与评分，剩余维度权重重新归一
    avail = {k: w for k, w in weights.items() if scores.get(k) is not None}
    w_sum = sum(avail.values())
    if w_sum > 0:
        total = sum(scores[k] * w for k, w in avail.items()) / w_sum
    else:
        total = 5.0  # 全部缺失时给中性分
    score = round(max(0.0, min(10.0, total)), 1)

    confidence = _calc_score_confidence(scores, d)
    phase = _map_phase(score, scores)
    warnings = _generate_warnings(scores, d)
    missing_dims = [k for k, v in scores.items() if v is None]
    if missing_dims:
        warnings.append(f"ℹ️ 数据缺失未参与评分: {', '.join(missing_dims)}")

    return {
        'score': score,
        'phase': phase,
        'phase_detail': PHASE_RULES_DETAIL.get(phase, ("未知", "", "")),
        'dim_scores': {k: (round(v, 1) if v is not None else None) for k, v in scores.items()},
        'weights': weights,
        'warnings': warnings,
        'confidence': confidence,
    }


def _calc_score_confidence(dim_scores: dict, d: SentimentInput) -> int:
    """计算情绪评分的置信度(0-100%)"""
    conf = 100.0

    if len(d.height_history) != 5:
        conf -= 15
    if d.yest_zt_avg_chg in (None, 0) and d.yest_lianban_promote_rate in (None, 0):
        conf -= 20

    values = [v for v in dim_scores.values() if v is not None]  # None=数据缺失，剔除
    if values:
        try:
            std = statistics.stdev(values)
            if std > 3:
                conf -= 15
            elif std > 2:
                conf -= 5
        except statistics.StatisticsError:
            pass

    return max(20, min(100, int(conf)))


# ── 各维度评分函数 ──

def _score_zt_heat(zt_today: int, zt_yest: int) -> float:
    thresholds = [(100, 10.0), (70, 8.5), (50, 7.0), (35, 5.5), (20, 4.0), (10, 2.5)]
    for threshold, score in thresholds:
        if zt_today >= threshold:
            return score
    return 1.0


def _score_money_effect(avg_chg, promote_rate):
    """avg_chg/promote_rate 为 None 表示数据缺失：两者都缺返回None(该维度不评分)，缺一项用另一项"""
    if avg_chg is None and promote_rate is None:
        return None

    chg_thresholds = [(5, 10), (3, 8), (1, 6), (0, 4), (-2, 2)]
    s_chg = None if avg_chg is None else next((s for t, s in chg_thresholds if avg_chg >= t), 0)

    pro_thresholds = [(60, 10), (45, 8), (30, 6), (15, 4)]
    s_pro = None if promote_rate is None else next((s for t, s in pro_thresholds if promote_rate >= t), 1)

    if s_chg is None:
        return round(float(s_pro), 1)
    if s_pro is None:
        return round(float(s_chg), 1)
    return round(s_chg * 0.6 + s_pro * 0.4, 1)


def _score_lianban_health(lianban_cnt: int, max_h: int, height_hist: list) -> float:
    cnt_thresholds = [(20, 10), (12, 8), (7, 6), (3, 4)]
    s_cnt = next((s for t, s in cnt_thresholds if lianban_cnt >= t), 1)

    h_thresholds = [(7, 10), (5, 8), (4, 6), (3, 4)]
    s_height = next((s for t, s in h_thresholds if max_h >= t), 1)

    s_trend = 0
    if len(height_hist) >= 2:
        trend = sum(1 for i in range(len(height_hist)-1) if height_hist[i+1] > height_hist[i])
        s_trend = min(10, trend * 2.5)

    return round(s_cnt * 0.35 + s_height * 0.40 + s_trend * 0.25, 1)


def _score_negative_feedback(zab_cnt: int, zab_rate: float, nuclear_cnt, dt_cnt: int) -> float:
    nuclear_cnt = 0 if nuclear_cnt is None else nuclear_cnt  # 数据缺失不扣分
    s_zab = max(0, 10 - min(zab_cnt * 0.5, 10))
    rate_penalty = 3 if zab_rate > 50 else (2 if zab_rate > 40 else (1 if zab_rate > 30 else 0))
    s_zab -= rate_penalty

    s_nuclear = max(0, 10 - nuclear_cnt * 3)
    s_dt = max(0, 10 - dt_cnt * 0.5)

    return round(s_zab * 0.35 + s_nuclear * 0.35 + s_dt * 0.30, 1)


def _score_theme(clear: bool, strength: str, rotation_freq: int) -> float:
    if not clear:
        return 2.0
    str_map = {"强": 10, "中": 6, "弱": 3, "无": 1}
    s_str = str_map.get(strength, 1)
    s_rot = max(0, 10 - rotation_freq * 2)
    return round(s_str * 0.7 + s_rot * 0.3, 1)


def _score_collapse_chain(d: SentimentInput) -> float:
    """崩溃前兆链检测（满分10，逐级扣分）"""
    score = 10.0
    deductions = []

    # Level 1: 追涨者亏钱（数据缺失None时跳过该项判定，不按0扣分制造假信号）
    if d.yest_zt_avg_chg is not None and d.yest_zt_avg_chg < 1.0:
        score -= 2.0
        deductions.append(f"L1-追涨亏损(昨均幅{d.yest_zt_avg_chg}%)")

    # Level 2: 活跃度骤降
    if d.zt_count_yesterday > 0:
        drop_ratio = (d.zt_count_yesterday - d.zt_count) / d.zt_count_yesterday
        if drop_ratio > 0.3:
            score -= 2.0
            deductions.append(f"L2-活跃骤降({drop_ratio*100:.0f}%)")

    # Level 4: 高位补跌（核按钮数据缺失None时跳过）
    if d.max_lianban >= 5 and d.yest_duanban_nuclear is not None and d.yest_duanban_nuclear >= 2:
        score -= 2.0
        deductions.append(f"L4-高位补跌(核按钮{d.yest_duanban_nuclear}家)")

    # Level 5: 大面积崩溃
    if d.dt_count >= 30:
        score = 0.0
        deductions.append("L5-大面积崩溃!!!")

    # 天地板超级警告
    if d.has_tiandiban:
        score = max(0, score - 3)
        deductions.append("⚠️天地板")

    return max(0.0, score)


def _generate_warnings(dim_scores: dict, d: SentimentInput) -> list[str]:
    warnings_list = []

    _me = dim_scores.get('money_effect', 10)
    if _me is not None and _me <= 2:
        warnings_list.append("⚠️ 赚钱效应极差，追涨资金大幅亏损")
    if dim_scores.get('collapse_chain', 10) <= 4:
        warnings_list.append("⚠️ 检测到崩溃前兆信号链")
    if dim_scores.get('negative', 10) <= 3:
        warnings_list.append("⚠️ 负反馈强烈（高跌停/高核按钮/高炸板）")
    if d.has_tiandiban:
        warnings_list.append("🔴 今日出现天地板！极端风险信号")
    if d.is_weekend_ahead and dim_scores.get('zt_heat', 10) >= 7:
        warnings_list.append("ℹ️ 明天周五，周末效应可能影响持股意愿")

    return warnings_list


# ── 周期映射 ──

PHASE_RULES = {
    (0, 2.0): ("🧊 冰点", "市场极度寒冷", "空仓/试错"),
    (2.0, 4.0): ("❄️ 冰点边缘", "情绪低迷但有暖意", "轻仓试错"),
    (4.0, 5.5): ("🔄 弱修复", "僵持格局，不上不下", "看戏/观望"),
    (5.5, 7.0): ("🔥 修复期", "赚钱效应回暖", "积极做多"),
    (7.0, 8.5): ("🔥🔥 亢奋前期", "赚钱效应良好", "重仓出击"),
    (8.5, 10.01): ("🚀 亢奋高潮", "市场狂热", "持仓/兑现"),
}

PHASE_RULES_DETAIL = {v[0]: v for v in PHASE_RULES.values()}


def _map_phase(score: float, dim_scores: dict) -> str:
    for (lo, hi), (name, _, _) in PHASE_RULES.items():
        if lo <= score < hi:
            return name
    return "🧊 冰点"


# ════════════════════════════════════
#  模块②：连板高度 & 渡劫诊断
# ════════════════════════════════════

def classify_board_pattern(stock_data: dict) -> BoardPattern:
    """根据个股K线数据判断涨停板形态"""
    get = lambda k, default=0: stock_data.get(k, default)

    open_p = get('open')
    high_p = get('high')
    low_p = get('low')
    close_p = get('close')
    zt_price = get('zt_price')
    turnover = get('turnover')
    chg_pct = get('chg_pct', 0)

    # 断板判断按市场/ST属性区分阈值（防ST涨停股被误判断板）
    if chg_pct < zt_threshold(stock_data.get('code', ''), stock_data.get('name', '')):
        return BoardPattern.DUANBAN
    if abs(open_p - zt_price) < 0.02 and abs(low_p - zt_price) < 0.02:
        return BoardPattern.YIZI
    if abs(open_p - zt_price) < 0.02 and low_p < zt_price - 0.01 and abs(close_p - zt_price) < 0.02:
        return BoardPattern.TZI
    if turnover > 15 and low_p < zt_price * 0.97:
        return BoardPattern.LANBAN
    return BoardPattern.SHITI


def diagnose_doujie(stock_history: list[dict]) -> DoujieResult:
    """
    判断一只连板股是否正在经历渡劫
    
    四种渡劫类型：炸板渡劫、巨量渡劫、低开渡劫、核按钮反包渡劫
    """
    if not stock_history or len(stock_history) < 2:
        return DoujieResult()

    today = stock_history[-1]
    prev_days = stock_history[:-1]
    board_count = today.get('consecutive_boards', 0)

    result = DoujieResult()

    # 类型1: 炸板渡劫
    open_times = today.get('open_times', 0)
    if open_times >= 3:
        result.is_doujie = True
        result.doujie_type = "炸板渡劫"
        result.doujie_level = min(5, open_times)
        # 回封判定：避免浮点直等比较；任一为None不判回封
        _close, _ztp = today.get('close'), today.get('zt_price')
        if _close is not None and _ztp is not None and abs(_close - _ztp) < 0.001:
            result.survival_prob = 0.7
            result.advice = "回封可轻仓介入（分歧转一致买点）"
        else:
            result.survival_prob = 0.3
            result.advice = "不介入，观察明日"

    # 类型2: 巨量渡劫
    elif len(prev_days) >= 3:
        prev_avg_turnover = sum(d.get('turnover', 0) for d in prev_days[-3:]) / 3
        today_turnover = today.get('turnover', 0)
        if today_turnover > prev_avg_turnover * 2.5 and today_turnover > 30:
            result.is_doujie = True
            result.doujie_type = "巨量渡劫"
            result.doujie_level = 4
            if today.get('close', 0) >= today.get('zt_price', 999):
                result.survival_prob = 0.65
                result.advice = "放量涨停=筹码充分交换=健康"
            else:
                result.survival_prob = 0.35
                result.advice = "放量未能封住=出货嫌疑大，回避"

    # 类型3: 低开渡劫
    if not result.is_doujie and len(prev_days) >= 1:
        prev_close = prev_days[-1].get('close', 0)
        today_open = today.get('open', 0)
        if prev_close > 0 and today_open > 0:
            gap_ratio = (prev_close - today_open) / prev_close
            if gap_ratio > 0.03:
                result.is_doujie = True
                result.doujie_type = "低开渡劫"
                result.doujie_level = min(5, int(gap_ratio * 100 / 2))
                if today.get('close', 0) >= today.get('zt_price', 999):
                    result.survival_prob = 0.75
                    result.advice = "【黄金买点】低开高走涨停，弱转强确认"
                elif today.get('chg_pct', 0) > 3:
                    result.survival_prob = 0.55
                    result.advice = "大阳线未涨停，观察明日"
                else:
                    result.survival_prob = 0.25
                    result.advice = "低开后无力，渡劫失败概率大"

    # 类型4: 核按钮反包渡劫
    if not result.is_doujie and len(prev_days) >= 1:
        if prev_days[-1].get('chg_pct', 0) < -9 and today.get('chg_pct', 0) > 8:
            result.is_doujie = True
            result.doujie_type = "核按钮反包渡劫"
            result.doujie_level = 5
            result.survival_prob = 0.5
            result.advice = "极端博弈点，仅限高手小仓"

    # 高位额外折扣
    if result.is_doujie:
        if board_count >= 7:
            result.survival_prob *= 0.7
        elif board_count >= 5:
            result.survival_prob *= 0.85
        result.survival_prob = round(result.survival_prob, 2)

    return result


def identify_life_cycle(stock_info: dict) -> tuple[LifeCyclePhase, str]:
    """生命周期五阶段判断"""
    boards = stock_info.get('consecutive_boards', 0)
    pattern = classify_board_pattern(stock_info)

    if boards <= 2:
        phase = LifeCyclePhase.STARTUP
        detail = f"{boards}板启动中，观察带动性"
    elif boards <= 4:
        phase = LifeCyclePhase.ACCELERATION
        desc = "缩量一致" if pattern in (BoardPattern.YIZI, BoardPattern.TZI) else "注意换手"
        detail = f"{boards}板加速期，{desc}"
    elif boards >= 5:
        if pattern in (BoardPattern.LANBAN, BoardPattern.DUANBAN):
            phase = LifeCyclePhase.DIVERGENCE
            detail = f"{boards}板首次分歧"
        elif pattern == BoardPattern.YIZI:
            phase = LifeCyclePhase.CLIMAX
            detail = f"{boards}板一字加速赶顶，警惕突然死亡"
        else:
            phase = LifeCyclePhase.DIVERGENCE
            detail = f"{boards}板高位实体板，观察换手健康度"

    if pattern == BoardPattern.DUANBAN:
        phase = LifeCyclePhase.DECLINE
        detail = "断板退潮，除非强力反包否则结束"

    return phase, detail


# ════════════════════════════════════
#  模块③：龙头三要素量化
# ════════════════════════════════════

def calc_three_elements(stock: dict, market_context: dict) -> DragonScore:
    """
    龙头三要素量化评估
    
    三要素：带领性(leading)、突破性(breakthrough)、唯一性(uniqueness)
    最终得分 = min(三者)，体现短板理论
    """
    leading = _calc_leading(stock, market_context)
    breakthrough = _calc_breakthrough(stock)
    uniqueness = _calc_uniqueness(stock, market_context)
    overall = min(leading, breakthrough, uniqueness)

    god_form = _analyze_god_vs_form(stock, market_context)
    is_real_dragon = (overall >= 6.0) and (god_form.get('god_score', 0) >= 6.0)

    god_score = god_form.get('god_score', 0)
    if god_score < 4.0 and overall >= 7.0:
        overall = max(god_score, 4.0)

    grade = _grade_dragon(overall)

    return DragonScore(
        leading_score=round(leading, 1),
        breakthrough_score=round(breakthrough, 1),
        uniqueness_score=round(uniqueness, 1),
        overall=round(overall, 1),
        grade=grade,
        is_real_dragon=is_real_dragon,
        god_form_analysis=god_form,
    )


def _calc_leading(stock: dict, ctx: dict) -> float:
    """带领性评估"""
    stock_chg = stock.get('chg_pct', 0)
    sector_avg_chg = ctx.get('sector_avg_chg', 0)
    sector_rank = stock.get('sector_chg_rank', 99)

    score = 5.0
    if sector_avg_chg > 0:
        ratio = stock_chg / max(sector_avg_chg, 0.01)
        if ratio >= 2.0: score += 3
        elif ratio >= 1.5: score += 2
        elif ratio >= 1.2: score += 1
        elif ratio < 0.8: score -= 2
    else:
        if stock_chg > 0: score += 3
        elif stock_chg > sector_avg_chg: score += 1

    if sector_rank == 1: score += 2
    elif sector_rank <= 3: score += 1
    elif sector_rank > 10: score -= 1

    return max(0, min(10, score))


def _calc_breakthrough(stock: dict) -> float:
    """突破性评估"""
    score = 5.0

    if stock.get('is_new_high', False): score += 2

    ma_break_count = sum([
        stock.get('above_ma5', False),
        stock.get('above_ma10', False),
        stock.get('above_ma20', False),
        stock.get('above_ma60', False),
    ])
    score += ma_break_count * 0.5

    if stock.get('volume_ratio', 1) > 1.5 and stock.get('chg_pct', 0) > 3:
        score += 1.5
    elif stock.get('volume_ratio', 1) > 1.2:
        score += 0.5

    boards = stock.get('consecutive_boards', 0)
    if boards >= 5: score += 1.5
    elif boards >= 3: score += 1

    return max(0, min(10, score))


def _calc_uniqueness(stock: dict, ctx: dict) -> float:
    """唯一性评估"""
    score = 5.0

    if stock.get('is_sector_leader', False): score += 2.5
    elif stock.get('is_sector_top3', False): score += 1.5

    amount_ratio = stock.get('sector_amount_ratio', 0)
    if amount_ratio >= 0.3: score += 2
    elif amount_ratio >= 0.15: score += 1

    if stock.get('consecutive_boards', 0) >= 3: score += 1
    if stock.get('is_main_theme_leader', False): score += 1.5

    return max(0, min(10, score))


def _grade_dragon(overall: float) -> str:
    if overall >= 8.5: return "S"
    elif overall >= 7.0: return "A"
    elif overall >= 5.5: return "B"
    elif overall >= 4.0: return "C"
    else: return "D"


def _analyze_god_vs_form(stock: dict, market_context: dict) -> dict:
    """神vs形辨析 — 区别真龙头与人造龙头"""

    form_score = 0.0
    form_items = []

    if stock.get('is_fangliang_yang'): form_score += 2; form_items.append("放量阳线")
    if stock.get('consecutive_red', 0) >= 3: form_score += 1.5; form_items.append(f"连红{stock['consecutive_red']}天")
    if stock.get('above_ma5') and stock.get('above_ma10'): form_score += 1; form_items.append("均线多头")
    if stock.get('volume_ratio', 1) > 1.5: form_score += 1.5; form_items.append("放量")
    if stock.get('macd_gold_cross'): form_score += 0.5; form_items.append("MACD金叉")
    form_score = min(10, form_score)

    god_score = 0.0
    god_items = []

    cycle_pos = stock.get('cycle_position', '')
    pos_scores = {'acceleration': 3, 'startup': 2, 'divergence': 1}
    if cycle_pos in pos_scores:
        god_score += pos_scores[cycle_pos]
        god_items.append(f"G1-处于{cycle_pos}期{'(最佳)' if cycle_pos=='acceleration' else ''}")
    else:
        god_items.append("G1-非核心位置")

    rank = stock.get('volume_rank', 999)
    if rank <= 5: god_score += 2.5; god_items.append(f"G2-全市场成交第{rank}")
    elif rank <= 20: god_score += 2.0; god_items.append(f"G2-全市场成交第{rank}")
    elif rank <= 50: god_score += 1.0; god_items.append(f"G2-全市场成交第{rank}")

    if stock.get('is_main_theme_leader'):
        god_score += 2.5; god_items.append("G3-主线龙头")
    elif stock.get('is_main_theme_core'):
        god_score += 1.5; god_items.append("G3-主线核心成员")
    elif stock.get('is_branch_theme_leader'):
        god_score += 0.5; god_items.append("G3-支线龙头(降权)")
    else:
        god_items.append("G3-非主流标的(-)")

    run = stock.get('run_days', 0)
    if run >= 20: god_score += 2
    elif run >= 10: god_score += 1.5
    elif run >= 5: god_score += 1
    god_items.append(f"G4-运行{run}天{'(真实)' if run>=10 else '(验证中)' if run>=3 else ''}")
    god_score = min(10, god_score)

    # 判词
    if god_score >= 7 and form_score >= 7:
        verdict = "神形兼备 — 真龙概率极高"
    elif god_score >= 7 and form_score < 5:
        verdict = "神似形不似 — 真龙潜质，短期技术待修复"
    elif god_score < 5 and form_score >= 7:
        verdict = "形似神不似 — ⚠️警惕人造龙头!"
    elif god_score < 5 and form_score < 5:
        verdict = "神形皆不符 — 非龙头"
    else:
        verdict = "需进一步观察"

    fake_risk = "高" if (god_score < 5 and form_score >= 7) else ("中" if god_score < 6 else "低")

    return {
        'form_score': round(form_score, 1),
        'god_score': round(god_score, 1),
        'form_items': form_items,
        'god_items': god_items,
        'verdict': verdict,
        'fake_risk': fake_risk,
        'fake_warning': (
            "图形漂亮但缺乏内在地位支撑，可能是假龙头。市值越大越真实。"
            if god_score < 5 and form_score >= 7 else ""
        ),
    }


# ════════════════════════════════════
#  模块④：板块梯队 & 主线判断
# ════════════════════════════════════

def build_sector_ladder(stocks: list[dict]) -> dict:
    """构建板块梯队结构"""
    sorted_stocks = sorted(
        stocks,
        key=lambda x: (x.get('consecutive_boards', 0), x.get('chg_pct', 0), x.get('amount', 0)),
        reverse=True,
    )
    ladder = {
        'dragon': sorted_stocks[0] if len(sorted_stocks) > 0 else None,
        'dragon_2': sorted_stocks[1] if len(sorted_stocks) > 1 else None,
        'dragon_3': sorted_stocks[2] if len(sorted_stocks) > 2 else None,
        'followers': sorted_stocks[3:] if len(sorted_stocks) > 3 else [],
    }
    health = _calc_ladder_health(ladder)
    ladder['health_score'] = health
    ladder['health_grade'] = _grade_health(health)
    return ladder


def _calc_ladder_health(ladder: dict) -> float:
    score = 0.0
    d = ladder.get('dragon')
    if d:
        score += 3 + min(2, d.get('consecutive_boards', 0) * 0.4)
    if ladder.get('dragon_2'): score += 2
    if ladder.get('dragon_3'): score += 1

    followers = ladder.get('followers', [])
    if len(followers) >= 5: score += 2
    elif len(followers) >= 3: score += 1.5
    elif followers: score += 1

    if d and ladder.get('dragon_2'):
        if d.get('chg_pct', 0) > 5 and ladder['dragon_2'].get('chg_pct', 0) > 3:
            score += 1
        elif d.get('chg_pct', 0) > 5 and ladder['dragon_2'].get('chg_pct', 0) < 0:
            score -= 1

    return max(0, min(10, score))


def _grade_health(score: float) -> str:
    if score >= 8: return "A(优秀)"
    elif score >= 6: return "B(良好)"
    elif score >= 4: return "C(一般)"
    elif score >= 2: return "D(较弱)"
    else: return "F(危险)"


def judge_mainline(sectors: list, sentiment_score: float) -> dict:
    """主线判断"""
    if not sectors:
        return {'exists': False, 'reason': '无活跃板块'}

    top = sectors[0] if sectors else {}
    # 各条件数据缺失(None)时跳过该项判定，不按0/假数据触发假信号
    _zt_ratio = top.get('zt_ratio')
    _ladder_health = top.get('ladder_health')
    _active_days = top.get('active_days')
    cond1 = None if _zt_ratio is None else _zt_ratio >= 0.20
    cond2 = None if _ladder_health is None else _ladder_health >= 3
    cond3 = None if _active_days is None else _active_days >= 2
    level = _classify_theme_level(top)
    known = [c for c in (cond1, cond2, cond3) if c is not None]
    exists = bool(known) and all(known)
    missing = [name for name, c in
               (('c1_占比达标', cond1), ('c2_梯队健康', cond2), ('c3_持续活跃', cond3))
               if c is None]

    result = {
        'exists': exists,
        'top_sector': top.get('name', ''),
        'level': level.value[0] if exists else None,
        'conditions': {'c1_占比达标': cond1, 'c2_梯队健康': cond2, 'c3_持续活跃': cond3},
        'strength': (
            "极强" if sentiment_score >= 8 and exists
            else "存在" if sentiment_score >= 5 and exists
            else "偏弱" if exists
            else "无明显主线"
        ),
    }
    if missing:
        result['data_note'] = f"数据缺失未参与评分: {', '.join(missing)}"
    return result


def _classify_theme_level(info: dict) -> ThemeLevel:
    signals = 0
    if info.get('policy_level') == 'national': signals += 1
    if info.get('duration_days', 0) >= 10: signals += 1
    if info.get('market_volume_ratio', 0) >= 0.15: signals += 1
    if info.get('has_complete_ladder'): signals += 1

    if signals >= 2: return ThemeLevel.MAINSTREAM
    if info.get('duration_days', 0) >= 3 and info.get('market_volume_ratio', 0) >= 0.05:
        return ThemeLevel.SUB_STREAM
    if info.get('duration_days', 0) >= 1: return ThemeLevel.MINOR_STREAM
    return ThemeLevel.NO_THEME


THEME_LEVEL_STRATEGY = {
    ThemeLevel.MAINSTREAM: {"hold_period": "1-4周", "position": "50-100%", "tactics": "打板/半路/低吸"},
    ThemeLevel.SUB_STREAM: {"hold_period": "3-7天", "position": "20-50%", "tactics": "打板为主"},
    ThemeLevel.MINOR_STREAM: {"hold_period": "1-2天", "position": "10-20%", "tactics": "只能打板"},
}


# ════════════════════════════════════
#  模块⑤：策略生成引擎
# ════════════════════════════════════

def generate_strategy(outputs: dict) -> dict:
    """策略生成主函数"""
    sentiment = outputs.get('sentiment', {})
    three_el = outputs.get('three_elements', {})
    sector = outputs.get('sector', {})

    score = sentiment.get('score', 5)
    phase = sentiment.get('phase', '🧊 冰点')

    # 第一层：总体定调
    tone, overall_advice = _gen_tone_and_advice(score, phase)
    strategy = {'tone': tone, 'overall_advice': overall_advice}

    # 第二层：仓位建议
    strategy['position'] = _gen_position(score, phase)

    # 第三层：方向选择
    mainline = sector.get('mainline', {})
    strategy['direction'] = _gen_direction(mainline, three_el)

    # 第四层：战术选择
    strategy['tactics'] = select_tactics(phase)

    # 第五层：风控铁律
    strategy['iron_rules'] = generate_iron_rules(phase, score)

    # 第六层：心理建设
    reflex = outputs.get('reflexivity', {})
    strategy['mindset'] = {
        'reflexivity_warning': reflex.get('reflexivity_warning', ''),
        'daily_reminder': _get_daily_reminder(score, phase),
    }

    # 置信度汇总
    strategy['confidence_summary'] = {
        'sentiment_confidence': sentiment.get('confidence', '?'),
    }

    return strategy


def _gen_tone_and_advice(score: float, phase: str) -> tuple[str, str]:
    if score <= 2:
        return "🧊 极寒 — 空仓保命", "空仓为主，1/10仓保持盘感"
    elif score <= 4:
        return "❄️ 严冬 — 试错为主", "极小仓试错首板，只做最强"
    elif score <= 5.5:
        return "🔄 僵持 — 看戏为宜", "弱修复阶段看戏! 每天≤1只小仓"
    elif score <= 7:
        return "☀️ 春暖 — 积极做多", "积极做多主线龙头，仓位30-50%"
    elif score <= 8.5:
        return "🔥 盛夏 — 重仓出击", "重仓参与主线龙头，单票≤30%"
    else:
        return "🚀 酷暑 — 兑现时刻", "狂热中兑现利润，不追新仓位"


def _gen_position(score: float, phase: str) -> dict:
    """仓位精算"""
    if score <= 2:
        rec = "≤10%"
    elif score <= 4:
        rec = "10-20%"
    elif score <= 5.5:
        rec = "≤10%(看戏)"
    elif score <= 7:
        rec = "30-50%"
    elif score <= 8.5:
        rec = "50-80%"
    else:
        rec = "逐步减仓至30-50%"

    t1_penalty = 0.2 if score <= 4 else (0.1 if score <= 5.5 else 0)

    return {
        'recommended_max': rec,
        't1_penalty': f"{int(t1_penalty*100)}%" if t1_penalty > 0 else "无",
        'single_stock_limit': "≤30%",
        'note': "T+1制度下买错当天无法纠错，弱势环境需更保守",
    }


def _gen_direction(mainline: dict, dragon: dict) -> dict:
    direction = {}

    if mainline.get('exists'):
        direction['main_direction'] = f"聚焦主线: {mainline.get('top_sector', '')}"
        direction['level'] = mainline.get('level', '')

        if dragon and dragon.get('is_real_dragon'):
            name = dragon.get('stock_name', dragon.get('name', '未知'))
            ov = dragon.get('overall', '?')
            verdict = dragon.get('god_form_analysis', {}).get('verdict', '')
            direction['specific_target'] = f"真龙: {name} ({ov}分, {verdict})"
        else:
            direction['specific_target'] = "暂无确认真龙，关注最强1-2只"
    else:
        direction['main_direction'] = "无明显主线"

    return direction


TACTICS_MATRIX = {
    "🧊 冰点":       {"打板": 1, "半路": 0, "低吸": 1, "回封": 0, "竞价": 0, "尾盘": 0},
    "❄️ 冰点边缘":   {"打板": 2, "半路": 1, "低吸": 2, "回封": 1, "竞价": 1, "尾盘": 1},
    "🔄 弱修复":     {"打板": 0, "半路": 0, "低吸": 0, "回封": 0, "竞价": 0, "尾盘": 0},
    "🔥 修复期":     {"打板": 4, "半路": 3, "低吸": 3, "回封": 4, "竞价": 3, "尾盘": 2},
    "🔥🔥 亢奋前期": {"打板": 5, "半路": 4, "低吸": 3, "回封": 5, "竞价": 4, "尾盘": 3},
    "🚀 亢奋高潮":   {"打板": 4, "半路": 3, "低吸": 2, "回封": 3, "竞价": 4, "尾盘": 3},
}

TACTIC_NOTES = {
    '打板': "打板确认强势，注意炸板率和封单强度",
    '半路': "半路追涨需配合放量+板块共振，风险较高",
    '低吸': "低吸适合趋势股回调或冰点期超跌，需严格止损",
    '回封': "回封是分歧转一致的确认信号，可轻仓参与",
    '竞价': "竞价关注弱转强的集合竞价信号",
    '尾盘': "尾盘仅作为次日观察备选，不宜当日入场",
}


def select_tactics(phase: str) -> dict:
    base = TACTICS_MATRIX.get(phase, {}).copy()

    if '弱修复' in phase:
        return {
            'recommendations': base,
            'best_tactic': 'None',
            'best_score': 0,
            'notes': '当前阶段不建议任何主动战术',
        }

    sorted_tac = sorted(base.items(), key=lambda x: x[1], reverse=True)
    best = sorted_tac[0] if sorted_tac else ('None', 0)

    return {
        'recommendations': dict(sorted_tac),
        'best_tactic': best[0],
        'best_score': best[1],
        'notes': TACTIC_NOTES.get(best[0], ""),
    }


def generate_iron_rules(phase: str, score: float) -> list[str]:
    rules = ["=== 🛡️ 今日风控铁律（不可违反）==="]

    rules.extend([
        "① 单票仓位 ≤ 总资产30%",
        "② 日内亏损达总资产2% → 停止操作",
        "③ 禁止临时起意，只做计划内操作",
        "④ 手风不顺 → 第二天赚钱就走",
        "⑤ 杜绝成本思维和仓位思维",
    ])

    if score <= 2:
        rules.extend(["⑥ 冰点: ≤1只, 仓≤10%", "⑦ 禁止一切追高/打板",
                     "⑧ 少即是多。一年2-3波行情"])
    elif '弱修复' in phase:
        rules.extend(["⑥ 弱修复: 看戏!", "⑦ 确要做: ≤1只, ≤10%",
                     "⑧ 经验够了盘面博弈让你条件反射"])
    elif score >= 8.5:
        rules.extend(["⑥ 亢奋高潮: 减仓不开新重仓",
                     "⑦ 战胜以丧礼处之，大胜后警惕乐极生悲"])

    return rules


def _get_daily_reminder(score: float, phase: str) -> str:
    reminders = {
        "🧊 冰点": "冰点期是布局良机，但需要耐心等信号确认",
        "❄️ 冰点边缘": "边缘地带最考验纪律，宁可错过不可做错",
        "🔄 弱修复": "看戏也是交易的一部分",
        "🔥 修复期": "赚钱效应回归时敢于上仓位，但要聚焦主线",
        "🔥🔥 亢奋前期": "好行情不常有，抓住机会但不忘风控",
        "🚀 亢奋高潮": "别人贪婪时恐惧一点，开始分批兑现",
    }
    return reminders.get(phase, "保持冷静，按计划执行")


# ════════════════════════════════════
#  模块⑪：人性博弈层（简化版）
# ════════════════════════════════════

def analyze_reflexivity_cycle(market_state: dict) -> dict:
    """反身性循环分析"""
    sentiment_score = market_state.get('sentiment_score', 5)
    zt_count = market_state.get('zt_count', 0)

    if sentiment_score >= 8.5 and zt_count >= 80:
        position = "正向加强晚期（过热区）"; risk = "极"; action = "逐步减仓"
        warning = "市场已被推向高潮，F'(Y)即将反转"
    elif sentiment_score >= 7 and zt_count >= 50:
        position = "正向加强中期"; risk = "中"; action = "持股/择机加仓"
        warning = "资金不断进入，赚钱效应自我强化"
    elif 4 <= sentiment_score < 6:
        position = "过冷区/转折临界点"; risk = "中"; action = "开始积极做多"
        warning = "情绪已达冰点附近，F'(Y)可能转向正面"
    elif sentiment_score < 4:
        position = "反向加强中（恐慌蔓延）"; risk = "高"; action = "空仓等待"
        warning = "亏钱效应扩散导致恐慌宣泄"
    else:
        position = "过渡区"; risk = "中低"; action = "观望为主"
        warning = "市场在选择方向"

    return {
        'cycle_position': position,
        'risk_level': risk,
        'reflexivity_warning': warning,
        'suggested_action': action,
        'insight': "你是要做主流Y里面的F(X)，不要做别的X。",
    }


def behavior_chain_monitor(data: dict) -> list[str]:
    """行为链条监控"""
    alerts = []
    avg = data.get('yest_zt_avg_chg')

    if avg is None:
        alerts.append("ℹ️ 追涨者: 昨日涨停表现数据缺失，未参与判定")
        return alerts

    if avg >= 5:
        alerts.append("✅ 追涨者: 赚钱效应强 → 模仿资金可能进场")
    elif 1 <= avg < 5:
        alerts.append("📈 追涨者: 有效应 → 热情维持中")
    elif -2 <= avg < 1:
        alerts.append("⚠️ 追涨者: 效应减弱 → 趋于谨慎")
    else:
        alerts.append("🔴 追涨者: 追涨亏钱 → 活跃度将进一步下降")

    return alerts


# ════════════════════════════════════
#  端到端Pipeline（容错版）
# ════════════════════════════════════

DEFAULT_SENTIMENT = {'score': 5.0, 'phase': '🔄 弱修复', 'dim_scores': {},
                     'warnings': ['使用默认值'], 'confidence': 30}


def daily_sentiment_pipeline(raw_data: dict) -> dict:
    """
    完整的情绪分析Pipeline
    
    输入: raw_data 来自 astock_data.py 的 full_review() 输出
    输出: 包含情绪评分、策略建议的完整分析报告
    """
    report = {'date': raw_data.get('date', 'unknown'), 'errors': [], 'warnings': []}

    def safe_run(step_name, fn, fallback):
        try:
            result = fn()
            report[step_name] = result
            return result
        except Exception as e:
            msg = f"[{step_name}] 异常: {str(e)}"
            report['errors'].append(msg)
            report['warnings'].append(f"⚠️ {step_name}降级为默认值")
            report[step_name] = fallback
            return fallback

    # Step 0: 构建SentimentInput
    input_data = _build_sentiment_input(raw_data)
    val_errors = input_data.validate()
    if val_errors:
        report['warnings'].extend([f"数据校验: {e}" for e in val_errors])

    # Step 1: 情绪计分卡
    report['sentiment'] = safe_run('sentiment',
        lambda: calc_sentiment_score(input_data), DEFAULT_SENTIMENT)

    # Step 2: 龙头三要素（取最高板股票）
    report['three_elements'] = safe_run('three_elements',
        lambda: _run_dragon_analysis(raw_data), {})

    # Step 3: 板块梯队 + 主线
    report['sector'] = safe_run('sector',
        lambda: _build_sector_analysis(raw_data, report.get('sentiment', {})), {})

    # Step 4: 反身性循环
    report['reflexivity'] = safe_run('reflexivity',
        lambda: analyze_reflexivity_cycle({
            'sentiment_score': report.get('sentiment', {}).get('score', 5),
            'zt_count': raw_data.get('zt_dt', {}).get('zt_count', 0),
            'dt_count': raw_data.get('zt_dt', {}).get('dt_count', 0),
        }), {})

    # Step 5: 行为链条
    report['behavior_chains'] = safe_run('behavior',
        lambda: behavior_chain_monitor(raw_data.get('zt_dt', {})), [])

    # Step 6: 策略生成
    report['strategy'] = safe_run('strategy',
        lambda: generate_strategy(report), DEFAULT_STRATEGY)

    # 汇总状态
    report['status'] = "✅ 完成" if not report['errors'] else f"⚠️ {len(report['errors'])}个异常"

    return report


def _build_sentiment_input(raw: dict) -> SentimentInput:
    """从raw_data构建SentimentInput对象"""
    zt = raw.get('zt_dt', {})

    # 昨日反馈数据当前无真实来源：置 None = 数据缺失，下游遇 None 跳过判定/不扣分
    # （此前硬编码0会触发"L1-追涨亏损每天扣2分"等假信号）
    # TODO: 接入 premium_ladder.py 的真实 avg_chg / 晋级率 / 核按钮数
    yest_zt_avg_chg = None
    yest_promote_rate = None
    yest_nuclear = None

    # 如果有连板数据，尝试推断晋级率
    lb = raw.get('lianban', {})
    summary = lb.get('summary', {})
    lianban_count = summary.get('total_lianban', zt.get('lianban_count', 0))

    return SentimentInput(
        zt_count=zt.get('zt_count', 0),
        zt_count_yesterday=zt.get('zt_count_yesterday', 0),
        lianban_count=lianban_count,
        max_lianban=zt.get('max_lianban', summary.get('max_height', 0)),
        zab_count=zt.get('zab_count', 0),
        try_zt_total=max(zt.get('try_zt_total', 1), 1),
        zab_rate=zt.get('zab_rate', 0.0),
        yest_zt_avg_chg=yest_zt_avg_chg,
        yest_lianban_promote_rate=yest_promote_rate,
        yest_duanban_nuclear=yest_nuclear,
        dt_count=zt.get('dt_count', 0),
        height_history=[3, 3, 3, 3, 3],  # 默认值，实际应从历史获取
        main_theme_clear=len(raw.get('sectors', {}).get('concept_top10', [])) > 0,
        main_theme_strength="中" if raw.get('sectors') else "无",
        theme_rotation_freq=0,
        has_tiandiban=False,
        has_ditianban=False,
        has_waipan_shock=False,
        is_weekend_ahead=False,
    )


def _run_dragon_analysis(raw: dict) -> dict:
    """对最高连板股进行龙头三要素诊断"""
    diag_stocks = raw.get('dragon_diagnosis', [])
    results = {}

    for stock in diag_stocks:
        code = stock.get('code', '')
        if not code:
            continue

        # 构建市场上下文
        sectors = raw.get('sectors', {})
        concept_top = sectors.get('concept_top10', [])
        avg_chg = 0.0
        if concept_top:
            avg_chg = sum(c.get('chg_pct', 0) for c in concept_top[:5]) / max(len(concept_top[:5]), 1)

        ctx = {
            'sector_avg_chg': avg_chg,
            'sentiment_score': 5.0,
        }

        dragon_result = calc_three_elements(stock, ctx)
        results[code] = {
            'name': stock.get('name', ''),
            'grade': dragon_result.grade,
            'overall': dragon_result.overall,
            'is_real_dragon': dragon_result.is_real_dragon,
            'god_form': dragon_result.god_form_analysis,
        }

    return results


def _build_sector_analysis(raw: dict, sentiment: dict) -> dict:
    """板块分析 + 主线判断

    zt_ratio/ladder_health/active_days 当前无真实数据来源，置 None = 数据缺失，
    judge_mainline 遇 None 跳过该条件判定并标注"数据缺失未参与评分"
    （此前硬编码 zt_ratio=0.1/active_days=1 会产生假信号）。
    TODO: 接入真实板块涨停占比/梯队健康度/持续活跃天数。
    """
    sec = raw.get('sectors', {})
    sectors_list = [{'name': c.get('name', ''), 'zt_ratio': None,
                     'ladder_health': None, 'active_days': None}
                    for c in sec.get('concept_top10', [])[:5]]

    mainline = judge_mainline(
        sectors_list,
        sentiment.get('score', 5),
    )
    return {'sectors_list': sectors_list[:3], 'mainline': mainline}


DEFAULT_STRATEGY = {
    'tone': 'N/A', 'overall_advice': 'Pipeline异常，请检查',
    'position': {}, 'direction': {}, 'tactics': {},
    'iron_rules': [], 'mindset': {}, 'confidence_summary': {},
}
