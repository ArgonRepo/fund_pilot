"""
FundPilot-AI 策略 B - 债券基金防守型策略
基于回撤幅度和均线乖离进行决策
"""

from dataclasses import dataclass
from typing import Optional

from strategy.indicators import QuantMetrics
from strategy.etf_strategy import Decision, StrategyResult
from core.logger import get_logger

logger = get_logger("bond_strategy")

# 债券大跌阈值（单日跌幅）
BOND_DROP_THRESHOLD = -0.15  # -0.15%


@dataclass
class BondSignal:
    """债券信号"""
    has_opportunity: bool     # 是否有买入机会
    signal_type: str          # 信号类型
    strength: float           # 信号强度 (0-1)


def detect_bond_signal(metrics: QuantMetrics) -> BondSignal:
    """
    检测债券买入信号
    
    信号条件：
    1. 跌破 60 日均线
    2. 单日跌幅 > 0.15%
    
    Args:
        metrics: 量化指标
    
    Returns:
        BondSignal 信号
    """
    signals = []
    
    # 信号 1: 跌破 60 日均线
    if metrics.ma_deviation < 0:
        strength = min(abs(metrics.ma_deviation) / 1.0, 1.0)  # 偏离 1% 满分
        signals.append(("跌破均线", strength))
    
    # 信号 2: 单日大跌
    if metrics.daily_change is not None and metrics.daily_change < BOND_DROP_THRESHOLD:
        strength = min(abs(metrics.daily_change) / 0.5, 1.0)  # 跌 0.5% 满分
        signals.append(("单日大跌", strength))
    
    if not signals:
        return BondSignal(
            has_opportunity=False,
            signal_type="正常波动",
            strength=0.0
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
        strength=total_strength
    )


def evaluate_bond_strategy(metrics: QuantMetrics) -> StrategyResult:
    """
    评估债券基金策略
    
    防守型策略逻辑：
    - 正常波动：持有，安抚心态
    - 跌破 60 日均线：提示买入机会
    - 单日跌幅 > 0.15%：提示买入机会（债券大跌）
    
    Args:
        metrics: 量化指标
    
    Returns:
        StrategyResult 决策结果
    """
    signal = detect_bond_signal(metrics)
    
    if signal.has_opportunity:
        # 有买入机会
        if signal.strength > 0.7:
            decision = Decision.DOUBLE_BUY
            confidence = 0.8
            reasoning = f"债券出现{signal.signal_type}信号，难得的加仓机会"
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
        zone=zone
    )
