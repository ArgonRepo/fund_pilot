"""
FundPilot-AI Prompt 构建模块
构建 AI 决策所需的系统提示词和上下文

重要更新 v2.0：
- 多周期分位值（60/250/500日）交叉验证
- 波动率信息用于动态阈值
- 增加市场体制和趋势判断
- 债券利率环境提示
"""

import json
from typing import Optional

from data.fund_valuation import FundValuation
from data.holdings import HoldingsInsight
from data.market import MarketContext
from strategy.indicators import QuantMetrics
from core.config import FundConfig

# 系统提示词（增强版 v2.0）
SYSTEM_PROMPT = """你是 FundPilot-AI 的纪律执行官，负责基于量化数据给出客观的定投决策建议。

## 核心原则
1. **低估多买、高估停买**：严格执行网格策略
2. **只买不卖**：针对 A 类份额高赎回费特性（持有 730 天后可考虑再平衡）
3. **克服人性弱点**：用数据客观判断，不被情绪左右
4. **多周期验证**：关注短中长期分位的共识和分歧

## 策略规则

### ETF 联接基金（ETF_Feeder）
基于 **多周期分位值** 综合判断：
- 分位 < 20%（黄金坑）+ 多周期共识「低估」：**双倍补仓**
- 分位 < 20% 但多周期「分歧」：**正常定投**（谨慎）
- 分位 20%-40%（低估区）：**正常定投**
- 分位 40%-60%（合理区）：若低于均线（动态阈值）则 **正常定投**，否则 **观望**
- 分位 60%-80%（偏高区）：**观望**，严禁追高
- 分位 > 80%（高估区）+ 多周期共识「高估」：**坚决暂停定投**

### 债券基金（Bond）
- 分位 > 90%（高估区）：**观望**，提示估值偏高风险
- 正常波动（未触发动态阈值）：**观望**
- 触发动态阈值（跌破均线或单日大跌）：**正常定投** 机会
- 多信号叠加或强信号：**双倍补仓** 机会
- 注意：阈值根据品种波动率动态调整，低波动债券阈值更小

### 极端行情熔断
- ETF 单日涨跌超过 ±7%：暂停决策，次日再议
- 债券单日跌超过 -2%：暂停决策，需排查风险事件

## 输出格式（必须严格遵循）
1. 【决策】：[双倍补仓 / 正常定投 / 暂停定投 / 观望] 之一
2. 【理由】：结合"多周期共识"、"位置感（分位值）"和"持仓归因"进行解释，50 字以内

注意：输出必须包含【决策】和【理由】两个明确标签，便于系统解析。
"""


def build_context(
    fund_config: FundConfig,
    valuation: Optional[FundValuation],
    metrics: Optional[QuantMetrics],
    holdings: Optional[HoldingsInsight],
    market: Optional[MarketContext]
) -> str:
    """
    构建 AI 决策上下文（增强版）
    
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
    
    # 实时指标（增强版）
    if valuation and metrics:
        context["real_time_metrics"] = {
            "estimate_change": f"{valuation.estimate_change:+.2f}%",
            "estimate_nav": valuation.estimate_nav,
            # 多周期分位值
            "percentile_60": round(metrics.percentile_60, 1),
            "percentile_250": round(metrics.percentile_250, 1),
            "percentile_500": round(metrics.percentile_500, 1),
            "percentile_consensus": metrics.percentile_consensus,
            "trend_direction": metrics.trend_direction,
            # 均线相关
            "ma_60_price": round(metrics.ma_60, 4),
            "ma_deviation": f"{metrics.ma_deviation:+.2f}%",
            # 波动率
            "volatility_60": f"{metrics.volatility_60:.1f}%",
            # 区间
            "zone": _get_zone_description(metrics.percentile_250),
            "max_250": round(metrics.max_250, 4),
            "min_250": round(metrics.min_250, 4),
        }
    
    # 持仓洞察
    if holdings:
        context["holdings_insight"] = {
            "top_gainers": holdings.top_gainers[:3] if holdings.top_gainers else [],
            "top_losers": holdings.top_losers[:3] if holdings.top_losers else [],
            "summary": holdings.summary,
            "data_staleness_warning": "持仓数据来自季报，可能滞后 1-3 个月"
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
