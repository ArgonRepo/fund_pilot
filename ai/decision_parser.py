"""
FundPilot-AI AI 决策输出解析模块
从 AI 回复中提取结构化的决策信息
"""

import re
from dataclasses import dataclass
from typing import Optional

from core.logger import get_logger

logger = get_logger("decision_parser")

# 有效决策类型
VALID_DECISIONS = ["双倍补仓", "正常定投", "暂停定投", "观望"]


@dataclass
class ParsedDecision:
    """解析后的决策"""
    decision: str       # 决策指令
    reasoning: str      # 决策理由
    raw_response: str   # 原始回复
    is_valid: bool      # 是否成功解析


def parse_ai_decision(response: Optional[str]) -> ParsedDecision:
    """
    解析 AI 决策输出
    
    期望格式:
    1. 【决策】：[双倍补仓/正常定投/暂停定投/观望]
    2. 【理由】：...
    
    Args:
        response: AI 回复内容
    
    Returns:
        ParsedDecision 解析结果
    """
    if not response:
        return ParsedDecision(
            decision="观望",
            reasoning="AI 服务暂时不可用，建议观望",
            raw_response="",
            is_valid=False
        )
    
    decision = None
    reasoning = None
    
    # 尝试匹配决策
    for valid_decision in VALID_DECISIONS:
        if valid_decision in response:
            decision = valid_decision
            break
    
    # 尝试提取理由
    # 匹配 【理由】：... 或 理由：... 或 2. ...
    reason_patterns = [
        r'【理由】[：:]\s*(.+?)(?:\n|$)',
        r'理由[：:]\s*(.+?)(?:\n|$)',
        r'2[.、]\s*(.+?)(?:\n|$)',
    ]
    
    for pattern in reason_patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            # 清理多余内容
            reasoning = re.sub(r'\s+', ' ', reasoning)
            reasoning = reasoning[:100]  # 限制长度
            break
    
    # 如果没找到格式化的理由，尝试提取有意义的内容
    if not reasoning:
        # 移除决策关键词后的第一句话
        clean_response = response
        for d in VALID_DECISIONS:
            clean_response = clean_response.replace(d, "")
        
        # 取第一个句号前的内容
        sentences = re.split(r'[。！？\n]', clean_response)
        for s in sentences:
            s = s.strip()
            if len(s) > 10:
                reasoning = s[:100]
                break
    
    # 默认理由
    if not reasoning:
        reasoning = "请参考量化指标进行决策"
    
    # 默认决策
    if not decision:
        decision = "观望"
        logger.warning(f"无法解析决策，使用默认值: {decision}")
    
    logger.info(f"解析决策: {decision} | 理由: {reasoning[:50]}...")
    
    return ParsedDecision(
        decision=decision,
        reasoning=reasoning,
        raw_response=response,
        is_valid=decision in VALID_DECISIONS
    )


def get_decision_emoji(decision: str) -> str:
    """获取决策对应的 emoji"""
    emoji_map = {
        "双倍补仓": "🔥",
        "正常定投": "✅",
        "暂停定投": "⏸️",
        "观望": "👀"
    }
    return emoji_map.get(decision, "📊")


def get_decision_color(decision: str) -> str:
    """获取决策对应的颜色（用于邮件）- 与 email_template 保持一致"""
    color_map = {
        "双倍补仓": "#D32F2F",   # 深红
        "正常定投": "#388E3C",   # 深绿
        "暂停定投": "#F57C00",   # 橙色
        "观望": "#757575"        # 灰色
    }
    return color_map.get(decision, "#757575")
