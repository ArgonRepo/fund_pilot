"""
FundPilot-AI 单只基金决策流水线
封装从数据采集到报告生成的完整处理流程
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.config import FundConfig
from core.logger import get_logger
from core.database import get_database
from core.http_client import request_stats
from data.fund_valuation import fetch_fund_valuation
from data.fund_history import get_fund_history, get_recent_nav
from data.holdings import get_holdings_with_quotes
from data.market import get_market_context
from data.us_market import fetch_nq_futures
from strategy.indicators import calculate_all_metrics, get_dynamic_ma_threshold, get_dynamic_drop_threshold
from strategy.etf_strategy import evaluate_etf_strategy, get_buy_multiplier
from strategy.bond_strategy import evaluate_bond_strategy
from strategy.asset_config import infer_asset_class, get_thresholds
from strategy.decision_synthesizer import synthesize_decisions
from ai.ai_decision import get_ai_decision
from ai.alert_context import build_context
from visualization.chart import generate_trend_chart
from notification.email_template import FundReport

logger = get_logger("pipeline")


@dataclass
class FundResult:
    """单只基金处理结果"""
    fund: FundConfig
    success: bool
    report: Optional[FundReport] = None
    chart_image: Optional[bytes] = None
    error: Optional[str] = None


def process_single_fund(fund: FundConfig, time_str: str) -> FundResult:
    """
    处理单只基金的决策流程（双轨决策版 v3.0）
    
    流程:
    1. 数据采集
    2. 策略主导决策（资产感知）
    3. AI主导决策（专业Prompt）
    4. 决策合成
    5. 报告生成
    
    Args:
        fund: 基金配置
        time_str: 时间字符串（如 "14:45"）
    
    Returns:
        FundResult 处理结果
    """
    logger.info(f"开始处理基金: {fund.name} ({fund.code})")
    
    try:
        # 1. 获取实时估值
        valuation = fetch_fund_valuation(fund.code)
        if not valuation:
            logger.warning(f"基金 {fund.code} 获取估值失败")
            return FundResult(fund=fund, success=False, error="获取估值失败")
        
        # 2. 获取历史净值（1250天，约5年，用于计算长期分位）
        history = get_fund_history(fund.code, days=1250)
        if not history:
            logger.warning(f"基金 {fund.code} 获取历史净值失败")
            return FundResult(fund=fund, success=False, error="获取历史净值失败")
        
        # 3. 计算量化指标（多周期分位值 + 波动率）
        prices_history = [nav for _, nav in history]
        metrics = calculate_all_metrics(
            current_price=valuation.estimate_nav,
            prices_history=prices_history,
            daily_change=valuation.estimate_change
        )
        
        # 4. 获取持仓信息
        holdings = get_holdings_with_quotes(fund)
        
        # 5. 获取市场环境
        market = get_market_context()
        
        # === 双轨决策架构 ===
        
        # 6a. 策略主导决策（资产感知）
        asset_class = fund.asset_class or infer_asset_class(fund.type, fund.name)
        
        # 获取大盘跌幅用于黄金对冲判断
        market_drop = None
        if market and market.shanghai_index:
            market_drop = market.shanghai_index.change
        
        if fund.type in ("ETF_Feeder", "QDII"):
            strategy_result = evaluate_etf_strategy(metrics, asset_class, fund.name, market_drop)
        else:
            strategy_result = evaluate_bond_strategy(metrics, asset_class, fund.name)
        
        logger.info(f"策略决策: {strategy_result.decision.value} (confidence: {strategy_result.confidence:.0%})")
        
        # 6b. QDII 基金: 获取 NQ=F 期货数据
        nq_futures = None
        if fund.type == "QDII":
            nq_futures = fetch_nq_futures()
            if nq_futures:
                logger.info(f"NQ=F 期货参考: {nq_futures.change_pct:+.2f}% [来源: {nq_futures.data_source}]")
            else:
                logger.warning("NQ=F 期货数据获取失败，仅使用基金历史数据决策")
        
        # 6c. AI主导决策（专业化Prompt）
        # 构建动态阈值用于债券Prompt
        dynamic_thresholds = None
        thresholds = get_thresholds(asset_class)
        if fund.type == "Bond":
            drop_normal, drop_severe = get_dynamic_drop_threshold(metrics.volatility_60)
            dynamic_thresholds = {
                "ma_threshold": min(get_dynamic_ma_threshold(metrics.volatility_60), thresholds.ma_base_threshold),
                "drop_normal": drop_normal,
                "drop_severe": drop_severe
            }
        
        # A-1: 构建策略参考（供 AI 交叉验证，但不强制约束 AI）
        strategy_reference = {
            "decision": strategy_result.decision.value,
            "confidence": f"{strategy_result.confidence:.0%}",
            "reasoning": strategy_result.reasoning,
            "note": "此为量化策略的独立判断，仅供参考。你应独立分析，可以认同也可以反驳。"
        }
        
        # A-2: 构建资产阈值参考（让 AI 理解系统对该资产的波动预期）
        asset_thresholds_info = {
            "zone_thresholds": {
                "golden_pit": f"<{thresholds.zone_thresholds[0]:.0f}%",
                "undervalued": f"<{thresholds.zone_thresholds[1]:.0f}%",
                "overvalued": f">{thresholds.zone_thresholds[2]:.0f}%",
                "overheated": f">{thresholds.zone_thresholds[3]:.0f}%"
            },
            "circuit_breaker": {
                "drop": f"{thresholds.circuit_breaker_drop:.1f}%",
                "rise": f"{thresholds.circuit_breaker_rise:.1f}%"
            },
            "description": thresholds.description,
            "note": "这些是系统为该资产类型设定的参考阈值，供你理解该类资产的正常波动范围"
        }
        
        ai_result = get_ai_decision(
            fund_config=fund,
            valuation=valuation,
            metrics=metrics,
            holdings=holdings,
            market=market,
            dynamic_thresholds=dynamic_thresholds,
            nq_futures=nq_futures,
            strategy_reference=strategy_reference,
            asset_thresholds=asset_thresholds_info
        )
        
        if ai_result:
            logger.info(f"AI决策: {ai_result.decision} (信心度: {ai_result.confidence})")
        else:
            logger.warning("AI决策失败，将仅使用策略决策")
        
        # 6d. 决策合成
        synthesized = synthesize_decisions(strategy_result, ai_result, asset_class)
        
        logger.info(f"最终决策: {synthesized.final_decision} ({synthesized.synthesis_method})")
        
        # 7. 生成图表
        recent_10 = get_recent_nav(history, 10)
        recent_10_asc = list(reversed(recent_10))
        
        chart_image = generate_trend_chart(
            fund_name=fund.name,
            history_10d=recent_10_asc,
            estimate_today=valuation.estimate_nav,
            ma_60=metrics.ma_60,
            estimate_change=valuation.estimate_change
        )
        
        # 8. 计算补仓倍数
        raw_multiplier = get_buy_multiplier(
            percentile=metrics.percentile_250,
            consensus=metrics.percentile_consensus,
            asset_class=asset_class
        )
        
        # 决策一致性修正
        final_multiplier = raw_multiplier
        if synthesized.final_decision == "正常定投" and final_multiplier < 1.0:
            final_multiplier = 1.0
        elif synthesized.final_decision == "双倍补仓" and final_multiplier < 2.0:
            final_multiplier = 2.0
        elif synthesized.final_decision in ["暂停定投", "观望"]:
            final_multiplier = 0.0

        # 9. 构建报告数据
        report = FundReport(
            fund_name=fund.name,
            fund_code=fund.code,
            fund_type=fund.type,
            decision=synthesized.final_decision,
            reasoning=synthesized.final_reasoning,
            estimate_change=valuation.estimate_change,
            percentile_250=metrics.percentile_250,
            ma_deviation=metrics.ma_deviation,
            zone=strategy_result.zone,
            holdings_summary=holdings.summary if holdings else None,
            top_gainers=holdings.top_gainers if holdings else None,
            top_losers=holdings.top_losers if holdings else None,
            chart_cid=f"chart_{fund.code}",
            warnings=synthesized.warnings,
            percentile_60=metrics.percentile_60,
            percentile_1250=metrics.percentile_1250,
            volatility_60=metrics.volatility_60,
            percentile_consensus=metrics.percentile_consensus,
            trend_direction=metrics.trend_direction,
            strategy_decision=synthesized.strategy_decision,
            strategy_confidence=synthesized.strategy_confidence,
            strategy_reasoning=synthesized.strategy_reasoning,
            ai_decision=synthesized.ai_decision,
            ai_confidence=synthesized.ai_confidence,
            ai_reasoning=synthesized.ai_reasoning,
            final_confidence=synthesized.final_confidence,
            synthesis_method=synthesized.synthesis_method,
            asset_class=asset_class,
            buy_multiplier=final_multiplier,
            nq_change_pct=nq_futures.change_pct if nq_futures else None,
            nq_data_source=nq_futures.data_source if nq_futures else None
        )
        
        # 10. 记录决策日志
        db = get_database()
        context_json = build_context(fund, valuation, metrics, holdings, market, nq_futures=nq_futures)
        db.save_decision_log(
            fund_code=fund.code,
            fund_name=fund.name,
            fund_type=fund.type,
            asset_class=asset_class,
            decision_time=datetime.now(),
            estimate_change=valuation.estimate_change,
            percentile_250=metrics.percentile_250,
            percentile_1250=metrics.percentile_1250,
            ma_60=metrics.ma_60,
            ai_decision=synthesized.final_decision,
            decision_nav=valuation.estimate_nav,
            ai_reasoning=synthesized.final_reasoning,
            raw_context=context_json
        )
        
        logger.info(f"基金 {fund.name} 处理完成: {synthesized.final_decision}")
        return FundResult(fund=fund, success=True, report=report, chart_image=chart_image)
        
    except Exception as e:
        logger.error(f"处理基金 {fund.name} 失败: {e}")
        return FundResult(fund=fund, success=False, error=str(e))
