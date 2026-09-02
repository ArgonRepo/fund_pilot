"""
FundPilot-AI 定时任务编排模块
定义预警和决策任务入口（双轨决策版 v3.1 + QDII 支持）
"""

from datetime import datetime
import time

from core.config import get_config
from core.logger import get_logger
from core.http_client import request_stats
from data.fund_valuation import fetch_fund_valuation
from data.fund_history import get_fund_history
from data.holdings import get_holdings_with_quotes
from data.market import get_market_context
from data.us_market import fetch_us_futures_for_fund
from strategy.indicators import calculate_all_metrics, get_percentile_zone, get_percentile_consensus
from notification.email_template import FundReport, generate_combined_email_html, generate_combined_email_subject
from notification.sender import send_combined_report, send_error_notification
from scheduler.calendar import should_run_task
from scheduler.pipeline import FundResult, process_single_fund

logger = get_logger("jobs")

# 单基金重试：整轮任务内，单只基金取数失败时延时重试一次，应对瞬时网络/限流。
# （底层 HTTP/AkShare 已各有 3 次重试，此处是「单只基金整体」这一层的补强。）
MAX_ATTEMPTS = 2   # 总尝试次数（含首次）
RETRY_DELAY = 5    # 重试间隔（秒）


def _failed_alert_fund(fund, reason: str):
    """构造一只取数失败的预警基金数据（保证邮件与 funds.json 对齐）"""
    from notification.alert_template import AlertFundData
    return AlertFundData(
        fund_name=fund.name,
        fund_code=fund.code,
        fund_type=fund.type,
        estimate_change=None,
        percentile_250=0.0,
        ma_deviation=0.0,
        zone="",
        drawdown=0.0,
        error=reason,
    )


def _failed_fund_report(fund, reason: str) -> FundReport:
    """构造一只取数失败的决策报告（保证邮件与 funds.json 对齐）"""
    return FundReport(
        fund_name=fund.name,
        fund_code=fund.code,
        fund_type=fund.type,
        decision="数据缺失",
        reasoning=reason,
        estimate_change=None,
        percentile_250=0.0,
        ma_deviation=0.0,
        zone="",
        error=reason,
    )


