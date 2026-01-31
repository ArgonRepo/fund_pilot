"""
FundPilot-AI 策略 A - ETF 联接基金网格交易策略
基于多周期分位值交叉验证进行决策

重要更新 v2.0：
- 多周期分位共识验证（避免单一周期锚定偏误）
- 动态均线偏离阈值（基于品种波动率）
- 趋势方向辅助判断
- 极端行情熔断机制
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from strategy.indicators import QuantMetrics, get_percentile_zone, get_dynamic_ma_threshold
from core.logger import get_logger

logger = get_logger("etf_strategy")


# 极端行情熔断阈值
CIRCUIT_BREAKER_DROP = -7.0   # 单日跌幅超过 7% 暂停决策
CIRCUIT_BREAKER_RISE = 7.0    # 单日涨幅超过 7% 暂停决策


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
    warnings: list[str]     # 风险提示列表


def evaluate_etf_strategy(metrics: QuantMetrics) -> StrategyResult:
    """
    评估 ETF 联接基金策略（增强版）
    
    核心变化：
    1. 使用多周期分位共识验证，避免单一锚定
    2. 动态均线偏离阈值（根据波动率调整）
    3. 极端行情熔断机制
    
    网格交易逻辑（基于 250 日分位值 + 多周期验证）：
    - 黄金坑 (分位 < 20%)：双倍补仓 (需多周期确认)
    - 低估区 (分位 20%-40%)：正常定投
    - 合理区 (分位 40%-60%)：正常定投 / 观望（看均线位置）
    - 偏高区 (分位 60%-80%)：观望，不追高
    - 高估区 (分位 > 80%)：暂停定投（积攒现金）
    
    Args:
        metrics: 量化指标（包含多周期分位值）
    
    Returns:
        StrategyResult 决策结果
    """
    warnings = []
    
    # === 熔断检查 ===
    if metrics.daily_change is not None:
        if metrics.daily_change < CIRCUIT_BREAKER_DROP:
            return StrategyResult(
                decision=Decision.HOLD,
                confidence=0.3,
                reasoning=f"触发熔断：单日大跌 {metrics.daily_change:.1f}%，建议冷静观察，次日再决策",
                zone="熔断",
                warnings=["⚠️ 极端行情熔断：跌幅过大，暂停决策"]
            )
        if metrics.daily_change > CIRCUIT_BREAKER_RISE:
            return StrategyResult(
                decision=Decision.HOLD,
                confidence=0.3,
                reasoning=f"触发熔断：单日大涨 {metrics.daily_change:.1f}%，建议冷静观察，次日再决策",
                zone="熔断",
                warnings=["⚠️ 极端行情熔断：涨幅过大，暂停决策"]
            )
    
    # === 多周期分位共识 ===
    percentile = metrics.percentile_250  # 主要参考
    consensus = metrics.percentile_consensus
    trend = metrics.trend_direction
    zone = get_percentile_zone(percentile)
    
    # 动态均线偏离阈值
    dynamic_ma_threshold = get_dynamic_ma_threshold(metrics.volatility_60)
    
    # 共识冲突警告
    if consensus == "分歧":
        warnings.append(f"⚠️ 多周期分位分歧：60日={metrics.percentile_60:.0f}%，250日={metrics.percentile_250:.0f}%，500日={metrics.percentile_500:.0f}%")
    
    # 趋势警告
    if trend == "上升趋势" and percentile > 60:
        warnings.append("📈 短期强于长期，可能处于趋势高点")
    if trend == "下降趋势" and percentile < 40:
        warnings.append("📉 短期弱于长期，可能仍有下跌空间")
    
    # === 决策逻辑 ===
    
    # 黄金坑：双倍补仓（需多周期确认）
    if percentile < 20:
        if consensus in ["强低估", "弱低估"]:
            decision = Decision.DOUBLE_BUY
            confidence = 0.9 if consensus == "强低估" else 0.75
            reasoning = f"250日分位 {percentile:.1f}%，多周期共识「{consensus}」，珍惜黄金坑加仓机会"
        else:
            # 短期分位与长期不一致，谨慎处理
            decision = Decision.NORMAL_BUY
            confidence = 0.6
            reasoning = f"250日分位 {percentile:.1f}% 处于黄金坑，但多周期「{consensus}」，建议正常定投观察"
            warnings.append("⚠️ 长期分位偏高，短期低估可能是假象")
    
    # 低估区：正常定投
    elif percentile < 40:
        decision = Decision.NORMAL_BUY
        if consensus in ["强低估", "弱低估"]:
            confidence = 0.8
            reasoning = f"250日分位 {percentile:.1f}%，多周期共识「{consensus}」，适合正常定投"
        else:
            confidence = 0.65
            reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，可正常定投"
    
    # 合理区：观望或正常定投（依据均线位置和动态阈值）
    elif percentile < 60:
        if metrics.ma_deviation < dynamic_ma_threshold:
            # 显著低于均线（使用动态阈值）
            decision = Decision.NORMAL_BUY
            confidence = 0.65
            reasoning = f"250日分位 {percentile:.1f}%，低于均线 {abs(metrics.ma_deviation):.1f}%（阈值 {abs(dynamic_ma_threshold):.1f}%），可正常定投"
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
        if consensus in ["强高估", "弱高估"]:
            confidence = 0.85
            reasoning = f"250日分位 {percentile:.1f}%，多周期共识「{consensus}」，严禁追高"
        else:
            confidence = 0.7
            reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，建议观望不追高"
    
    # 高估区：暂停定投
    else:
        decision = Decision.STOP_BUY
        if consensus in ["强高估", "弱高估"]:
            confidence = 0.95
            reasoning = f"250日分位 {percentile:.1f}%，多周期共识「{consensus}」，坚决暂停定投积攒弹药"
        else:
            confidence = 0.8
            reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，建议暂停定投积攒弹药"
            if consensus == "分歧":
                warnings.append("📊 多周期存在分歧，可小幅减少暂停力度")
    
    logger.info(f"ETF策略决策: {decision.value} (分位: {percentile:.1f}%, 共识: {consensus}, 区间: {zone})")
    
    return StrategyResult(
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        zone=zone,
        warnings=warnings
    )


def get_buy_multiplier(percentile: float, consensus: str = "分歧") -> float:
    """
    获取补仓倍数（增强版）
    
    Args:
        percentile: 250日分位值
        consensus: 多周期共识
    
    Returns:
        补仓倍数 (1.0 = 正常，2.0 = 双倍，0.0 = 暂停)
    """
    base_multiplier = 1.0
    
    if percentile < 10:
        base_multiplier = 2.0
    elif percentile < 20:
        base_multiplier = 1.5
    elif percentile < 40:
        base_multiplier = 1.2
    elif percentile < 60:
        base_multiplier = 1.0
    elif percentile < 80:
        base_multiplier = 0.5  # 偏高区减半
    else:
        base_multiplier = 0.0  # 高估区暂停
    
    # 共识调整
    if consensus == "强低估" and base_multiplier > 0:
        base_multiplier = min(2.0, base_multiplier * 1.2)
    elif consensus == "强高估" and base_multiplier > 0:
        base_multiplier = max(0, base_multiplier * 0.5)
    
    return base_multiplier
