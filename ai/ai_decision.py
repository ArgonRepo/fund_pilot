"""
FundPilot-AI AI主导决策模块
独立于策略逻辑的 AI 决策路径

该模块实现并行的 AI 主导决策：
- 使用专业化 Prompt 进行定性分析
- 返回独立的 AI 决策结果
- 与策略决策最终合成
"""

from dataclasses import dataclass
from typing import Optional
import json

from ai.deepseek_client import get_deepseek_client
from ai.specialized_prompts import get_specialized_prompt, get_asset_description
from strategy.indicators import QuantMetrics
from strategy.asset_config import infer_asset_class
from data.fund_valuation import FundValuation
from data.holdings import HoldingsInsight
from data.market import MarketContext
from core.config import FundConfig
from core.logger import get_logger

logger = get_logger("ai_decision")


@dataclass
class AIDecisionResult:
    """AI主导决策结果"""
    decision: str               # 决策: 双倍补仓/正常定投/暂停定投/观望
    confidence: str             # 信心度: 高/中/低
    reasoning: str              # 决策理由
    asset_class: str            # 资产类型
    raw_response: Optional[str] = None  # 原始 AI 回复


def _build_ai_context(
    fund_config: FundConfig,
    valuation: Optional[FundValuation],
    metrics: Optional[QuantMetrics],
    holdings: Optional[HoldingsInsight],
    market: Optional[MarketContext]
) -> dict:
    """
    构建 AI 决策上下文（完整数据版 v2.0）
    
    设计理念：提供尽可能丰富的客观数据，让 AI 进行独立专业分析
    DeepSeek 支持 40K+ tokens，充分利用其上下文能力
    
    Args:
        fund_config: 基金配置
        valuation: 实时估值
        metrics: 量化指标
        holdings: 持仓洞察
        market: 市场环境
    
    Returns:
        上下文字典
    """
    context = {}
    
    # ============================================
    # 1. 基金基本信息
    # ============================================
    context["fund_info"] = {
        "name": fund_config.name,
        "code": fund_config.code,
        "type": fund_config.type,
        "asset_class": fund_config.asset_class,
        "asset_description": get_asset_description(fund_config.asset_class or "")
    }
    
    # ============================================
    # 2. 实时估值与核心指标
    # ============================================
    if valuation:
        context["valuation"] = {
            "today_estimate_change": f"{valuation.estimate_change:+.2f}%",
            "estimate_nav": round(valuation.estimate_nav, 4),
            "estimate_time": valuation.estimate_time,
            "note": "估值为系统实时计算，非最终净值"
        }
    
    if metrics:
        # 多周期分位值（核心估值指标）
        context["valuation_metrics"] = {
            "multi_period_percentile": {
                "60_days": {
                    "value": round(metrics.percentile_60, 1),
                    "interpretation": _interpret_percentile(metrics.percentile_60)
                },
                "250_days": {
                    "value": round(metrics.percentile_250, 1),
                    "interpretation": _interpret_percentile(metrics.percentile_250)
                },
                "500_days": {
                    "value": round(metrics.percentile_500, 1),
                    "interpretation": _interpret_percentile(metrics.percentile_500)
                }
            },
            "percentile_consensus": metrics.percentile_consensus,
            "trend_direction": metrics.trend_direction,
            "note": "分位值表示当前净值在历史区间中的位置，0%=历史最低，100%=历史最高"
        }
        
        # 技术指标
        context["technical_indicators"] = {
            "ma_60": round(metrics.ma_60, 4),
            "ma_60_deviation": f"{metrics.ma_deviation:+.2f}%",
            "ma_deviation_interpretation": "高于均线" if metrics.ma_deviation > 0 else "低于均线",
            "volatility_60_annualized": f"{metrics.volatility_60:.1f}%",
            "volatility_level": _interpret_volatility(metrics.volatility_60),
            "price_range_250d": {
                "max": round(metrics.max_250, 4),
                "min": round(metrics.min_250, 4),
                "current_position": f"距最高{((metrics.max_250 - valuation.estimate_nav) / metrics.max_250 * 100):.1f}%" if valuation else "N/A"
            }
        }
        
        # 风险指标
        context["risk_indicators"] = {
            "daily_change": f"{metrics.daily_change:+.2f}%" if metrics.daily_change else "N/A",
            "drawdown_from_peak": f"{metrics.drawdown:.1f}%" if metrics.drawdown else "N/A",
            "drawdown_60d": f"{metrics.drawdown_60:.1f}%" if metrics.drawdown_60 else "N/A",
            "risk_assessment": _assess_risk(metrics)
        }
    
    # ============================================
    # 3. 完整持仓分析（ETF/股票型基金）
    # ============================================
    if holdings and holdings.holdings:
        holdings_list = []
        for h in holdings.holdings:
            holding_data = {
                "stock_name": h.stock_name,
                "stock_code": h.stock_code,
                "weight": f"{h.weight:.2f}%",
            }
            if h.change is not None:
                holding_data["today_change"] = f"{h.change:+.2f}%"
            holdings_list.append(holding_data)
        
        context["holdings_analysis"] = {
            "top_holdings": holdings_list,
            "holdings_count": len(holdings_list),
            "top_gainers": holdings.top_gainers if holdings.top_gainers else [],
            "top_losers": holdings.top_losers if holdings.top_losers else [],
            "summary": holdings.summary,
            "data_source": "季报持仓数据，可能滞后1-3个月"
        }
    
    # ============================================
    # 4. 市场环境（多指数）
    # ============================================
    if market:
        market_data = {
            "summary": market.summary
        }
        if market.shanghai_index:
            market_data["shanghai_index"] = {
                "current": market.shanghai_index.current,
                "change": f"{market.shanghai_index.change:+.2f}%"
            }
        if market.hs300_index:
            market_data["hs300_index"] = {
                "current": market.hs300_index.current,
                "change": f"{market.hs300_index.change:+.2f}%"
            }
        context["market_environment"] = market_data
    
    # ============================================
    # 5. 分析提示（帮助 AI 理解数据）
    # ============================================
    context["analysis_hints"] = {
        "decision_options": ["双倍补仓", "正常定投", "暂停定投", "观望"],
        "confidence_levels": ["高", "中", "低"],
        "key_factors_to_consider": [
            "多周期分位值的一致性",
            "当前价格相对于均线的位置",
            "今日涨跌幅是否异常",
            "持仓表现是否有信号意义",
            "市场整体环境"
        ]
    }
    
    return context


