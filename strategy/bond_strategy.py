"""
FundPilot-AI 策略 B - 债券基金防守型策略
基于回撤幅度和均线乖离进行决策

重要更新 v3.0：
- 资产类型感知：区分 BOND_ENHANCED/BOND_PURE
- 动态阈值：基于品种历史波动率 + 资产类型自动调整
- 多周期分位交叉验证
- 利率环境提示（宏观因子）
- 极端行情熔断机制
"""

from dataclasses import dataclass
from typing import Optional

from strategy.indicators import QuantMetrics, get_dynamic_ma_threshold, get_dynamic_drop_threshold
from strategy.etf_strategy import Decision, StrategyResult
from strategy.asset_config import get_thresholds, AssetClass, infer_asset_class
from core.logger import get_logger

logger = get_logger("bond_strategy")




@dataclass
class BondSignal:
    """债券信号"""
    has_opportunity: bool     # 是否有买入机会
    signal_type: str          # 信号类型
    strength: float           # 信号强度 (0-1)
    is_overvalued: bool = False  # 是否处于高估区
    dynamic_thresholds: Optional[dict] = None  # 使用的动态阈值


def detect_bond_signal(
    metrics: QuantMetrics,
    asset_class: Optional[str] = None
) -> BondSignal:
    """
    检测债券买入信号（资产感知版 v3.0）
    
    信号条件（动态阈值）：
    1. 显著跌破 60 日均线（阈值根据波动率 + 资产类型动态调整）
    2. 单日跌幅超过阈值
    
    预警条件：
    - 250日分位 > zone_thresholds[3]（资产特定高估线）
    
    Args:
        metrics: 量化指标
        asset_class: 资产类型 (BOND_ENHANCED / BOND_PURE)
    
    Returns:
        BondSignal 信号
    """
    signals = []
    
    # 获取资产类型对应的阈值
    thresholds = get_thresholds(asset_class or "DEFAULT_BOND")
    
    # 动态阈值计算（结合波动率和资产类型）
    volatility_ma_threshold = get_dynamic_ma_threshold(metrics.volatility_60)
    ma_threshold = min(volatility_ma_threshold, thresholds.ma_base_threshold)
    drop_normal, drop_severe = get_dynamic_drop_threshold(metrics.volatility_60)
    
    dynamic_thresholds = {
        "ma_threshold": ma_threshold,
        "drop_normal": drop_normal,
        "drop_severe": drop_severe,
        "volatility_60": metrics.volatility_60,
        "asset_class": asset_class or "DEFAULT_BOND"
    }
    
    # 检查是否高估（使用资产特定阈值）
    overvalued_threshold = thresholds.zone_thresholds[3]  # 过热线
    is_overvalued = metrics.percentile_250 >= overvalued_threshold
    
    # 信号 1: 显著跌破 60 日均线（动态阈值）
    if metrics.ma_deviation < ma_threshold:
        # 偏离程度越大，信号越强
        strength = min(abs(metrics.ma_deviation) / (abs(ma_threshold) * 3), 1.0)
        signals.append(("跌破均线", strength))
    
    # 信号 2: 单日大跌（动态阈值）
    if metrics.daily_change is not None and metrics.daily_change < drop_normal:
        if metrics.daily_change < drop_severe:
            strength = 1.0  # 严重大跌
        else:
            # 线性映射
            strength = min((abs(metrics.daily_change) - abs(drop_normal)) / (abs(drop_severe) - abs(drop_normal)) * 0.5 + 0.5, 1.0)
        signals.append(("单日大跌", strength))
    
    if not signals:
        return BondSignal(
            has_opportunity=False,
            signal_type="正常波动",
            strength=0.0,
            is_overvalued=is_overvalued,
            dynamic_thresholds=dynamic_thresholds
        )
    
    # 取最强信号
    signals.sort(key=lambda x: x[1], reverse=True)
    best_signal = signals[0]
    
    # 多信号叠加增强
    total_strength = min(sum(s[1] for s in signals), 1.0)
    
    if len(signals) > 1:
        signal_type = " + ".join(s[0] for s in signals)
    else:
        signal_type = best_signal[0]
    
    return BondSignal(
        has_opportunity=True,
        signal_type=signal_type,
        strength=total_strength,
        is_overvalued=is_overvalued,
        dynamic_thresholds=dynamic_thresholds
    )


