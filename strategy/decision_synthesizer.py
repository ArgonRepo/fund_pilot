"""
FundPilot-AI 决策合成器
合并策略主导决策和 AI 主导决策，生成最终建议

合成规则:
1. 两者一致 → 直接采用，信心度提升
2. 两者分歧 → 根据资产类型决定权重
3. 极端分歧 → 保守处理，倾向观望
"""

from dataclasses import dataclass
from typing import Optional

from strategy.etf_strategy import StrategyResult, Decision
from ai.ai_decision import AIDecisionResult, confidence_to_score, score_to_confidence
from strategy.asset_config import get_thresholds
from core.logger import get_logger

logger = get_logger("decision_synthesizer")


# 决策优先级（用于分歧时的保守处理）
DECISION_PRIORITY = {
    "双倍补仓": 4,
    "正常定投": 3,
    "观望": 2,
    "暂停定投": 1,
}

# 决策反向映射
PRIORITY_TO_DECISION = {v: k for k, v in DECISION_PRIORITY.items()}


@dataclass
class SynthesizedDecision:
    """合成决策结果"""
    # 策略决策
    strategy_decision: str
    strategy_confidence: float
    strategy_reasoning: str
    
    # AI 决策
    ai_decision: str
    ai_confidence: str
    ai_reasoning: str
    
    # 最终决策
    final_decision: str
    final_confidence: str
    final_reasoning: str
    
    # 元信息
    is_consistent: bool           # 两者是否一致
    synthesis_method: str         # 合成方式
    asset_class: str              # 资产类型
    
    # 风险提示
    warnings: list[str]


def _decision_to_priority(decision: str) -> int:
    """将决策转换为优先级数值"""
    return DECISION_PRIORITY.get(decision, 2)


def _priority_to_decision(priority: int) -> str:
    """将优先级转换为决策"""
    return PRIORITY_TO_DECISION.get(priority, "观望")


def _get_conservative_decision(d1: str, d2: str) -> str:
    """
    获取保守决策（取两者中间值，偏向观望）
    
    规则：
    - 双倍补仓 vs 观望 → 正常定投
    - 暂停定投 vs 正常定投 → 观望
    - 极端分歧 → 观望
    """
    p1, p2 = _decision_to_priority(d1), _decision_to_priority(d2)
    
    diff = abs(p1 - p2)
    if diff >= 2:
        # 分歧较大，选中间值（向观望方向取整）
        avg = (p1 + p2 + 1) // 2  # +1 使其偏向 观望(2) 而非 暂停(1)
        return _priority_to_decision(avg)
    else:
        # 分歧较小，偏向观望（priority=2）
        # 在 暂停(1) 和 正常定投(3) 之间选观望
        return _priority_to_decision(max(min(p1, p2), 2))


def synthesize_decisions(
    strategy_result: StrategyResult,
    ai_result: Optional[AIDecisionResult],
    asset_class: str
) -> SynthesizedDecision:
    """
    合成策略决策和 AI 决策
    
    Args:
        strategy_result: 策略决策结果
        ai_result: AI 决策结果（可能为 None）
        asset_class: 资产类型
    
    Returns:
        SynthesizedDecision 合成决策
    """
    warnings = list(strategy_result.warnings)  # 复制策略警告
    
    strategy_decision = strategy_result.decision.value
    strategy_confidence = strategy_result.confidence
    
    # AI 决策失败时，降级为仅策略决策
    if ai_result is None:
        logger.warning(f"AI决策失败，降级为仅策略决策: {strategy_decision}")
        warnings.append("AI决策不可用，仅参考策略决策")
        
        return SynthesizedDecision(
            strategy_decision=strategy_decision,
            strategy_confidence=strategy_confidence,
            strategy_reasoning=strategy_result.reasoning,
            ai_decision="不可用",
            ai_confidence="低",
            ai_reasoning="AI服务暂时不可用",
            final_decision=strategy_decision,
            final_confidence=score_to_confidence(strategy_confidence * 0.8),
            final_reasoning=strategy_result.reasoning,
            is_consistent=True,
            synthesis_method="降级模式：仅策略决策",
            asset_class=asset_class,
            warnings=warnings
        )
    
    ai_decision = ai_result.decision
    ai_confidence_str = ai_result.confidence
    ai_confidence = confidence_to_score(ai_confidence_str)
    
    # 获取资产类型对应的 AI 权重
    thresholds = get_thresholds(asset_class)
    ai_weight = thresholds.ai_weight
    strategy_weight = 1 - ai_weight
    
    # 判断是否一致
    is_consistent = (strategy_decision == ai_decision)
    
    if is_consistent:
        # 两者一致：信心度加成
        combined_confidence = min(1.0, strategy_confidence * 0.5 + ai_confidence * 0.5 + 0.1)
        final_decision = strategy_decision
        synthesis_method = "一致性加成"
        final_reasoning = f"策略与AI一致建议「{final_decision}」"
        
        logger.info(f"决策一致: {final_decision} (加成后信心: {combined_confidence:.0%})")
    else:
        # 两者分歧：根据权重和保守原则处理
        diff = abs(_decision_to_priority(strategy_decision) - _decision_to_priority(ai_decision))
        
        if diff >= 2:
            # 极端分歧：保守处理
            final_decision = _get_conservative_decision(strategy_decision, ai_decision)
            combined_confidence = 0.5  # 降低信心
            synthesis_method = "分歧保守处理"
            final_reasoning = f"策略建议「{strategy_decision}」与AI建议「{ai_decision}」分歧较大，保守建议「{final_decision}」"
            warnings.append(f"策略({strategy_decision})与AI({ai_decision})存在分歧")
            
            logger.info(f"极端分歧: 策略={strategy_decision}, AI={ai_decision}, 最终保守={final_decision}")
        else:
            # 轻度分歧：根据权重选择
            if ai_confidence > strategy_confidence and ai_weight >= 0.5:
                final_decision = ai_decision
                combined_confidence = ai_confidence * ai_weight + strategy_confidence * strategy_weight
                synthesis_method = f"AI主导 (权重{ai_weight:.0%})"
            else:
                final_decision = strategy_decision
                combined_confidence = strategy_confidence * strategy_weight + ai_confidence * ai_weight
                synthesis_method = f"策略主导 (权重{strategy_weight:.0%})"
            
            final_reasoning = f"综合策略「{strategy_decision}」和AI「{ai_decision}」，建议「{final_decision}」"
            
            logger.info(f"轻度分歧: 策略={strategy_decision}, AI={ai_decision}, 最终={final_decision} ({synthesis_method})")
    
    return SynthesizedDecision(
        strategy_decision=strategy_decision,
        strategy_confidence=strategy_confidence,
        strategy_reasoning=strategy_result.reasoning,
        ai_decision=ai_decision,
        ai_confidence=ai_confidence_str,
        ai_reasoning=ai_result.reasoning,
        final_decision=final_decision,
        final_confidence=score_to_confidence(combined_confidence),
        final_reasoning=final_reasoning,
        is_consistent=is_consistent,
        synthesis_method=synthesis_method,
        asset_class=asset_class,
        warnings=warnings
    )