def _interpret_percentile(percentile: float) -> str:
    """解释分位值含义"""
    if percentile < 20:
        return "极端低估区"
    elif percentile < 40:
        return "低估区"
    elif percentile < 60:
        return "正常区"
    elif percentile < 80:
        return "偏高区"
    else:
        return "极端高估区"


def _interpret_volatility(volatility: float) -> str:
    """解释波动率水平"""
    if volatility < 5:
        return "极低波动（类固收）"
    elif volatility < 15:
        return "低波动"
    elif volatility < 25:
        return "中等波动"
    elif volatility < 35:
        return "高波动"
    else:
        return "极高波动（高风险）"


def _assess_risk(metrics: QuantMetrics) -> str:
    """评估当前风险状况"""
    risks = []
    
    if metrics.daily_change and metrics.daily_change < -3:
        risks.append("今日大跌")
    if metrics.drawdown and metrics.drawdown > 15:
        risks.append("深度回撤")
    if metrics.percentile_250 > 85:
        risks.append("估值极高")
    if metrics.percentile_250 < 15:
        risks.append("估值极低")
    
    if not risks:
        return "正常"
    return "、".join(risks)


def _parse_ai_response(response: str) -> tuple[str, str, str]:
    """
    解析 AI 回复，提取决策、信心度和理由
    
    Args:
        response: AI 原始回复
    
    Returns:
        (decision, confidence, reasoning) 元组
    """
    decision = "观望"  # 默认
    confidence = "中"
    reasoning = ""
    
    # 解析决策
    if "【决策】" in response:
        parts = response.split("【决策】")
        if len(parts) > 1:
            decision_part = parts[1].split("【")[0].strip()
            # 提取决策关键词
            for keyword in ["双倍补仓", "正常定投", "暂停定投", "观望"]:
                if keyword in decision_part:
                    decision = keyword
                    break
    
    # 解析信心度
    if "【信心度】" in response:
        parts = response.split("【信心度】")
        if len(parts) > 1:
            conf_part = parts[1].split("【")[0].strip()
            for level in ["高", "中", "低"]:
                if level in conf_part:
                    confidence = level
                    break
    
    # 解析理由
    for key in ["【核心理由】", "【理由】"]:
        if key in response:
            parts = response.split(key)
            if len(parts) > 1:
                reasoning = parts[1].split("【")[0].strip()
                # 限制长度
                if len(reasoning) > 100:
                    reasoning = reasoning[:100] + "..."
                break
    
    return decision, confidence, reasoning


