"""
FundPilot-AI 定时任务定义模块
定义预警和决策任务（合并报告版）
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.config import get_config, FundConfig
from core.logger import get_logger
from core.database import get_database
from data.fund_valuation import fetch_fund_valuation, FundValuation
from data.fund_history import get_fund_history, get_recent_nav
from data.holdings import get_holdings_with_quotes
from data.market import get_market_context
from data.http_client import request_stats  # 请求统计
from strategy.indicators import calculate_all_metrics, QuantMetrics
from strategy.etf_strategy import evaluate_etf_strategy
from strategy.bond_strategy import evaluate_bond_strategy
from ai.deepseek_client import get_deepseek_client
from ai.prompt_builder import build_context, get_system_prompt
from ai.decision_parser import parse_ai_decision
from visualization.chart import generate_trend_chart
from notification.email_template import FundReport, generate_combined_email_html, generate_combined_email_subject
from notification.sender import send_combined_report, send_error_notification
from scheduler.calendar import should_run_task

logger = get_logger("jobs")


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
    处理单只基金的决策流程
    
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
        
        history = get_fund_history(fund.code, days=260)
        if not history:
            logger.warning(f"基金 {fund.code} 获取历史净值失败")
            return FundResult(fund=fund, success=False, error="获取历史净值失败")
        
        # 3. 计算量化指标（使用250日分位值）
        prices_history = [nav for _, nav in history]
        metrics = calculate_all_metrics(
            current_price=valuation.estimate_nav,
            prices_history=prices_history,
            daily_change=valuation.estimate_change
        )
        
        # 4. 获取持仓信息 (尝试获取所有基金的重仓股，如债券基、混合基)
        holdings = get_holdings_with_quotes(fund)
        
        # 5. 获取市场环境
        market = get_market_context()
        
        # 6. 量化策略预判
        if fund.type == "ETF_Feeder":
            strategy_result = evaluate_etf_strategy(metrics)
        else:
            strategy_result = evaluate_bond_strategy(metrics)
        
        # 7. AI 决策
        ai_decision = None
        ai_reasoning = strategy_result.reasoning  # 默认使用策略理由
        
        try:
            client = get_deepseek_client()
            context_json = build_context(fund, valuation, metrics, holdings, market)
            ai_response = client.get_decision(get_system_prompt(), context_json)
            
            if ai_response:
                parsed = parse_ai_decision(ai_response)
                if parsed.is_valid:
                    ai_decision = parsed.decision
                    ai_reasoning = parsed.reasoning
                    
        except Exception as e:
            logger.warning(f"AI 决策失败，使用量化策略: {e}")
            ai_decision = strategy_result.decision.value
        
        # 最终决策
        final_decision = ai_decision or strategy_result.decision.value
        
        # 8. 生成图表
        recent_10 = get_recent_nav(history, 10)
        # 按日期升序排列
        recent_10_asc = list(reversed(recent_10))
        
        chart_image = generate_trend_chart(
            fund_name=fund.name,
            history_10d=recent_10_asc,
            estimate_today=valuation.estimate_nav,
            ma_60=metrics.ma_60,
            estimate_change=valuation.estimate_change
        )
        
        # 9. 构建报告数据
        report = FundReport(
            fund_name=fund.name,
            fund_code=fund.code,
            fund_type=fund.type,
            decision=final_decision,
            reasoning=ai_reasoning,
            estimate_change=valuation.estimate_change,
            percentile_250=metrics.percentile_250,
            ma_deviation=metrics.ma_deviation,
            zone=strategy_result.zone,
            holdings_summary=holdings.summary if holdings else None,
            top_gainers=holdings.top_gainers if holdings else None,
            top_losers=holdings.top_losers if holdings else None,
            chart_cid=f"chart_{fund.code}"
        )
        
        # 10. 记录决策日志（复用 context_json）
        db = get_database()
        db.save_decision_log(
            fund_code=fund.code,
            decision_time=datetime.now(),
            estimate_change=valuation.estimate_change,
            percentile_250=metrics.percentile_250,
            ma_60=metrics.ma_60,
            ai_decision=final_decision,
            ai_reasoning=ai_reasoning,
            raw_context=context_json
        )
        
        logger.info(f"基金 {fund.name} 处理完成: {final_decision}")
        return FundResult(fund=fund, success=True, report=report, chart_image=chart_image)
        
    except Exception as e:
        logger.error(f"处理基金 {fund.name} 失败: {e}")
        return FundResult(fund=fund, success=False, error=str(e))


def run_decision_task():
    """
    运行决策任务（主入口）
    收集所有基金结果，发送一封合并报告邮件
    """
    logger.info("="*50)
    logger.info("FundPilot-AI 决策任务启动")
    logger.info("="*50)
    
    # 检查交易日
    if not should_run_task():
        return
    
    config = get_config()
    time_str = datetime.now().strftime("%H:%M")
    
    # 获取市场概况
    market = get_market_context()
    market_summary = market.summary if market else "市场数据获取中..."
    
    # 处理所有基金
    results: list[FundResult] = []
    for fund in config.funds:
        try:
            result = process_single_fund(fund, time_str)
            results.append(result)
        except Exception as e:
            logger.error(f"处理基金 {fund.name} 异常: {e}")
            results.append(FundResult(fund=fund, success=False, error=str(e)))
    
    # 统计结果
    success_results = [r for r in results if r.success and r.report]
    fail_count = len(results) - len(success_results)
    
    logger.info(f"处理完成: 成功 {len(success_results)}, 失败 {fail_count}")
    
    if not success_results:
        send_error_notification(f"所有 {len(results)} 只基金处理失败，请检查系统日志。")
        return
    
    # 构建合并邮件
    reports = [r.report for r in success_results]
    charts = {r.report.chart_cid: r.chart_image for r in success_results if r.chart_image}
    
    # 生成 HTML
    html_content = generate_combined_email_html(
        reports=reports,
        time_str=time_str,
        market_summary=market_summary
    )
    
    # 生成标题
    subject = generate_combined_email_subject(reports, time_str)
    
    # 发送合并邮件
    success = send_combined_report(subject, html_content, charts)
    
    if success:
        logger.info(f"合并报告邮件发送成功: {len(reports)} 只基金")
    else:
        logger.error("合并报告邮件发送失败")
    
    # 检查数据获取失败率
    failure_rate = request_stats.get_failure_rate()
    if failure_rate > 50:
        logger.warning(f"数据获取失败率过高: {failure_rate:.1f}%")
        send_error_notification(
            f"数据获取失败率过高: {failure_rate:.1f}%\n"
            f"总请求: {request_stats.total}, 失败: {request_stats.failed}\n"
            f"请检查网络或 API 状态。"
        )
    
    # 重置统计
    request_stats.reset()
    
    logger.info("="*50)
    logger.info("决策任务完成")
    logger.info("="*50)



def run_alert_task():
    """
    运行盘中预警任务（12:30 上午数据快照）
    发送包含市场概况和基金数据的预警邮件
    """
    logger.info("="*50)
    logger.info("FundPilot 盘中预警任务启动")
    logger.info("="*50)
    
    if not should_run_task():
        return
    
    config = get_config()
    time_str = datetime.now().strftime("%H:%M")
    
    # 导入预警模板
    from notification.alert_template import (
        AlertFundData, MarketData,
        generate_alert_email_html, generate_alert_email_subject
    )
    from notification.sender import send_alert_email
    
    # 1. 获取市场数据
    market_ctx = get_market_context()
    market_data = None
    if market_ctx:
        market_data = MarketData(
            shanghai_price=market_ctx.shanghai_index.current if market_ctx.shanghai_index else 0,
            shanghai_change=market_ctx.shanghai_index.change if market_ctx.shanghai_index else 0,
            hs300_price=market_ctx.hs300_index.current if market_ctx.hs300_index else 0,
            hs300_change=market_ctx.hs300_index.change if market_ctx.hs300_index else 0
        )
    
    # 2. 获取各基金数据
    fund_data_list: list[AlertFundData] = []
    
    for fund in config.funds:
        try:
            # 获取实时估值
            valuation = fetch_fund_valuation(fund.code)
            if not valuation:
                logger.warning(f"预警: {fund.name} 估值获取失败")
                continue
            
            # 获取历史数据计算指标
            history = get_fund_history(fund.code, days=260)
            if not history:
                logger.warning(f"预警: {fund.name} 历史数据获取失败")
                continue
            
            prices_history = [nav for _, nav in history]
            metrics = calculate_all_metrics(
                current_price=valuation.estimate_nav,
                prices_history=prices_history,
                daily_change=valuation.estimate_change
            )
            
            # 确定估值区间
            from strategy.indicators import get_percentile_zone
            zone = get_percentile_zone(metrics.percentile_250)
            
            # 获取持仓信息 (用于穿透分析)
            holdings = get_holdings_with_quotes(fund)
            holdings_txt = None
            if holdings and holdings.holdings:
                # 取波动最大的前3只重仓股
                valid_holdings = [h for h in holdings.holdings if h.change is not None]
                if valid_holdings:
                    sorted_h = sorted(valid_holdings, key=lambda x: abs(x.change), reverse=True)
                    top3 = sorted_h[:3]
                    parts = []
                    for h in top3:
                        # 红色涨，绿色跌
                        color = "#D32F2F" if h.change > 0 else "#388E3C"
                        parts.append(f"{h.stock_name} <span style='color:{color}'>{h.change:+.1f}%</span>")
                    holdings_txt = "&nbsp; ".join(parts)
            
            fund_data = AlertFundData(
                fund_name=fund.name,
                fund_code=fund.code,
                fund_type=fund.type,
                estimate_change=valuation.estimate_change,
                percentile_250=metrics.percentile_250,
                ma_deviation=metrics.ma_deviation,
                zone=zone,
                drawdown=metrics.drawdown_60,  # 使用 60 日回撤
                holdings_txt=holdings_txt
            )
            fund_data_list.append(fund_data)
            
            logger.info(f"预警: {fund.name} {valuation.estimate_change:+.2f}% 分位:{metrics.percentile_250:.0f}%")
            
        except Exception as e:
            logger.warning(f"预警获取 {fund.name} 失败: {e}")
    
    if not fund_data_list:
        logger.error("预警: 所有基金数据获取失败")
        return
    
    # 3. 生成并发送邮件
    subject = generate_alert_email_subject()
    html_content = generate_alert_email_html(fund_data_list, market_data, time_str)
    
    success = send_alert_email(subject, html_content)
    
    if success:
        logger.info(f"盘中预警邮件发送成功: {len(fund_data_list)} 只基金")
    else:
        logger.error("盘中预警邮件发送失败")
    
    logger.info("="*50)
    logger.info("预警任务完成")
    logger.info("="*50)