def _collect_alert_fund_data(fund):
    """
    收集单只基金的盘中预警数据。

    成功返回完整 AlertFundData；任一取数环节失败则返回带 error 的 AlertFundData
    （不抛异常、不 continue），交由调用方决定是否重试，最终在邮件中标注失败。
    """
    from notification.alert_template import AlertFundData

    try:
        # 实时估值（QDII 不走估值API，盘中参考来自期货）
        # 估值取不到不再整只失败：降级用「前日净值」口径展示，邮件中标注来源
        valuation = None
        if fund.type != "QDII":
            valuation = fetch_fund_valuation(fund.code, fund.underlying_etf)

        # 历史净值（用于多周期分位等指标）
        history = get_fund_history(fund.code, days=1250)
        if not history:
            return _failed_alert_fund(fund, "历史净值未取到")

        # 估值降级: 用于指标计算
        estimate_source = None
        if valuation:
            current_price = valuation.estimate_nav
            daily_change = valuation.estimate_change
            realtime_change = valuation.estimate_change
            estimate_source = valuation.source  # eastmoney / etf_proxy / holdings_weighted
        else:
            current_price = history[0][1]
            if len(history) >= 2:
                prev_price = history[1][1]
                daily_change = (current_price - prev_price) / prev_price * 100
            else:
                daily_change = 0.0
            # QDII 盘中显示期货参考；其余基金（债基等）降级显示前日净值涨跌
            realtime_change = None if fund.type == "QDII" else daily_change
            estimate_source = None if fund.type == "QDII" else "last_nav"

        prices_history = [nav for _, nav in history]
        metrics = calculate_all_metrics(
            current_price=current_price,
            prices_history=prices_history,
            daily_change=daily_change
        )

        # 确定估值区间（资产感知动态阈值）
        from strategy.asset_config import infer_asset_class, get_thresholds
        _asset_class = fund.asset_class or infer_asset_class(fund.type, fund.name)
        thresholds = get_thresholds(_asset_class)
        zones = thresholds.zone_thresholds
        p = metrics.percentile_250
        if p < zones[0]:
            zone = "黄金坑"
        elif p < zones[1]:
            zone = "低估区"
        elif p < zones[2]:
            zone = "合理区"
        elif p < zones[3]:
            zone = "偏高区"
        else:
            zone = "高估区"

        # 多周期共识（资产特定阈值）
        consensus = get_percentile_consensus(
            metrics,
            low_threshold=thresholds.consensus_low_threshold,
            high_threshold=thresholds.consensus_high_threshold
        )

        # 持仓穿透（黄金/QDII 等无股票持仓的基金跳过）
        holdings = None
        if _asset_class not in ("GOLD_ETF", "US_EQUITY_INDEX") and fund.type != "QDII":
            holdings = get_holdings_with_quotes(fund)
        holdings_txt = None
        if holdings and holdings.holdings:
            valid_holdings = [h for h in holdings.holdings if h.change is not None]
            if valid_holdings:
                sorted_h = sorted(valid_holdings, key=lambda x: abs(x.change), reverse=True)
                top3 = sorted_h[:3]
                parts = []
                for h in top3:
                    color = "#D32F2F" if h.change > 0 else "#388E3C"
                    parts.append(f"{h.stock_name} <span style='color:{color}'>{h.change:+.1f}%</span>")
                holdings_txt = "&nbsp; ".join(parts)

        # QDII: 对应期货数据
        us_futures = None
        if fund.type == "QDII":
            us_futures = fetch_us_futures_for_fund(fund.name)
            if us_futures:
                logger.info(f"盘中预警 {us_futures.futures_symbol}: {us_futures.change_pct:+.2f}% [来源: {us_futures.data_source}]")

        fund_data = AlertFundData(
            fund_name=fund.name,
            fund_code=fund.code,
            fund_type=fund.type,
            estimate_change=realtime_change,
            estimate_source=estimate_source,
            percentile_250=metrics.percentile_250,
            ma_deviation=metrics.ma_deviation,
            zone=zone,
            drawdown=metrics.drawdown_60,
            holdings_txt=holdings_txt,
            percentile_60=metrics.percentile_60,
            percentile_1250=metrics.percentile_1250,
            volatility_60=metrics.volatility_60,
            percentile_consensus=consensus,
            nq_change_pct=us_futures.change_pct if (fund.type == "QDII" and us_futures) else None,
            nq_data_source=us_futures.data_source if (fund.type == "QDII" and us_futures) else None,
            nq_market_status=us_futures.market_status if (fund.type == "QDII" and us_futures) else None,
            nq_futures_symbol=us_futures.futures_symbol if (fund.type == "QDII" and us_futures) else None
        )

        logger.info(f"预警: {fund.name} {daily_change:+.2f}% 分位:{metrics.percentile_250:.0f}%")
        return fund_data

    except Exception as e:
        logger.warning(f"预警获取 {fund.name} 异常: {e}")
        return _failed_alert_fund(fund, f"处理异常: {e}")


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
    
    # 处理所有基金（含单基金重试）
    results: list[FundResult] = []
    for fund in config.funds:
        result = process_single_fund(fund, time_str)
        # 失败则重试，应对瞬时网络/限流（决策日志仅在成功末尾写入，重试不产生重复写入）
        for attempt in range(1, MAX_ATTEMPTS):
            if result.success:
                break
            logger.warning(f"决策 {fund.name} 第{attempt}次失败: {result.error}，{RETRY_DELAY}s 后重试")
            time.sleep(RETRY_DELAY)
            result = process_single_fund(fund, time_str)
        if not result.success:
            logger.warning(f"决策 {fund.name} 经 {MAX_ATTEMPTS} 次尝试仍失败: {result.error}")
        results.append(result)

    # 统计结果
    success_results = [r for r in results if r.success and r.report]
    fail_count = len(results) - len(success_results)
    logger.info(f"处理完成: 成功 {len(success_results)}, 失败 {fail_count}")

    # 构建合并邮件报告：成功取 report，失败构造标注 error 的最小报告
    # （邮件与 funds.json 对齐，失败的基金以「数据获取失败」卡片呈现，不静默吞掉）
    reports: list[FundReport] = []
    charts = {}
    for r in results:
        if r.success and r.report:
            reports.append(r.report)
            if r.chart_image:
                charts[r.report.chart_cid] = r.chart_image
        else:
            reports.append(_failed_fund_report(r.fund, r.error or "处理失败"))

    if not reports:
        send_error_notification(f"所有 {len(results)} 只基金处理失败，请检查系统日志。")
        return

    # 生成 HTML 与标题
    html_content = generate_combined_email_html(
        reports=reports,
        time_str=time_str,
        market_summary=market_summary
    )
    subject = generate_combined_email_subject(reports, time_str)

    # 发送合并邮件
    success = send_combined_report(subject, html_content, charts)

    if success:
        logger.info(f"合并报告邮件发送成功: 共 {len(reports)} 只基金（失败 {fail_count}）")
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
        MarketData,
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

    # 2. 获取各基金数据（含单基金重试；失败也入列，邮件中标注「数据获取失败」）
    fund_data_list = []
    for fund in config.funds:
        fund_data = _collect_alert_fund_data(fund)
        # 失败则重试，应对瞬时网络/限流（确定性失败重试无效，但无副作用）
        for attempt in range(1, MAX_ATTEMPTS):
            if not fund_data.error:
                break
            logger.warning(f"预警 {fund.name} 第{attempt}次失败: {fund_data.error}，{RETRY_DELAY}s 后重试")
            time.sleep(RETRY_DELAY)
            fund_data = _collect_alert_fund_data(fund)
        if fund_data.error:
            logger.warning(f"预警 {fund.name} 经 {MAX_ATTEMPTS} 次尝试仍失败: {fund_data.error}")
        fund_data_list.append(fund_data)

    if not fund_data_list:
        logger.error("预警: 无基金配置，跳过")
        return

    success_count = sum(1 for f in fund_data_list if not f.error)
    fail_count = len(fund_data_list) - success_count
    logger.info(f"预警数据采集完成: 成功 {success_count}, 失败 {fail_count}")

    # 3. 生成并发送邮件（失败基金以失败行呈现，邮件与 funds.json 对齐）
    subject = generate_alert_email_subject()
    html_content = generate_alert_email_html(fund_data_list, market_data, time_str)

    success = send_alert_email(subject, html_content)

    if success:
        logger.info(f"盘中预警邮件发送成功: 共 {len(fund_data_list)} 只基金（失败 {fail_count}）")
    else:
        logger.error("盘中预警邮件发送失败")

    logger.info("="*50)
    logger.info("预警任务完成")
    logger.info("="*50)
