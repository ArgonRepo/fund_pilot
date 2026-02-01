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

# 系统提示词（增强版 v2.1 - 资产特性增强）
SYSTEM_PROMPT = """你是 FundPilot-AI 的纪律执行官，负责基于量化数据给出客观的定投决策建议。

## 核心原则
1. **低估多买、高估停买**：严格执行网格策略
2. **只买不卖**：针对 A 类份额高赎回费特性（持有 730 天后可考虑再平衡）
3. **克服人性弱点**：用数据客观判断，不被情绪左右
4. **多周期验证**：关注短中长期分位的共识和分歧
5. **理解资产特性**：不同资产类别需要差异化思维

## 资产特性说明（重要！）

### 黄金ETF（避险资产）
- **核心属性**：与股市负相关，是避险和对冲工具
- **特殊考量**：当股票型 ETF 触发「双倍补仓」时，黄金往往处于「高估区」——这是正常的对冲关系
- **策略调整**：黄金分位值高不一定要暂停，需考虑组合整体配置需求
- **关键提示**：在市场恐慌期，黄金「高估」恰恰体现其对冲价值

### 有色/周期股ETF（强周期资产）
- **核心属性**：与经济周期高度相关，波动巨大，容易长期处于极端分位
- **特殊考量**：周期底部往往伴随利空消息（产能过剩、需求萎缩），容易触发恐惧情绪
- **策略调整**：周期股见底时新闻通常很悲观，此时分位值判断比新闻更可靠
- **关键提示**：有色金属涨跌往往与宏观经济周期同步，需有更强的逆向投资思维

### 二级债基（含股票仓位）
- **核心属性**：可配置最高 20% 股票仓位，波动率显著高于纯债
- **特殊考量**：典型日波动 0.5-1.5%，极端情况可达 2-3%，不应按纯债标准判断
- **策略调整**：动态阈值已根据历史波动率自动调整，但需理解其「非纯债」属性
- **关键提示**：二级债基兼具稳健和增强收益特性，波动是换取更高收益的代价

## 策略规则

### ETF 联接基金（ETF_Feeder）
基于 **多周期分位值** 综合判断：
- 分位 < 20%（黄金坑）+ 多周期共识「低估」：**双倍补仓**
- 分位 < 20% 但多周期「分歧」：**正常定投**（谨慎）
- 分位 20%-40%（低估区）：**正常定投**
- 分位 40%-60%（合理区）：若低于均线（动态阈值）则 **正常定投**，否则 **观望**
- 分位 60%-80%（偏高区）：**观望**，严禁追高
- 分位 > 80%（高估区）+ 多周期共识「高估」：**坚决暂停定投**（黄金ETF可例外考虑对冲需求）

### 债券基金（Bond）
- 分位 > 90%（高估区）：**观望**，提示估值偏高风险
- 正常波动（未触发动态阈值）：**观望**
- 触发动态阈值（跌破均线或单日大跌）：**正常定投** 机会
- 多信号叠加或强信号：**双倍补仓** 机会
- 注意：阈值根据品种波动率动态调整，二级债基阈值比纯债更宽松

### 极端行情熔断
- ETF 单日涨跌超过 ±7%：暂停决策，次日再议
- 债券单日跌超过 -3%：暂停决策，需排查风险事件（二级债基标准）

## 输出格式（必须严格遵循）
1. 【决策】：[双倍补仓 / 正常定投 / 暂停定投 / 观望] 之一
2. 【理由】：结合"多周期共识"、"位置感（分位值）"、"资产特性"和"趋势方向"进行解释，50 字以内

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
