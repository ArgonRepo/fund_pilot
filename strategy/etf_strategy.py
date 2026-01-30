"""
FundPilot-AI 策略 A - ETF 联接基金网格交易策略
基于 250 日分位值进行决策（约 1 年窗口，避免短期行情失真）
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from strategy.indicators import QuantMetrics, get_percentile_zone
from core.logger import get_logger

logger = get_logger("etf_strategy")


class Decision(Enum):
    """决策类型"""
    DOUBLE_BUY = "双倍补仓"
    NORMAL_BUY = "正常定投"
    HOLD = "观望"
    STOP_BUY = "暂停定投"


@dataclass
class StrategyResult:
    """策略决策结果"""
    decision: Decision
    confidence: float       # 置信度 (0-1)
    reasoning: str          # 决策理由
    zone: str               # 分位区间描述


def evaluate_etf_strategy(metrics: QuantMetrics) -> StrategyResult:
    """
    评估 ETF 联接基金策略
    
    网格交易逻辑（基于 250 日分位值）：
    - 黄金坑 (分位 < 20%)：双倍补仓 (x1.5 ~ x2.0)
    - 低估区 (分位 20%-40%)：正常定投
    - 合理区 (分位 40%-60%)：正常定投 / 观望（看均线位置）
    - 偏高区 (分位 60%-80%)：观望，不追高
    - 高估区 (分位 > 80%)：暂停定投（积攒现金）
    
    Args:
        metrics: 量化指标（包含 250 日分位值）
    
    Returns:
        StrategyResult 决策结果
    """
    percentile = metrics.percentile_250
    zone = get_percentile_zone(percentile)
    
    # 黄金坑：双倍补仓
    if percentile < 20:
        decision = Decision.DOUBLE_BUY
        confidence = 0.9 if percentile < 10 else 0.8
        reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，建议加大定投力度"
    
    # 低估区：正常定投
    elif percentile < 40:
        decision = Decision.NORMAL_BUY
        confidence = 0.75
        reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，适合正常定投"
    
    # 合理区：观望或正常定投（依据均线位置）
    elif percentile < 60:
        # 如果均线偏离为负（低于均线），建议定投
        if metrics.ma_deviation < -2:  # 低于均线 2% 以上
            decision = Decision.NORMAL_BUY
            confidence = 0.65
            reasoning = f"250日分位 {percentile:.1f}%，低于60日均线 {abs(metrics.ma_deviation):.1f}%，可正常定投"
        elif metrics.ma_deviation < 0:
            decision = Decision.NORMAL_BUY
            confidence = 0.55
            reasoning = f"250日分位 {percentile:.1f}%，略低于均线，可正常定投"
        else:
            decision = Decision.HOLD
            confidence = 0.5
            reasoning = f"250日分位 {percentile:.1f}%，处于{zone}且高于均线，可观望等待机会"
    
    # 偏高区：观望
    elif percentile < 80:
        decision = Decision.HOLD
        confidence = 0.75
        reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，建议观望不追高"
    
    # 高估区：暂停定投
    else:
        decision = Decision.STOP_BUY
        confidence = 0.9 if percentile > 90 else 0.8
        reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，建议暂停定投积攒弹药"
    
    logger.info(f"ETF策略决策: {decision.value} (分位: {percentile:.1f}%, 区间: {zone})")
    
    return StrategyResult(
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        zone=zone
    )


def get_buy_multiplier(percentile: float) -> float:
    """
    获取补仓倍数
    
    Args:
        percentile: 250日分位值
    
    Returns:
        补仓倍数 (1.0 = 正常，2.0 = 双倍，0.0 = 暂停)
    """
    if percentile < 10:
        return 2.0
    elif percentile < 20:
        return 1.5
    elif percentile < 40:
        return 1.2
    elif percentile < 60:
        return 1.0
    elif percentile < 80:
        return 0.5  # 偏高区减半
    else:
        return 0.0  # 高估区暂停
