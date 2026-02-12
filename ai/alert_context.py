"""
FundPilot-AI Prompt 构建模块
构建盘中预警邮件所需的上下文数据

用途说明：
- 本模块 build_context() 专用于盘中预警邮件（alert）场景
- AI 决策流程使用 ai_decision._build_ai_context()，两者独立
- 两者字段和格式不同，请勿混用

重要更新 v2.0：
- 多周期分位值（60/250/500日）交叉验证
- 波动率信息用于动态阈值
- 增加市场体制和趋势判断
- 债券利率环境提示

重要更新 v2.1:
- QDII 基金支持：注入 NQ=F 纳指期货数据作为盘中参考
- 数据来源追踪：明确标注 nq_futures / fund_nav
"""

import json
from typing import Optional

from data.fund_valuation import FundValuation
from data.holdings import HoldingsInsight
from data.market import MarketContext
from data.us_market import NQFuturesData
from strategy.indicators import QuantMetrics, get_percentile_zone
from core.config import FundConfig




def build_context(
    fund_config: FundConfig,
    valuation: Optional[FundValuation],
    metrics: Optional[QuantMetrics],
    holdings: Optional[HoldingsInsight],
    market: Optional[MarketContext],
    nq_futures: Optional[NQFuturesData] = None
) -> str:
    """
    构建 AI 决策上下文（增强版）
    
    Args:
        fund_config: 基金配置
        valuation: 实时估值
        metrics: 量化指标
        holdings: 持仓洞察
        market: 市场环境
        nq_futures: NQ=F 期货数据（QDII 基金专用）
    
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
            "percentile_1250_5y": round(metrics.percentile_1250, 1),
            "percentile_consensus": metrics.percentile_consensus,
            "trend_direction": metrics.trend_direction,
            # 均线相关
            "ma_60_price": round(metrics.ma_60, 4),
            "ma_deviation": f"{metrics.ma_deviation:+.2f}%",
            # 波动率
            "volatility_60": f"{metrics.volatility_60:.1f}%",
            # 区间
            "zone": get_percentile_zone(metrics.percentile_250),
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
    
    # NQ=F 纳指期货数据 (QDII 基金专用)
    if nq_futures:
        context["nq_futures_reference"] = {
            "data_source": nq_futures.data_source,
            "price": nq_futures.price,
            "change_pct": f"{nq_futures.change_pct:+.2f}%",
            "market_status": nq_futures.market_status,
            "is_fallback": nq_futures.is_fallback,
            "note": "期货数据仅供参考，与实际指数存在基差"
        }
    
    return json.dumps(context, ensure_ascii=False, indent=2)

