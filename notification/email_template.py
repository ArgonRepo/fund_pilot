"""
FundPilot 邮件模板模块
专业、简洁的投资决策报告
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class FundReport:
    """单只基金报告数据"""
    fund_name: str
    fund_code: str
    fund_type: str
    decision: str
    reasoning: str
    estimate_change: float
    percentile_250: float  # 250 日分位值（主要参考）
    ma_deviation: float
    zone: str
    holdings_summary: Optional[str] = None
    top_gainers: Optional[list[str]] = None
    top_losers: Optional[list[str]] = None
    chart_cid: Optional[str] = None
    # 新增字段 v2.0
    warnings: Optional[list[str]] = None           # 风险提示列表
    percentile_60: Optional[float] = None          # 60日分位值
    percentile_500: Optional[float] = None         # 500日分位值
    volatility_60: Optional[float] = None          # 60日年化波动率
    percentile_consensus: Optional[str] = None     # 多周期共识
    trend_direction: Optional[str] = None          # 趋势方向


# 决策颜色配置（专业克制）
DECISION_COLORS = {
    "双倍补仓": "#D32F2F",   # 深红（强调行动）
    "正常定投": "#388E3C",   # 深绿（积极）
    "暂停定投": "#F57C00",   # 橙色（警告）
    "观望": "#757575"        # 灰色（中性）
}

DECISION_BG_COLORS = {
    "双倍补仓": "#FFEBEE",
    "正常定投": "#E8F5E9",
    "暂停定投": "#FFF3E0",
    "观望": "#F5F5F5"
}


def _get_decision_color(decision: str) -> str:
    return DECISION_COLORS.get(decision, "#757575")


def _get_decision_bg(decision: str) -> str:
    return DECISION_BG_COLORS.get(decision, "#F5F5F5")


def _get_fund_type_label(fund_type: str) -> str:
    return {"Bond": "债券型", "ETF_Feeder": "ETF联接"}.get(fund_type, fund_type)


def _format_change(change: float) -> str:
    """格式化涨跌幅"""
    return f"{change:+.2f}%"


def _get_change_color(change: float) -> str:
    """涨跌颜色"""
    if change > 0:
        return "#D32F2F"  # 红涨
    elif change < 0:
        return "#388E3C"  # 绿跌
    return "#333333"


def _get_consensus_color(consensus: str) -> str:
    """共识颜色"""
    colors = {
        "强低估": "#2E7D32",   # 深绿
        "弱低估": "#66BB6A",   # 浅绿
        "分歧": "#FF9800",     # 橙色
        "弱高估": "#EF5350",   # 浅红
        "强高估": "#C62828",   # 深红
    }
    return colors.get(consensus, "#757575")


def _get_trend_color(trend: str) -> str:
    """趋势颜色"""
    colors = {
        "上升趋势": "#D32F2F",   # 红色（偏强）
        "下降趋势": "#388E3C",   # 绿色（偏弱）
        "震荡": "#757575",       # 灰色（中性）
    }
    return colors.get(trend, "#757575")


# ============================================================
# 主邮件模板 - 简洁专业风格
# ============================================================

COMBINED_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background-color: #f8f9fa;
            color: #333;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        .email-container {{
            max-width: 640px;
            margin: 0 auto;
            background: #fff;
        }}
        
        /* 头部 - 简洁大方 */
        .header {{
            padding: 32px 24px 24px;
            border-bottom: 1px solid #eee;
        }}
        .header-title {{
            font-size: 20px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 4px;
        }}
        .header-meta {{
            font-size: 13px;
            color: #888;
        }}
        
        /* 决策摘要卡片 - 最重要 */
        .summary-section {{
            padding: 24px;
            background: #fafafa;
        }}
        .summary-title {{
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 16px;
        }}
        .decision-card {{
            display: table;
            width: 100%;
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 8px;
            border: 1px solid #eee;
        }}
        .decision-row {{
            display: table-row;
        }}
        .decision-cell {{
            display: table-cell;
            padding: 14px 16px;
            vertical-align: middle;
            border-bottom: 1px solid #f0f0f0;
        }}
        .decision-card .decision-row:last-child .decision-cell {{
            border-bottom: none;
        }}
        .fund-info {{
            width: 45%;
        }}
        .fund-name-short {{
            font-size: 14px;
            font-weight: 500;
            color: #1a1a1a;
        }}
        .fund-change {{
            font-size: 12px;
            margin-top: 2px;
        }}
        .decision-info {{
            width: 35%;
            text-align: right;
        }}
        .decision-tag {{
            display: inline-block;
            padding: 6px 14px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
        }}
        .percentile-info {{
            width: 20%;
            text-align: center;
            font-size: 13px;
            color: #666;
        }}
        .percentile-value {{
            font-weight: 600;
            color: #333;
        }}
        
        /* 详细分析区 */
        .detail-section {{
            padding: 24px;
        }}
        .fund-detail {{
            margin-bottom: 24px;
            padding-bottom: 24px;
            border-bottom: 1px solid #eee;
        }}
        .fund-detail:last-child {{
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }}
        .detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }}
        .detail-fund-name {{
            font-size: 15px;
            font-weight: 600;
            color: #1a1a1a;
        }}
        .detail-fund-type {{
            font-size: 11px;
            color: #888;
            margin-top: 2px;
        }}
        .detail-decision {{
            padding: 5px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        
        /* 分析理由 */
        .analysis-box {{
            background: #f8f9fa;
            border-radius: 6px;
            padding: 14px 16px;
            margin-bottom: 14px;
        }}
        .analysis-text {{
            font-size: 13px;
            color: #444;
            line-height: 1.7;
        }}
        
        /* 指标网格 */
        .metrics-grid {{
            display: table;
            width: 100%;
            margin-bottom: 14px;
        }}
        .metrics-row {{
            display: table-row;
        }}
        .metric-item {{
            display: table-cell;
            width: 25%;
            text-align: center;
            padding: 10px 0;
        }}
        .metric-label {{
            font-size: 11px;
            color: #888;
            margin-bottom: 4px;
        }}
        .metric-value {{
            font-size: 14px;
            font-weight: 600;
            color: #1a1a1a;
        }}
        
        /* 持仓信息 */
        .holdings-box {{
            background: #fff;
            border: 1px solid #eee;
            border-radius: 6px;
            padding: 12px 14px;
            font-size: 12px;
            color: #666;
            margin-bottom: 14px;
        }}
        .holdings-title {{
            font-weight: 500;
            color: #333;
            margin-bottom: 6px;
        }}
        
        /* 图表区 */
        .chart-box {{
            text-align: center;
        }}
        .chart-box img {{
            max-width: 100%;
            border-radius: 6px;
            border: 1px solid #eee;
        }}
        
        /* 页脚 */
        .footer {{
            padding: 20px 24px;
            background: #fafafa;
            border-top: 1px solid #eee;
            text-align: center;
        }}
        .footer-text {{
            font-size: 11px;
            color: #999;
        }}
        .footer-disclaimer {{
            font-size: 10px;
            color: #bbb;
            margin-top: 8px;
        }}
        
        /* 指标说明 */
        .glossary-section {{
            padding: 24px;
            background: #fff;
            border-top: 1px solid #f0f0f0;
        }}
        .glossary-title {{
            font-size: 12px;
            font-weight: 600;
            color: #444;
            margin-bottom: 12px;
            letter-spacing: 0.5px;
        }}
        .glossary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
            color: #666;
            line-height: 1.6;
        }}
        .glossary-table td {{
            padding: 8px 0;
            border-bottom: 1px dashed #eee;
            vertical-align: top;
        }}
        .glossary-table tr:last-child td {{
            border-bottom: none;
        }}
        .term-cell {{
            width: 90px;
            font-weight: 600;
            color: #555;
            padding-right: 12px;
            white-space: nowrap;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="summary-section">
            <table class="data-table" style="width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; border-radius: 8px; overflow: hidden;">
                <tr style="background: #f8f9fa;">
                    <th style="text-align: left; padding: 10px 12px; font-weight: 500; color: #888; border-bottom: 2px solid #eee; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">代码</th>
                    <th style="text-align: left; padding: 10px 12px; font-weight: 500; color: #888; border-bottom: 2px solid #eee; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">基金</th>
                    <th style="text-align: center; padding: 10px 12px; font-weight: 500; color: #888; border-bottom: 2px solid #eee; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">250日分位</th>
                    <th style="text-align: right; padding: 10px 12px; font-weight: 500; color: #888; border-bottom: 2px solid #eee; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">今日决策</th>
                </tr>
                {summary_rows}
            </table>
        </div>
        
        <div class="detail-section">
            {fund_sections}
        </div>
        
        <div class="glossary-section">
            <div class="glossary-title">📌 术语说明</div>
            <table class="glossary-table">
                <tr>
                    <td class="term-cell">多周期分位</td>
                    <td>同时查看 60日（3个月）、250日（1年）、500日（2年）的价格位置，交叉验证当前是否真的便宜或昂贵。</td>
                </tr>
                <tr>
                    <td class="term-cell">多周期共识</td>
                    <td>短中长期分位是否一致。"强低估"表示三个周期都认为便宜，信号更可靠；"分歧"表示看法不一致，需谨慎。</td>
                </tr>
                <tr>
                    <td class="term-cell">60日均线偏离</td>
                    <td>当前价格相对于近 60 天平均价的偏离。正值 = 高于均线（走强），负值 = 低于均线（走弱）。</td>
                </tr>
                <tr>
                    <td class="term-cell">趋势方向</td>
                    <td>基于短期与长期分位差异判断。"上升趋势"表示短期强于长期，"下降趋势"表示短期弱于长期，"震荡"表示无明显方向。</td>
                </tr>
                <tr>
                    <td class="term-cell">估值区间</td>
                    <td>基于分位值划分：黄金坑（0-20%）、低估区（20-40%）、合理区（40-60%）、偏高区（60-80%）、高估区（80-100%）。</td>
                </tr>
            </table>
        </div>
        
        <div class="footer">
            <div class="footer-text">FundPilot · 量化定投决策系统</div>
            <div class="footer-disclaimer">本报告基于量化模型生成，仅供投资参考，不构成买卖建议</div>
        </div>
    </div>
</body>
</html>"""


