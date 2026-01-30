"""
FundPilot-AI Prompt 构建模块
构建 AI 决策所需的系统提示词和上下文
"""

import json
from typing import Optional

from data.fund_valuation import FundValuation
from data.holdings import HoldingsInsight
from data.market import MarketContext
from strategy.indicators import QuantMetrics
from core.config import FundConfig

# 系统提示词
SYSTEM_PROMPT = """你是 FundPilot-AI 的纪律执行官，负责基于量化数据给出客观的定投决策建议。

## 核心原则
1. **低估多买、高估停买**：严格执行网格策略
2. **只买不卖**：针对 A 类份额高赎回费特性
3. **克服人性弱点**：用数据客观判断，不被情绪左右

## 策略规则

### ETF 联接基金（ETF_Feeder）
- 60日分位 < 20%（黄金坑）：**双倍补仓**
- 60日分位 20%-80%（合理区）：**正常定投** 或 **观望**
- 60日分位 > 80%（高估区）：**暂停定投**，严禁追高

### 债券基金（Bond）
- 正常波动：**观望**，安抚心态
- 跌破 60 日均线：提示 **正常定投** 机会
- 单日跌幅 > 0.15%：提示 **双倍补仓** 机会

## 输出要求
你必须给出：
1. 明确指令：[双倍补仓 / 正常定投 / 暂停定投 / 观望] 之一
2. 简短理由：结合"位置感（分位值）"和"持仓归因"进行解释，50 字以内
"""


def build_context(
    fund_config: FundConfig,
    valuation: Optional[FundValuation],
    metrics: Optional[QuantMetrics],
    holdings: Optional[HoldingsInsight],
    market: Optional[MarketContext]
) -> str:
    """
    构建 AI 决策上下文
    
    Args:
        fund_config: 基金配置
        valuation: 实时估值
        metrics: 量化指标
        holdings: 持仓洞察
        market: 市场环境
    
    Returns:
        JSON 格式的上下文字符串
    """
    context = {
        "fund_name": fund_config.name,
        "fund_code": fund_config.code,
        "fund_type": fund_config.type,
    }
    
    # 实时指标
    if valuation and metrics:
        context["real_time_metrics"] = {
            "estimate_change": f"{valuation.estimate_change:+.2f}%",
            "estimate_nav": valuation.estimate_nav,
            "percentile_60": round(metrics.percentile_60, 1),
            "ma_60_price": round(metrics.ma_60, 4),
            "ma_deviation": f"{metrics.ma_deviation:+.2f}%",
            "zone": _get_zone_description(metrics.percentile_60)
        }
    
    # 持仓洞察
    if holdings:
        context["holdings_insight"] = {
            "top_gainers": holdings.top_gainers[:3] if holdings.top_gainers else [],
            "top_losers": holdings.top_losers[:3] if holdings.top_losers else [],
            "summary": holdings.summary
        }
    
    # 市场环境
    if market:
        context["market_context"] = {
            "shanghai_index": f"{market.shanghai_index.change:+.2f}%" if market.shanghai_index else "N/A",
            "hs300_index": f"{market.hs300_index.change:+.2f}%" if market.hs300_index else "N/A",
            "summary": market.summary
        }
    
    return json.dumps(context, ensure_ascii=False, indent=2)


def _get_zone_description(percentile: float) -> str:
    """获取分位区间描述"""
    if percentile < 20:
        return "黄金坑（极度低估）"
    elif percentile < 40:
        return "低估区"
    elif percentile < 60:
        return "合理区"
    elif percentile < 80:
        return "偏高区"
    else:
        return "高估区（谨慎追高）"


def get_system_prompt() -> str:
    """获取系统提示词"""
    return SYSTEM_PROMPT
