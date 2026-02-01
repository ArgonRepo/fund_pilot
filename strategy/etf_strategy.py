"""
FundPilot-AI 策略 A - ETF 联接基金网格交易策略
基于多周期分位值交叉验证进行决策

重要更新 v3.0：
- 资产类型感知：根据 asset_class 动态调整阈值
- 多周期分位共识验证（避免单一周期锚定偏误）
- 动态均线偏离阈值（基于品种波动率 + 资产类型）
- 趋势方向辅助判断
- 极端行情熔断机制
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from strategy.indicators import QuantMetrics, get_dynamic_ma_threshold
from strategy.asset_config import (
    AssetClass, StrategyThresholds, 
    get_thresholds, get_zone_name, infer_asset_class
)
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
    warnings: list[str]     # 风险提示列表


def evaluate_etf_strategy(
    metrics: QuantMetrics, 
    asset_class: Optional[str] = None,
    fund_name: str = "",
    market_drop: Optional[float] = None
) -> StrategyResult:
    """
    评估 ETF 联接基金策略（资产感知版 v3.1）
    
    核心变化：
    1. 根据 asset_class 获取动态阈值
    2. 使用多周期分位共识验证，避免单一锚定
    3. 动态均线偏离阈值（基于波动率 + 资产类型）
    4. 极端行情熔断机制
    5. 黄金ETF考虑大盘表现（对冲配置）
    
    Args:
        metrics: 量化指标（包含多周期分位值）
        asset_class: 资产类别 (GOLD_ETF / COMMODITY_CYCLE 等)
        fund_name: 基金名称（用于推断 asset_class）
        market_drop: 大盘跌幅（负值，用于黄金对冲判断）
    
    Returns:
        StrategyResult 决策结果
    """
    warnings: list[str] = []
    
    # === 获取资产类型对应的阈值 ===
    if not asset_class:
        asset_class = infer_asset_class("ETF_Feeder", fund_name)
    
    thresholds = get_thresholds(asset_class)
    zones = thresholds.zone_thresholds  # (黄金坑, 低估, 高估, 过热)
    
    logger.debug(f"使用资产类型 {asset_class} 阈值: {zones}")
    
    # === 熔断检查 ===
    if metrics.daily_change is not None:
        if metrics.daily_change < thresholds.circuit_breaker_drop:
            return StrategyResult(
                decision=Decision.HOLD,
                confidence=0.3,
                reasoning=f"触发熔断：单日大跌 {metrics.daily_change:.1f}%，建议冷静观察，次日再决策",
                zone="熔断",
                warnings=["⚠️ 极端行情熔断：跌幅过大，暂停决策"]
            )
        if metrics.daily_change > thresholds.circuit_breaker_rise:
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
    zone = get_zone_name(percentile, thresholds)
    
    # 动态均线偏离阈值（结合波动率和资产基准）
    volatility_threshold = get_dynamic_ma_threshold(metrics.volatility_60)
    dynamic_ma_threshold = min(volatility_threshold, thresholds.ma_base_threshold)
    
    # 共识冲突警告
    if consensus == "分歧":
        warnings.append(f"⚠️ 多周期分位分歧：60日={metrics.percentile_60:.0f}%，250日={metrics.percentile_250:.0f}%，500日={metrics.percentile_500:.0f}%")
    
    # 趋势警告
    if trend == "上升趋势" and percentile > zones[2]:  # 高于高估阈值
        warnings.append("📈 短期强于长期，可能处于趋势高点")
    if trend == "下降趋势" and percentile < zones[1]:  # 低于低估阈值
        warnings.append("📉 短期弱于长期，可能仍有下跌空间")
    
    # === 资产特性提示（仅在特定条件下显示）===
    if asset_class == AssetClass.GOLD_ETF.value and percentile < zones[3]:
        # 只在非高估区提示，高估区有专门逻辑
        warnings.append("💡 黄金为避险资产，高估不一定暂停，需考虑对冲需求")
    elif asset_class == AssetClass.COMMODITY_CYCLE.value:
        warnings.append("💡 周期资产易长期处于极端分位，需逆向思维")
    
    # === 决策逻辑（使用动态阈值）===
    decision: Decision
    confidence: float
    reasoning: str
    
    # 黄金坑：双倍补仓（需多周期确认）
    if percentile < zones[0]:  # 动态黄金坑阈值
        if consensus in ["强低估", "弱低估"]:
            decision = Decision.DOUBLE_BUY
            confidence = 0.9 if consensus == "强低估" else 0.75
            reasoning = f"250日分位 {percentile:.1f}%（<{zones[0]:.0f}%），多周期共识「{consensus}」，珍惜黄金坑加仓机会"
        else:
            # 短期分位与长期不一致，谨慎处理
            decision = Decision.NORMAL_BUY
            confidence = 0.6
            reasoning = f"250日分位 {percentile:.1f}% 处于黄金坑，但多周期「{consensus}」，建议正常定投观察"
            warnings.append("⚠️ 长期分位偏高，短期低估可能是假象")
    
    # 低估区：正常定投
    elif percentile < zones[1]:  # 动态低估阈值
        decision = Decision.NORMAL_BUY
        if consensus in ["强低估", "弱低估"]:
            confidence = 0.8
            reasoning = f"250日分位 {percentile:.1f}%，多周期共识「{consensus}」，适合正常定投"
        else:
            confidence = 0.65
            reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，可正常定投"
    
    # 合理区：观望或正常定投（依据均线位置和动态阈值）
    elif percentile < zones[2]:  # 动态高估阈值
        if metrics.ma_deviation < dynamic_ma_threshold:
            # 显著低于均线
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
    elif percentile < zones[3]:  # 动态过热阈值
        decision = Decision.HOLD
        if consensus in ["强高估", "弱高估"]:
            confidence = 0.85
            reasoning = f"250日分位 {percentile:.1f}%，多周期共识「{consensus}」，严禁追高"
        else:
            confidence = 0.7
            reasoning = f"250日分位 {percentile:.1f}%，处于{zone}，建议观望不追高"
    
    # 高估区：暂停定投
    else:
        # 黄金 ETF 特殊处理：考虑大盘表现
        if asset_class == AssetClass.GOLD_ETF.value:
            # 大盘暴跌时，黄金高估体现对冲价值，应正常定投
            if market_drop is not None and market_drop < -2.0:
                decision = Decision.NORMAL_BUY
                confidence = 0.65
                reasoning = f"250日分位 {percentile:.1f}%，黄金高估但大盘跌 {abs(market_drop):.1f}%，对冲配置价值显现，建议正常定投"
                warnings.append("🛡️ 大盘下跌时黄金具备对冲价值")
            else:
                decision = Decision.HOLD
                confidence = 0.6
                reasoning = f"250日分位 {percentile:.1f}%，黄金高估但具避险价值，建议观望而非暂停"
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
    
    logger.info(f"ETF策略决策: {decision.value} (资产: {asset_class}, 分位: {percentile:.1f}%, 共识: {consensus}, 区间: {zone})")
    
    return StrategyResult(
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        zone=zone,
        warnings=warnings
    )


def get_buy_multiplier(
    percentile: float, 
    consensus: str = "分歧",
    asset_class: Optional[str] = None
) -> float:
    """
    获取补仓倍数（资产感知版 v3.1）
    
    周期资产分批建仓逻辑：
    - 分位 <5%：2倍
    - 分位 5-10%：1.5倍
    - 分位 10-15%：1.2倍
    - 分位 15-30%：正常
    
    Args:
        percentile: 250日分位值
        consensus: 多周期共识
        asset_class: 资产类型
    
    Returns:
        补仓倍数 (1.0 = 正常，2.0 = 双倍，0.0 = 暂停)
    """
    thresholds = get_thresholds(asset_class or "DEFAULT_ETF")
    zones = thresholds.zone_thresholds
    
    # 周期资产使用分批建仓逻辑，避免一次性重仓
    if asset_class == "COMMODITY_CYCLE":
        if percentile < 5.0:
            base_multiplier = 2.0
        elif percentile < 10.0:
            base_multiplier = 1.5
        elif percentile < zones[0]:  # 15%
            base_multiplier = 1.2
        elif percentile < zones[1]:  # 30%
            base_multiplier = 1.0
        elif percentile < zones[2]:  # 70%
            base_multiplier = 0.8
        elif percentile < zones[3]:  # 90%
            base_multiplier = 0.3
        else:
            base_multiplier = 0.0
    else:
        # 其他资产类型使用标准逻辑
        if percentile < zones[0] * 0.5:  # 极端低估
            base_multiplier = 2.0
        elif percentile < zones[0]:  # 黄金坑
            base_multiplier = 1.5
        elif percentile < zones[1]:  # 低估区
            base_multiplier = 1.2
        elif percentile < zones[2]:  # 合理区
            base_multiplier = 1.0
        elif percentile < zones[3]:  # 偏高区
            base_multiplier = 0.5
        else:  # 高估区
            base_multiplier = 0.0
    
    # 共识调整
    if consensus == "强低估" and base_multiplier > 0:
        base_multiplier = min(2.0, base_multiplier * 1.2)
    elif consensus == "强高估" and base_multiplier > 0:
        base_multiplier = max(0, base_multiplier * 0.5)
    
    return base_multiplier