SUMMARY_ROW_TEMPLATE = """<tr>
    <td style="padding: 12px; border-bottom: 1px solid #f0f0f0; color: #888; font-size: 12px;">{fund_code}</td>
    <td style="padding: 12px; border-bottom: 1px solid #f0f0f0;">
        <div style="font-size: 14px; font-weight: 500; color: #1a1a1a;">{fund_name}</div>
        <div style="font-size: 12px; margin-top: 2px; color: {change_color};">{estimate_change}</div>
    </td>
    <td style="padding: 12px; border-bottom: 1px solid #f0f0f0; text-align: center;">
        <span style="font-weight: 600; color: #333;">{percentile}</span>
    </td>
    <td style="padding: 12px; border-bottom: 1px solid #f0f0f0; text-align: right;">
        <span style="display: inline-block; padding: 6px 14px; border-radius: 4px; font-size: 13px; font-weight: 500; background: {decision_bg}; color: {decision_color};">{decision}</span>
    </td>
</tr>"""


FUND_SECTION_TEMPLATE = """<div class="fund-detail">
    <div class="detail-header">
        <div>
            <div class="detail-fund-name">{fund_name}</div>
            <div class="detail-fund-type">{fund_type} · {fund_code}</div>
        </div>
        <span class="detail-decision" style="background: {decision_bg}; color: {decision_color};">{decision}</span>
    </div>
    
    <div class="analysis-box">
        <div class="analysis-text">{reasoning}</div>
    </div>
    
    {warnings_html}
    
    <div class="metrics-grid">
        <div class="metrics-row">
            <div class="metric-item">
                <div class="metric-label">今日涨跌</div>
                <div class="metric-value" style="color: {change_color};">{estimate_change}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">多周期分位</div>
                <div class="metric-value" style="font-size: 12px;">{multi_percentile}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">多周期共识</div>
                <div class="metric-value" style="color: {consensus_color};">{consensus}</div>
            </div>
        </div>
        <div class="metrics-row">
            <div class="metric-item">
                <div class="metric-label">60日均线偏离</div>
                <div class="metric-value" style="color: {deviation_color};">{ma_deviation}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">趋势方向</div>
                <div class="metric-value" style="color: {trend_color};">{trend}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">估值区间</div>
                <div class="metric-value">{zone}</div>
            </div>
        </div>
    </div>
    
    {holdings_html}
    
    <div class="chart-box">
        <img src="cid:{chart_cid}" alt="趋势图">
    </div>
</div>"""