def get_ai_decision(
    fund_config: FundConfig,
    valuation: Optional[FundValuation],
    metrics: Optional[QuantMetrics],
    holdings: Optional[HoldingsInsight],
    market: Optional[MarketContext],
    dynamic_thresholds: Optional[dict] = None
) -> Optional[AIDecisionResult]:
    """
    获取 AI 主导决策
    
    Args:
        fund_config: 基金配置
        valuation: 实时估值
        metrics: 量化指标
        holdings: 持仓洞察
        market: 市场环境
        dynamic_thresholds: 动态阈值（用于 Prompt）
    
    Returns:
        AIDecisionResult 或 None（失败时）
    """
    # 确定资产类型
    asset_class = fund_config.asset_class
    if not asset_class:
        asset_class = infer_asset_class(fund_config.type, fund_config.name)
    
    logger.info(f"AI决策开始: {fund_config.name} (资产类型: {asset_class})")
    
    # 获取专业化 Prompt
    system_prompt = get_specialized_prompt(asset_class, dynamic_thresholds)
    
    # 构建上下文
    context = _build_ai_context(fund_config, valuation, metrics, holdings, market)
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    
    # 构建用户消息
    user_message = f"""请基于以下数据，运用你的专业分析框架，给出独立的投资决策建议：

```json
{context_json}
```

请严格按照输出格式回复，包含【决策】、【信心度】和【核心理由】三个部分。"""
    
    # 调用 AI
    try:
        client = get_deepseek_client()
        response = client.chat(system_prompt, user_message, temperature=0.3)
        
        # 增强空值检测：检查长度和关键词
        if not response or len(response) < 10:
            logger.warning(f"AI决策返回过短: {fund_config.name} (长度: {len(response) if response else 0})")
            return None
        
        # 检查是否包含必要标记
        if "【决策】" not in response and "决策" not in response:
            logger.warning(f"AI响应缺少决策标记: {fund_config.name}")
            logger.debug(f"原始响应: {response}")
            return None
        
        # 解析响应
        decision, confidence, reasoning = _parse_ai_response(response)
        
        # 验证解析结果：如果 reasoning 为空说明解析可能失败
        if not reasoning:
            # 尝试从响应中提取任何有用信息作为理由
            reasoning = response[:80] + "..." if len(response) > 80 else response
            logger.warning(f"AI响应理由解析失败，使用原始响应: {fund_config.name}")
        
        logger.info(f"AI决策完成: {fund_config.name} -> {decision} ({confidence})")
        
        return AIDecisionResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            asset_class=asset_class,
            raw_response=response
        )
        
    except Exception as e:
        logger.error(f"AI决策失败: {fund_config.name} - {e}")
        return None


def confidence_to_score(confidence: str) -> float:
    """将信心度转换为数值"""
    return {"高": 0.9, "中": 0.6, "低": 0.3}.get(confidence, 0.5)


def score_to_confidence(score: float) -> str:
    """将数值转换为信心度"""
    if score >= 0.75:
        return "高"
    elif score >= 0.45:
        return "中"
    else:
        return "低"
