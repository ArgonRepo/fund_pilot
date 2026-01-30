"""
FundPilot-AI HTML 邮件模板模块
生成美观的 HTML 邮件内容（合并报告版）
"""

from dataclasses import dataclass
from typing import Optional
from ai.decision_parser import get_decision_emoji, get_decision_color


@dataclass
class FundReport:
    """单只基金报告数据"""
    fund_name: str
    fund_code: str
    fund_type: str
    decision: str
    reasoning: str
    estimate_change: float
    percentile_60: float
    ma_deviation: float
    zone: str
    holdings_summary: Optional[str] = None
    top_gainers: Optional[list[str]] = None
    top_losers: Optional[list[str]] = None
    chart_cid: Optional[str] = None  # 图表 CID


# 合并邮件模板
COMBINED_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f5f6fa;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 700px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 22px;
            font-weight: 600;
        }}
        .header .subtitle {{
            margin-top: 8px;
            font-size: 14px;
            opacity: 0.9;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .summary-table th {{
            background-color: #f8f9fa;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
            color: #333;
            border-bottom: 2px solid #dee2e6;
            font-size: 13px;
        }}
        .summary-table td {{
            padding: 12px 8px;
            border-bottom: 1px solid #dee2e6;
            font-size: 13px;
        }}
        .fund-section {{
            margin: 15px 20px;
            padding: 15px;
            border-radius: 8px;
            background-color: #fafafa;
            border-left: 4px solid #667eea;
        }}
        .fund-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .fund-name {{
            font-size: 16px;
            font-weight: 600;
            color: #333;
        }}
        .fund-type {{
            font-size: 12px;
            color: #666;
            background-color: #e9ecef;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .decision-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 14px;
            color: white;
        }}
        .decision-double {{ background-color: #e74c3c; }}
        .decision-normal {{ background-color: #27ae60; }}
        .decision-stop {{ background-color: #f39c12; }}
        .decision-hold {{ background-color: #3498db; }}
        .fund-reason {{
            font-size: 13px;
            color: #555;
            margin-top: 8px;
            line-height: 1.5;
        }}
        .fund-metrics {{
            display: flex;
            gap: 15px;
            margin-top: 10px;
            flex-wrap: wrap;
        }}
        .metric {{
            font-size: 12px;
            color: #666;
        }}
        .metric-value {{
            font-weight: 600;
            color: #333;
        }}
        .positive {{ color: #e74c3c; }}
        .negative {{ color: #27ae60; }}
        .chart-container {{
            padding: 10px 20px;
            text-align: center;
        }}
        .chart-container img {{
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }}
        .holdings-info {{
            font-size: 12px;
            color: #666;
            margin-top: 8px;
            padding: 8px;
            background-color: #f0f0f0;
            border-radius: 4px;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 15px;
            text-align: center;
            font-size: 12px;
            color: #999;
        }}
        .market-summary {{
            padding: 15px 20px;
            background-color: #f8f9fa;
            margin: 0 20px 20px 20px;
            border-radius: 8px;
            font-size: 13px;
            color: #555;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 FundPilot-AI 决策报告</h1>
            <div class="subtitle">{time} | 共 {fund_count} 只基金</div>
        </div>
        
        <div class="market-summary">
            🌍 <strong>市场概况</strong>：{market_summary}
        </div>
        
        <div style="padding: 0 20px;">
            <table class="summary-table">
                <tr>
                    <th>基金</th>
                    <th>涨跌</th>
                    <th>分位</th>
                    <th>决策</th>
                </tr>
                {summary_rows}
            </table>
        </div>
        
        {fund_sections}
        
        <div class="footer">
            FundPilot-AI · 智能定投决策系统<br>
            本建议仅供参考，不构成投资建议
        </div>
    </div>
</body>
</html>
"""

SUMMARY_ROW_TEMPLATE = """
<tr>
    <td>{fund_name}</td>
    <td class="{change_class}">{estimate_change}</td>
    <td>{percentile_60}</td>
    <td><span style="color: {decision_color};">{decision_emoji} {decision}</span></td>
</tr>
"""

FUND_SECTION_TEMPLATE = """
<div class="fund-section" style="border-left-color: {decision_color};">
    <div class="fund-header">
        <div>
            <span class="fund-name">{fund_name}</span>
            <span class="fund-type">{fund_type_label}</span>
        </div>
        <span class="decision-badge {decision_class}">{decision_emoji} {decision}</span>
    </div>
    <div class="fund-reason">💡 {reasoning}</div>
    <div class="fund-metrics">
        <span class="metric">涨跌: <span class="metric-value {change_class}">{estimate_change}</span></span>
        <span class="metric">分位: <span class="metric-value">{percentile_60}</span></span>
        <span class="metric">偏离: <span class="metric-value {deviation_class}">{ma_deviation}</span></span>
        <span class="metric">区间: <span class="metric-value">{zone}</span></span>
    </div>
    {holdings_info}
</div>
<div class="chart-container">
    <img src="cid:{chart_cid}" alt="{fund_name}">
</div>
"""

HOLDINGS_INFO_TEMPLATE = """
<div class="holdings-info">
    🏢 {holdings_summary}
    {gainers_losers}
</div>
"""


def _get_decision_class(decision: str) -> str:
    """获取决策 CSS 类"""
    class_map = {
        "双倍补仓": "decision-double",
        "正常定投": "decision-normal",
        "暂停定投": "decision-stop",
        "观望": "decision-hold"
    }
    return class_map.get(decision, "decision-hold")


def _get_fund_type_label(fund_type: str) -> str:
    """获取基金类型标签"""
    type_map = {
        "Bond": "债券",
        "ETF_Feeder": "ETF联接"
    }
    return type_map.get(fund_type, fund_type)


def generate_combined_email_html(
    reports: list[FundReport],
    time_str: str,
    market_summary: str = "市场数据获取中..."
) -> str:
    """
    生成合并的 HTML 邮件内容
    
    Args:
        reports: 基金报告列表
        time_str: 时间字符串
        market_summary: 市场概况
    
    Returns:
        HTML 字符串
    """
    # 生成汇总行
    summary_rows = []
    for report in reports:
        change_class = "positive" if report.estimate_change >= 0 else "negative"
        summary_rows.append(SUMMARY_ROW_TEMPLATE.format(
            fund_name=report.fund_name[:10] + "..." if len(report.fund_name) > 10 else report.fund_name,
            estimate_change=f"{report.estimate_change:+.2f}%",
            change_class=change_class,
            percentile_60=f"{report.percentile_60:.0f}%",
            decision=report.decision,
            decision_emoji=get_decision_emoji(report.decision),
            decision_color=get_decision_color(report.decision)
        ))
    
    # 生成详细区块
    fund_sections = []
    for i, report in enumerate(reports):
        change_class = "positive" if report.estimate_change >= 0 else "negative"
        deviation_class = "positive" if report.ma_deviation >= 0 else "negative"
        
        # 持仓信息
        holdings_info = ""
        if report.holdings_summary:
            gainers_losers = ""
            if report.top_gainers:
                gainers_losers += f"<br>📈 领涨: {', '.join(report.top_gainers[:2])}"
            if report.top_losers:
                gainers_losers += f"<br>📉 领跌: {', '.join(report.top_losers[:2])}"
            
            holdings_info = HOLDINGS_INFO_TEMPLATE.format(
                holdings_summary=report.holdings_summary,
                gainers_losers=gainers_losers
            )
        
        fund_sections.append(FUND_SECTION_TEMPLATE.format(
            fund_name=report.fund_name,
            fund_type_label=_get_fund_type_label(report.fund_type),
            decision=report.decision,
            decision_emoji=get_decision_emoji(report.decision),
            decision_color=get_decision_color(report.decision),
            decision_class=_get_decision_class(report.decision),
            reasoning=report.reasoning,
            estimate_change=f"{report.estimate_change:+.2f}%",
            change_class=change_class,
            percentile_60=f"{report.percentile_60:.1f}%",
            ma_deviation=f"{report.ma_deviation:+.2f}%",
            deviation_class=deviation_class,
            zone=report.zone,
            holdings_info=holdings_info,
            chart_cid=report.chart_cid or f"chart_{i}"
        ))
    
    return COMBINED_EMAIL_TEMPLATE.format(
        time=time_str,
        fund_count=len(reports),
        market_summary=market_summary,
        summary_rows="".join(summary_rows),
        fund_sections="".join(fund_sections)
    )


def generate_combined_email_subject(
    reports: list[FundReport],
    time_str: str
) -> str:
    """生成合并邮件标题"""
    # 统计决策
    decisions = [r.decision for r in reports]
    decision_counts = {}
    for d in decisions:
        decision_counts[d] = decision_counts.get(d, 0) + 1
    
    # 找出主要决策
    main_decision = max(decision_counts, key=decision_counts.get)
    emoji = get_decision_emoji(main_decision)
    
    return f"【FundPilot】{time_str} 决策报告 | {len(reports)}只基金 {emoji}"


# 保留旧的单基金模板函数（兼容性）
def generate_email_html(
    fund_name: str,
    decision: str,
    reasoning: str,
    estimate_change: float,
    percentile_60: float,
    ma_deviation: float,
    zone: str,
    time_str: str,
    holdings_summary: Optional[str] = None,
    top_gainers: Optional[list[str]] = None,
    top_losers: Optional[list[str]] = None
) -> str:
    """生成单基金 HTML 邮件（兼容旧接口）"""
    report = FundReport(
        fund_name=fund_name,
        fund_code="",
        fund_type="",
        decision=decision,
        reasoning=reasoning,
        estimate_change=estimate_change,
        percentile_60=percentile_60,
        ma_deviation=ma_deviation,
        zone=zone,
        holdings_summary=holdings_summary,
        top_gainers=top_gainers,
        top_losers=top_losers,
        chart_cid="trend_chart"
    )
    return generate_combined_email_html([report], time_str)


def generate_email_subject(
    fund_name: str,
    decision: str,
    estimate_change: float,
    time_str: str
) -> str:
    """生成邮件标题（兼容旧接口）"""
    emoji = get_decision_emoji(decision)
    return f"【FundPilot】{time_str} 决策: [{decision}] {emoji} {estimate_change:+.2f}% ({fund_name})"