HOLDINGS_TEMPLATE = """<div class="holdings-box">
    <div class="holdings-title">持仓动态</div>
    <div>{summary}</div>
    {details}
</div>"""


def generate_combined_email_html(
    reports: list[FundReport],
    time_str: str,
    market_summary: str = ""
) -> str:
    """
    生成合并的 HTML 邮件内容
    
    Args:
        reports: 基金报告列表
        time_str: 时间字符串（如 "14:30"）
        market_summary: 市场概况（暂未使用）
    
    Returns:
        HTML 字符串
    """
    # 日期格式化
    today = datetime.now()
    date_str = f"{today.month}月{today.day}日 {time_str}"
    
    # 生成摘要行
    summary_rows = []
    for report in reports:
        # 基金名称截断
        name = report.fund_name
        if len(name) > 12:
            name = name[:11] + "…"
        
        summary_rows.append(SUMMARY_ROW_TEMPLATE.format(
            fund_code=report.fund_code,
            fund_name=name,
            estimate_change=_format_change(report.estimate_change),
            change_color=_get_change_color(report.estimate_change),
            percentile=f"{report.percentile_250:.0f}%",
            decision=report.decision,
            decision_color=_get_decision_color(report.decision),
            decision_bg=_get_decision_bg(report.decision)
        ))
    
    # 生成详细区块
    fund_sections = []
    for i, report in enumerate(reports):
        # 持仓信息
        holdings_html = ""
        if report.holdings_summary:
            details = ""
            if report.top_gainers:
                details += f"领涨: {', '.join(report.top_gainers[:2])}"
            if report.top_losers:
                if details:
                    details += " · "
                details += f"领跌: {', '.join(report.top_losers[:2])}"
            
            holdings_html = HOLDINGS_TEMPLATE.format(
                summary=report.holdings_summary,
                details=f"<div style='margin-top: 6px; color: #888;'>{details}</div>" if details else ""
            )
        
        # 风险提示 HTML
        warnings_html = ""
        if report.warnings:
            warning_items = "".join([
                f"<div style='margin-bottom: 4px;'>{w}</div>" 
                for w in report.warnings
            ])
            warnings_html = f"""<div style="background: #FFF8E1; border-left: 3px solid #FFC107; padding: 10px 14px; margin-bottom: 14px; border-radius: 4px; font-size: 12px; color: #5D4037;">
                <div style="font-weight: 500; margin-bottom: 6px;">⚠️ 风险提示</div>
                {warning_items}
            </div>"""
        
        # 多周期分位显示
        p60 = f"{report.percentile_60:.0f}" if report.percentile_60 is not None else "?"
        p250 = f"{report.percentile_250:.0f}"
        p500 = f"{report.percentile_500:.0f}" if report.percentile_500 is not None else "?"
        multi_percentile = f"{p60}/{p250}/{p500}%"
        
        # 共识颜色
        consensus = report.percentile_consensus or "N/A"
        consensus_color = _get_consensus_color(consensus)
        
        # 趋势方向
        trend = report.trend_direction or "N/A"
        trend_color = _get_trend_color(trend)
        
        fund_sections.append(FUND_SECTION_TEMPLATE.format(
            fund_name=report.fund_name,
            fund_type=_get_fund_type_label(report.fund_type),
            fund_code=report.fund_code,
            decision=report.decision,
            decision_color=_get_decision_color(report.decision),
            decision_bg=_get_decision_bg(report.decision),
            reasoning=report.reasoning,
            estimate_change=_format_change(report.estimate_change),
            change_color=_get_change_color(report.estimate_change),
            multi_percentile=multi_percentile,
            consensus=consensus,
            consensus_color=consensus_color,
            ma_deviation=_format_change(report.ma_deviation),
            deviation_color=_get_change_color(report.ma_deviation),
            trend=trend,
            trend_color=trend_color,
            zone=report.zone,
            warnings_html=warnings_html,
            holdings_html=holdings_html,
            chart_cid=report.chart_cid or f"chart_{i}"
        ))
    
    return COMBINED_EMAIL_TEMPLATE.format(
        date_str=date_str,
        fund_count=len(reports),
        summary_rows="\n".join(summary_rows),
        fund_sections="\n".join(fund_sections)
    )


