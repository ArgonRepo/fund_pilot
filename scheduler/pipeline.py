"""
FundPilot 单只基金决策流水线
封装从数据采集到报告生成的完整处理流程

v4.1 审计优化:
- NQ 期货数据参与 QDII 决策（C2）
- 策略决策与定投倍数一体化，消除"两张皮"（C3）
- 估值数据过期检测（M4）
- 补仓节奏控制，避免短期集中投入（I1）
- QDII 数据时效性标注（I5）
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
from data.us_market import fetch_us_futures_for_fund
from strategy.indicators import calculate_all_metrics
from strategy.etf_strategy import evaluate_etf_strategy
from strategy.bond_strategy import evaluate_bond_strategy
from strategy.asset_config import infer_asset_class
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
    处理单只基金的决策流程（v4.1 审计优化版）
    
    流程:
    1. 数据采集（估值 + 历史 + 持仓 + 市场 + NQ期货）
    2. 数据质量检查（估值时效性）
    3. 策略决策（资产感知 + NQ修正 + 倍数一体化输出）
    4. 补仓节奏控制
    5. 报告生成
    
    Args:
        fund: 基金配置
        time_str: 时间字符串（如 "14:45"）
    
    Returns:
        FundResult 处理结果
    """
    logger.info(f"开始处理基金: {fund.name} ({fund.code})")
    
    try:
        # 1. 获取历史净值（1250天，约5年，用于计算长期分位）
        history = get_fund_history(fund.code, days=1250)
        if not history:
            logger.warning(f"基金 {fund.code} 获取历史净值失败")
            return FundResult(fund=fund, success=False, error="获取历史净值失败")
        
        # 2. 获取实时估值（QDII 不走估值API，实时参考来自期货）
        valuation = None
        if fund.has_realtime_valuation:
            valuation = fetch_fund_valuation(fund.code, fund.underlying_etf)
            if not valuation:
                logger.warning(f"基金 {fund.code} 获取估值失败")
                return FundResult(fund=fund, success=False, error="获取估值失败")
        
        # 3. 确定当前价格和日涨跌幅
        realtime_change = None
        if valuation:
            current_price = valuation.estimate_nav
            daily_change = valuation.estimate_change
            realtime_change = valuation.estimate_change
        else:
            current_price = history[0][1]  # history 降序，[0] 是最新
            prev_price = history[1][1] if len(history) >= 2 else current_price
            daily_change = (current_price - prev_price) / prev_price * 100 if prev_price else 0.0
            logger.info(f"基金 {fund.code} 使用前日净值: {current_price:.4f} ({daily_change:+.2f}%)")
            
        # 计算昨日估值涨跌幅 (基于最新收盘净值)
        previous_change = None
        if len(history) >= 2:
            prev_day_nav = history[0][1]
            day_before_nav = history[1][1]
            previous_change = (prev_day_nav - day_before_nav) / day_before_nav * 100 if day_before_nav else 0.0
            
        # 获取过去5个交易日的涨跌幅
        recent_5_changes = []
        for i in range(min(5, len(history) - 1)):
            date_obj = history[i][0]
            current_nav = history[i][1]
            prev_nav = history[i+1][1]
            change = (current_nav - prev_nav) / prev_nav * 100 if prev_nav else 0.0
            # 使用 hasattr 以防 date_obj 是 datetime 对象
            date_str = date_obj.strftime("%m-%d") if hasattr(date_obj, 'strftime') else str(date_obj)[5:10]
            recent_5_changes.append((date_str, change))
        recent_5_changes.reverse() # 时间正序：最老在前，最新在后
        
        # 4. 计算量化指标（多周期分位值 + 波动率）
        prices_history = [nav for _, nav in history]
        metrics = calculate_all_metrics(
            current_price=current_price,
            prices_history=prices_history,
            daily_change=daily_change
        )
        
        # 4. 获取持仓信息
        asset_class = fund.asset_class or infer_asset_class(fund.type, fund.name)
        holdings = None
        
        if asset_class not in ("GOLD_ETF", "US_EQUITY_INDEX") and fund.type != "QDII":
            holdings = get_holdings_with_quotes(fund)
        
        # 5. 获取市场环境
        market = get_market_context()
        
        # 6. QDII: 获取对应期货数据（C2: 在决策之前获取，参与决策）
        us_futures = None
        nq_change_pct = None
        if fund.type == "QDII":
            us_futures = fetch_us_futures_for_fund(fund.name)
            if us_futures:
                nq_change_pct = us_futures.change_pct
                logger.info(f"{us_futures.futures_symbol} 期货参考: {us_futures.change_pct:+.2f}% [来源: {us_futures.data_source}]")
            else:
                logger.warning("美股期货数据获取失败，仅使用基金历史数据决策")
        
        # 7. 策略决策（C3: 策略直接输出 buy_multiplier，无需二次计算）
        market_drop = None
        if market and market.shanghai_index:
            market_drop = market.shanghai_index.change
        
        if fund.type in ("ETF_Feeder", "QDII"):
            strategy_result = evaluate_etf_strategy(
                metrics, asset_class, fund.name, market_drop,
                nq_change=nq_change_pct  # C2: NQ 期货参与决策
            )
        else:
            strategy_result = evaluate_bond_strategy(metrics, asset_class, fund.name)
        
        logger.info(f"策略决策: {strategy_result.decision.value} (confidence: {strategy_result.confidence:.0%}, multiplier: {strategy_result.buy_multiplier:.1f}x)")
        
        # 8. M4: 估值数据时效性检查
        if valuation and valuation.is_stale:
            strategy_result.warnings.append("⚠️ 估值数据可能滞后，请参考实际盘面确认")
            strategy_result.confidence = max(0.2, strategy_result.confidence - 0.15)
            logger.warning(f"基金 {fund.code} 估值数据已过期，置信度下调")
        elif not valuation:
            strategy_result.warnings.append("⚠️ 无盘中估值（QDII-FOF），决策基于前日净值 + 期货参考")
            strategy_result.confidence = max(0.2, strategy_result.confidence - 0.1)
            logger.info(f"基金 {fund.code} 无盘中估值，置信度小幅下调")
        
        # 9. I5: QDII 数据时效性标注
        if fund.type == "QDII":
            futures_label = us_futures.futures_symbol if us_futures else "美股"
            if us_futures:
                strategy_result.warnings.append(
                    f"QDII 决策基于前日净值 + {futures_label}期货盘中走势，美股今夜开盘后实际走势可能不同"
                )
            else:
                strategy_result.warnings.append(
                    "QDII 决策仅基于前日净值，美股实时数据暂不可用，请酌情参考"
                )
        
        # 10. 直接使用策略输出的倍数（基于当前数据客观判断）
        db = get_database()
        final_multiplier = strategy_result.buy_multiplier
        final_decision = strategy_result.decision.value
        
        # 11. 保存估值快照（记录邮件发送时的实时估值/期货估值，用于事后回溯）
        snapshot_estimate = None
        snapshot_source = None
        if fund.type == "QDII":
            if us_futures:
                snapshot_estimate = us_futures.change_pct
                snapshot_source = f"futures:{us_futures.futures_symbol}"
        else:
            if valuation:
                snapshot_estimate = valuation.estimate_change
                snapshot_source = "fund_valuation"
        
        if snapshot_estimate is not None:
            db.save_valuation_snapshot(
                fund_code=fund.code,
                snapshot_date=datetime.now().date(),
                estimate_change=snapshot_estimate,
                source=snapshot_source
            )
        
        # 12. 查询过去5日的历史估值快照（用于与确认净值对比）
        recent_5_estimates = []
        if recent_5_changes:
            past_dates = [history[i][0] for i in range(min(5, len(history) - 1))]
            past_dates.reverse()  # 与 recent_5_changes 同为时间正序
            snapshots = db.get_valuation_snapshots(fund.code, past_dates)
            for d in past_dates:
                d_str = d.strftime("%m-%d") if hasattr(d, 'strftime') else str(d)[5:10]
                est = snapshots.get(d.isoformat() if hasattr(d, 'isoformat') else str(d))
                recent_5_estimates.append((d_str, est))
        
        # 13. 生成图表
        recent_90 = get_recent_nav(history, 90)
        recent_90_asc = list(reversed(recent_90))
        
        chart_image = generate_trend_chart(
            fund_name=fund.name,
            history_data=recent_90_asc,
            estimate_today=current_price,
            ma_60=metrics.ma_60,
            estimate_change=daily_change
        )
        
        # 14. 构建报告数据
        report = FundReport(
            fund_name=fund.name,
            fund_code=fund.code,
            fund_type=fund.type,
            decision=final_decision,
            reasoning=strategy_result.reasoning,
            estimate_change=realtime_change,
            previous_change=previous_change,
            recent_5_changes=recent_5_changes,
            recent_5_estimates=recent_5_estimates,
            percentile_250=metrics.percentile_250,
            ma_deviation=metrics.ma_deviation,
            zone=strategy_result.zone,
            holdings_summary=holdings.summary if holdings else None,
            top_gainers=holdings.top_gainers if holdings else None,
            top_losers=holdings.top_losers if holdings else None,
            chart_cid=f"chart_{fund.code}",
            warnings=list(strategy_result.warnings),
            percentile_60=metrics.percentile_60,
            percentile_1250=metrics.percentile_1250,
            volatility_60=metrics.volatility_60,
            percentile_consensus=metrics.percentile_consensus,
            trend_direction=metrics.trend_direction,
            strategy_decision=final_decision,
            strategy_confidence=strategy_result.confidence,
            strategy_reasoning=strategy_result.reasoning,
            asset_class=asset_class,
            buy_multiplier=final_multiplier,
            nq_change_pct=us_futures.change_pct if us_futures else None,
            nq_data_source=us_futures.data_source if us_futures else None,
            nq_futures_symbol=us_futures.futures_symbol if us_futures else None
        )
        
        # 15. 记录决策日志
        db.save_decision_log(
            fund_code=fund.code,
            fund_name=fund.name,
            fund_type=fund.type,
            asset_class=asset_class,
            decision_time=datetime.now(),
            estimate_change=daily_change,
            percentile_250=metrics.percentile_250,
            percentile_1250=metrics.percentile_1250,
            ma_60=metrics.ma_60,
            decision=final_decision,
            decision_nav=current_price,
            reasoning=strategy_result.reasoning
        )
        
        logger.info(f"基金 {fund.name} 处理完成: {final_decision} ({final_multiplier:.1f}x)")
        return FundResult(fund=fund, success=True, report=report, chart_image=chart_image)
        
    except Exception as e:
        logger.error(f"处理基金 {fund.name} 失败: {e}")
        return FundResult(fund=fund, success=False, error=str(e))

