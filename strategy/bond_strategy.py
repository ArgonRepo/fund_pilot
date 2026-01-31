"""
FundPilot-AI 策略 B - 债券基金防守型策略
基于回撤幅度和均线乖离进行决策

重要更新 v2.0：
- 动态阈值：基于品种历史波动率自动调整
- 多周期分位交叉验证
- 利率环境提示（宏观因子）
- 极端行情熔断机制
"""

from dataclasses import dataclass
from typing import Optional

from strategy.indicators import QuantMetrics, get_dynamic_ma_threshold, get_dynamic_drop_threshold
from strategy.etf_strategy import Decision, StrategyResult
from core.logger import get_logger

logger = get_logger("bond_strategy")


# 债券高估预警阈值
BOND_OVERVALUED_PERCENTILE = 90  # 250日分位 > 90% 时提示风险

# 极端行情熔断阈值（债券专用，比 ETF 更敏感）
BOND_CIRCUIT_BREAKER_DROP = -2.0   # 单日跌幅超过 2% 暂停决策


@dataclass
class BondSignal:
    """债券信号"""
    has_opportunity: bool     # 是否有买入机会
    signal_type: str          # 信号类型
    strength: float           # 信号强度 (0-1)
    is_overvalued: bool = False  # 是否处于高估区
    dynamic_thresholds: Optional[dict] = None  # 使用的动态阈值


def detect_bond_signal(metrics: QuantMetrics) -> BondSignal:
    """
    检测债券买入信号（增强版）
    
    信号条件（动态阈值）：
    1. 显著跌破 60 日均线（阈值根据波动率动态调整）
    2. 单日跌幅超过阈值（阈值根据波动率动态调整）
    
    预警条件：
    - 250日分位 > 90%：高估预警
    
    Args:
        metrics: 量化指标
    
    Returns:
        BondSignal 信号
    """
    signals = []
    
    # 动态阈值计算
    ma_threshold = get_dynamic_ma_threshold(metrics.volatility_60)
    drop_normal, drop_severe = get_dynamic_drop_threshold(metrics.volatility_60)
    
    dynamic_thresholds = {
        "ma_threshold": ma_threshold,
        "drop_normal": drop_normal,
        "drop_severe": drop_severe,
        "volatility_60": metrics.volatility_60
    }
    
    # 检查是否高估
    is_overvalued = metrics.percentile_250 >= BOND_OVERVALUED_PERCENTILE
    
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


def evaluate_bond_strategy(metrics: QuantMetrics) -> StrategyResult:
    """
    评估债券基金策略（增强版）
    
    核心变化：
    1. 动态阈值：根据品种波动率自动调整
    2. 多周期分位验证
    3. 极端行情熔断
    
    防守型策略逻辑：
    - 极端行情（单日跌 > 2%）：熔断，次日决策
    - 高估区（250日分位 > 90%）：观望，提示风险
    - 正常波动：持有观望
    - 显著跌破均线或单日大跌：定投/补仓机会
    
    Args:
        metrics: 量化指标
    
    Returns:
        StrategyResult 决策结果
    """
    warnings = []
    
    # === 熔断检查 ===
    if metrics.daily_change is not None and metrics.daily_change < BOND_CIRCUIT_BREAKER_DROP:
        return StrategyResult(
            decision=Decision.HOLD,
            confidence=0.3,
            reasoning=f"触发熔断：债券单日大跌 {metrics.daily_change:.2f}%，极为罕见，建议冷静观察后决策",
            zone="熔断",
            warnings=["⚠️ 债券极端行情：跌幅罕见，可能有重大风险事件"]
        )
    
    signal = detect_bond_signal(metrics)
    consensus = metrics.percentile_consensus
    
    # 动态阈值信息
    if signal.dynamic_thresholds:
        thresholds = signal.dynamic_thresholds
        warnings.append(
            f"📊 动态阈值：均线偏离 {thresholds['ma_threshold']:.2f}%，"
            f"大跌 {thresholds['drop_normal']:.2f}%/{thresholds['drop_severe']:.2f}%"
            f"（基于 {thresholds['volatility_60']:.1f}% 年化波动率）"
        )
    
    # 多周期分位警告
    if consensus == "分歧":
        warnings.append(
            f"⚠️ 多周期分位分歧：60日={metrics.percentile_60:.0f}%，"
            f"250日={metrics.percentile_250:.0f}%，500日={metrics.percentile_500:.0f}%"
        )
    
    # 趋势警告
    trend = metrics.trend_direction
    if trend == "上升趋势":
        warnings.append("📈 债券短期走强，利率可能处于下行周期")
    if trend == "下降趋势":
        warnings.append("📉 债券短期走弱，需关注利率上行风险")
    
    # === 高估区处理 ===
    if signal.is_overvalued:
        if signal.has_opportunity and signal.strength > 0.8:
            # 高估区但有强烈信号，可以小额定投
            decision = Decision.NORMAL_BUY
            confidence = 0.5
            reasoning = f"虽有{signal.signal_type}信号（强度 {signal.strength:.0%}），但250日分位 {metrics.percentile_250:.0f}% 偏高，建议小额定投"
            warnings.append("⚠️ 高估区补仓需控制仓位，建议减半")
        else:
            decision = Decision.HOLD
            confidence = 0.7
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
            warnings=warnings
        )
    
    # === 正常估值区域 ===
    if signal.has_opportunity:
        # 有买入机会
        if signal.strength > 0.7:
            decision = Decision.DOUBLE_BUY
            confidence = 0.8
            reasoning = f"债券出现{signal.signal_type}信号（强度 {signal.strength:.0%}），难得的加仓机会"
            
            # 多周期共识增强
            if consensus in ["强低估", "弱低估"]:
                confidence = min(0.95, confidence + 0.1)
                reasoning += f"，多周期共识「{consensus}」"
        else:
            decision = Decision.NORMAL_BUY
            confidence = 0.7
            reasoning = f"债券{signal.signal_type}，可适度加仓"
        
        zone = "机会区"
    else:
        # 正常波动，持有观望
        decision = Decision.HOLD
        confidence = 0.6
        
        if metrics.daily_change is not None:
            if metrics.daily_change > 0:
                reasoning = f"债券今日上涨 {metrics.daily_change:+.2f}%，保持持有即可"
            else:
                reasoning = f"债券今日微跌 {metrics.daily_change:+.2f}%，属正常波动无需担忧"
        else:
            reasoning = "债券平稳运行，保持持有即可"
        
        zone = "正常区"
    
    logger.info(f"债券策略决策: {decision.value} (信号: {signal.signal_type})")
    
    return StrategyResult(
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        zone=zone,
        warnings=warnings
    )