def generate_combined_email_subject(
    reports: list[FundReport],
    time_str: str
) -> str:
    """
    生成邮件标题 - 遵照用户指定格式
    
    格式: [Fund Pilot] 投资决策 (26.01.30) - 1补仓/1观望
    """
    today = datetime.now()
    # 格式化日期为 YY.MM.DD
    date_str = today.strftime("%y.%m.%d")
    
    # 统计决策
    decision_counts = {}
    for r in reports:
        short_name = {
            "双倍补仓": "补仓",
            "正常定投": "定投",
            "暂停定投": "暂停",
            "观望": "观望"
        }.get(r.decision, r.decision)
        decision_counts[short_name] = decision_counts.get(short_name, 0) + 1
    
    # 生成决策摘要
    priority = ["补仓", "定投", "暂停", "观望"]
    summary_parts = []
    for d in priority:
        if d in decision_counts:
            summary_parts.append(f"{decision_counts[d]}{d}")
    
    summary = "/".join(summary_parts)
    
    return f"[Fund Pilot] 投资决策 ({date_str}) - {summary}"


# ============================================================
# 兼容旧接口
# ============================================================

def generate_email_html(
    fund_name: str,
    decision: str,
    reasoning: str,
    estimate_change: float,
    percentile_250: float,
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
        percentile_250=percentile_250,
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
    today = datetime.now()
    date_str = today.strftime("%y.%m.%d")
    return f"[Fund Pilot] 投资决策 ({date_str}) - {decision}"