def evaluate_bond_strategy(
    metrics: QuantMetrics,
    asset_class: Optional[str] = None,
    fund_name: str = ""
) -> StrategyResult:
    """
    评估债券基金策略（资产感知版 v3.0）
    
    核心变化：
    1. 资产类型感知：区分 BOND_ENHANCED / BOND_PURE
    2. 动态阈值：根据品种波动率 + 资产类型自动调整
    3. 多周期分位验证
    4. 极端行情熔断
    
    防守型策略逻辑：
    - 极端行情：熔断，次日决策
    - 高估区（250日分位 > 资产过热线）：观望，提示风险
    - 正常波动：持有观望
    - 显著跌破均线或单日大跌：定投/补仓机会
    
    Args:
        metrics: 量化指标
        asset_class: 资产类型 (BOND_ENHANCED / BOND_PURE)
        fund_name: 基金名称（用于推断 asset_class）
    
    Returns:
        StrategyResult 决策结果
    """
    warnings = []
    
    # === 获取资产类型对应的阈值 ===
    if not asset_class:
        asset_class = infer_asset_class("Bond", fund_name)
    
    thresholds = get_thresholds(asset_class)
    circuit_breaker = thresholds.circuit_breaker_drop
    
    # === 熔断检查（使用资产类型动态阈值）===
    if metrics.daily_change is not None:
        if metrics.daily_change < circuit_breaker:
            return StrategyResult(
                decision=Decision.HOLD,
                confidence=0.3,
                reasoning=f"触发熔断：债券单日大跌 {metrics.daily_change:.2f}%（阈值 {circuit_breaker:.1f}%），极为罕见，建议冷静观察后决策",
                zone="熔断",
                warnings=[f"债券极端行情：跌幅罕见（{asset_class}），可能有重大风险事件"],
                buy_multiplier=0.0
            )
        if metrics.daily_change > thresholds.circuit_breaker_rise:
            return StrategyResult(
                decision=Decision.HOLD,
                confidence=0.3,
                reasoning=f"触发熔断：债券单日异常大涨 {metrics.daily_change:+.2f}%（阈值 {thresholds.circuit_breaker_rise:.1f}%），建议观望而非追高",
                zone="熔断",
                warnings=["债券异常大涨，可能是利率急降或市场情绪过热，建议观望"],
                buy_multiplier=0.0
            )
    
    signal = detect_bond_signal(metrics, asset_class)
    consensus = metrics.get_consensus_with_thresholds(
        thresholds.consensus_low_threshold, thresholds.consensus_high_threshold
    )
    
    # 动态阈值信息
    if signal.dynamic_thresholds:
        dynamic_info = signal.dynamic_thresholds
        warnings.append(
            f"动态阈值：均线偏离 {dynamic_info['ma_threshold']:.2f}%，"
            f"大跌 {dynamic_info['drop_normal']:.2f}%/{dynamic_info['drop_severe']:.2f}%"
            f"（基于 {dynamic_info['volatility_60']:.1f}% 年化波动率）"
        )
    
    # 多周期分位警告
    if consensus == "分歧":
        warnings.append(
            f"多周期分位分歧：60日={metrics.percentile_60:.0f}%，"
            f"250日={metrics.percentile_250:.0f}%，500日={metrics.percentile_1250:.0f}%"
        )
    
    # 趋势警告
    trend = metrics.trend_direction
    if trend == "上升趋势":
        warnings.append("债券短期走强，利率可能处于下行周期")
    if trend == "下降趋势":
        warnings.append("债券短期走弱，需关注利率上行风险")
    
    # === 高估区处理 ===
    if signal.is_overvalued:
        if signal.has_opportunity and signal.strength > 0.8:
            # 高估区但有强烈信号，可以小额定投
            decision = Decision.NORMAL_BUY
            confidence = 0.5
            buy_multiplier = 0.5
            reasoning = f"虽有{signal.signal_type}信号（强度 {signal.strength:.0%}），但250日分位 {metrics.percentile_250:.0f}% 偏高，建议小额定投"
            warnings.append("高估区补仓需控制仓位，建议减半")
        else:
            decision = Decision.HOLD
            confidence = 0.7
            buy_multiplier = 0.0
            reasoning = f"250日分位 {metrics.percentile_250:.0f}% 处于高位，债券估值偏贵，建议观望"
        
        zone = "高估区"
        
        # 多周期共识强化
        if consensus == "强高估":
            confidence = min(0.95, confidence + 0.1)
            reasoning += "，多周期共识「强高估」"
        
        logger.info(f"债券策略决策: {decision.value} (高估预警)")
        return StrategyResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            zone=zone,
            warnings=warnings,
            buy_multiplier=buy_multiplier
        )
    
    # === 正常估值区域 ===
    if signal.has_opportunity:
        # 有买入机会
        if signal.strength > 0.7:
            decision = Decision.DOUBLE_BUY
            confidence = 0.8
            buy_multiplier = min(2.0, 1.5 + signal.strength * 0.5)
            reasoning = f"债券出现{signal.signal_type}信号（强度 {signal.strength:.0%}），难得的加仓机会"
            
            # 多周期共识增强
            if consensus in ["强低估", "弱低估"]:
                confidence = min(0.95, confidence + 0.1)
                reasoning += f"，多周期共识「{consensus}」"
        else:
            decision = Decision.NORMAL_BUY
            confidence = 0.7
            buy_multiplier = 1.0
            reasoning = f"债券{signal.signal_type}，可适度加仓"
        
        zone = "机会区"
    else:
        # 正常波动：根据资产类型决定默认策略
        if asset_class == "BOND_ENHANCED":
            # M2: 二级债基正常区增加分位感知
            if metrics.percentile_250 < 40:
                # 低分位：积极定投
                decision = Decision.NORMAL_BUY
                confidence = 0.7
                buy_multiplier = 1.0
                if metrics.daily_change is not None:
                    if metrics.daily_change > 0:
                        reasoning = f"二级债基上涨 {metrics.daily_change:+.2f}%，分位{metrics.percentile_250:.0f}%偏低，保持定投节奏"
                    else:
                        reasoning = f"二级债基微跌 {metrics.daily_change:+.2f}%，分位{metrics.percentile_250:.0f}%偏低，正是定投好时机"
                else:
                    reasoning = f"二级债基平稳运行，分位{metrics.percentile_250:.0f}%偏低，建议保持定投节奏"
            elif metrics.percentile_250 < 55:
                # 中等分位：常规定投
                decision = Decision.NORMAL_BUY
                confidence = 0.55
                buy_multiplier = 0.8
                if metrics.daily_change is not None:
                    reasoning = f"二级债基今日 {metrics.daily_change:+.2f}%，分位{metrics.percentile_250:.0f}%处于均衡水平，常规定投"
                else:
                    reasoning = f"二级债基平稳运行，分位{metrics.percentile_250:.0f}%处于均衡水平，常规定投"
            else:
                # 接近偏高区：观望等回调
                decision = Decision.HOLD
                confidence = 0.5
                buy_multiplier = 0.0
                if metrics.daily_change is not None:
                    reasoning = f"二级债基今日 {metrics.daily_change:+.2f}%，分位{metrics.percentile_250:.0f}%接近偏高区，可等回调再定投"
                else:
                    reasoning = f"二级债基分位{metrics.percentile_250:.0f}%接近偏高区，建议等回调再定投"
            zone = "正常区"
        else:
            # 纯债或其他类型，可观望等待信号
            decision = Decision.HOLD
            confidence = 0.6
            buy_multiplier = 0.0
            if metrics.daily_change is not None:
                if metrics.daily_change > 0:
                    reasoning = f"债券今日上涨 {metrics.daily_change:+.2f}%，保持持有即可"
                else:
                    reasoning = f"债券今日微跌 {metrics.daily_change:+.2f}%，属正常波动无需担忧"
            else:
                reasoning = "债券平稳运行，保持持有即可"
            zone = "正常区"
    
    logger.info(f"债券策略决策: {decision.value} (信号: {signal.signal_type}, 倍数: {buy_multiplier:.1f}x)")
    
    return StrategyResult(
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        zone=zone,
        warnings=warnings,
        buy_multiplier=buy_multiplier
    )
