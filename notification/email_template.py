"""
FundPilot 邮件模板模块 v5.0
专业、简洁、透明的投资决策报告
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class FundReport:
    """单只基金报告数据（双轨决策版 v3.0）"""
    fund_name: str
    fund_code: str
    fund_type: str
    decision: str                                    # 最终决策（保持兼容）
    reasoning: str                                   # 最终理由（保持兼容）
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
    # 双轨决策字段 v3.0
    strategy_decision: Optional[str] = None        # 策略主导决策
    strategy_confidence: Optional[float] = None    # 策略置信度
    strategy_reasoning: Optional[str] = None       # 策略理由
    ai_decision: Optional[str] = None              # AI主导决策
    ai_confidence: Optional[str] = None            # AI信心度（高/中/低）
    ai_reasoning: Optional[str] = None             # AI理由
    final_confidence: Optional[str] = None         # 最终信心度
    synthesis_method: Optional[str] = None         # 合成方式
    asset_class: Optional[str] = None              # 资产类型


# ============================================================
# 辅助函数
# ============================================================

DECISION_COLORS = {
    "双倍补仓": "#c0392b",
    "正常定投": "#27ae60",
    "暂停定投": "#e67e22",
    "观望": "#7f8c8d"
}

DECISION_BG_COLORS = {
    "双倍补仓": "#fadbd8",
    "正常定投": "#d5f5e3",
    "暂停定投": "#fdebd0",
    "观望": "#f4f6f6"
}


def _get_decision_color(decision: str) -> str:
    return DECISION_COLORS.get(decision, "#7f8c8d")


def _get_decision_bg(decision: str) -> str:
    return DECISION_BG_COLORS.get(decision, "#f4f6f6")


def _get_fund_type_label(fund_type: str) -> str:
    return {"Bond": "债券型", "ETF_Feeder": "ETF联接"}.get(fund_type, fund_type)


def _format_change(change: float) -> str:
    return f"{change:+.2f}%"


def _get_change_color(change: float) -> str:
    if change > 0:
        return "#c0392b"
    elif change < 0:
        return "#27ae60"
    return "#2c3e50"


def _get_zone_label(zone: str) -> str:
    """估值区间标签"""
    labels = {
        "低估区": "低估",
        "合理区": "合理",
        "偏高区": "偏高",
        "高估区": "高估",
        "极端低估": "极低",
        "极端高估": "极高"
    }
    return labels.get(zone, zone or "—")


def _get_zone_color(zone: str) -> str:
    colors = {
        "低估区": "#27ae60",
        "极端低估": "#1e8449",
        "合理区": "#2c3e50",
        "偏高区": "#e67e22",
        "高估区": "#c0392b",
        "极端高估": "#922b21"
    }
    return colors.get(zone, "#7f8c8d")


def _get_asset_label(asset_class: str) -> str:
    labels = {
        "GOLD_ETF": "黄金",
        "COMMODITY_CYCLE": "周期",
        "BOND_ENHANCED": "固收+",
        "BOND_PURE": "纯债",
        "DEFAULT_ETF": "ETF",
        "DEFAULT_BOND": "债基",
    }
    return labels.get(asset_class, "基金")


def _confidence_to_pct(conf: str) -> str:
    """Convert AI confidence to display format, handling both old (高/中/低) and new (70%) formats"""
    if not conf:
        return "—"
    # New format: contains percentage
    if "%" in conf:
        return conf
    # Old format: text labels
    if "高" in conf:
        return "80%"
    if "中" in conf:
        return "60%"
    if "低" in conf:
        return "40%"
    return conf


# ============================================================
# v5.0 邮件模板 - 专业简洁风格
# ============================================================

COMBINED_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            background: #f5f6fa;
            color: #2c3e50;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        
        .container {{
            max-width: 680px;
            margin: 0 auto;
            background: #ffffff;
        }}
        
        /* Header */
        .header {{
            background: #2c3e50;
            color: #ffffff;
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-brand {{
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        .header-date {{
            font-size: 14px;
            opacity: 0.85;
        }}
        
        /* Section */
        .section {{
            padding: 20px 24px;
            border-bottom: 1px solid #ecf0f1;
        }}
        .section:last-child {{
            border-bottom: none;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 12px;
            padding-bottom: 6px;
            border-bottom: 2px solid #3498db;
            display: inline-block;
        }}
        
        /* Summary Table */
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        .summary-table th {{
            text-align: left;
            padding: 10px 8px;
            background: #f8f9fa;
            font-weight: 500;
            color: #7f8c8d;
            border-bottom: 1px solid #ecf0f1;
        }}
        .summary-table td {{
            padding: 12px 8px;
            border-bottom: 1px solid #f4f6f6;
        }}
        .summary-table tr:last-child td {{
            border-bottom: none;
        }}
        .decision-tag {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 500;
        }}
        
        /* Fund Card */
        .fund-card {{
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            margin-bottom: 24px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }}
        .fund-card + .fund-card {{
            margin-top: 24px;
            border-top: 3px solid #3498db;
        }}
        .fund-header {{
            background: #f1f5f9;
            padding: 12px 16px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .fund-name {{
            font-size: 15px;
            font-weight: 600;
            color: #1e293b;
        }}
        .fund-meta {{
            font-size: 12px;
            color: #64748b;
            font-weight: 400;
            margin-left: 4px;
        }}
        .fund-body {{
            padding: 16px;
        }}
        
        /* Metrics Grid */
        .metrics-grid {{
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}
        .metric-item {{
            flex: 1;
            min-width: 80px;
            text-align: center;
            padding: 8px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .metric-label {{
            font-size: 11px;
            color: #64748b;
            margin-bottom: 2px;
        }}
        .metric-value {{
            font-size: 16px;
            font-weight: 600;
        }}
        
        /* Conclusion Box */
        .conclusion-box {{
            background: #f0f9ff;
            border: 1px solid #bae6fd;
            border-radius: 6px;
            padding: 12px 14px;
            margin-bottom: 12px;
        }}
        .conclusion-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        .conclusion-label {{
            font-size: 12px;
            color: #0369a1;
            font-weight: 500;
        }}
        .conclusion-decision {{
            font-size: 15px;
            font-weight: 700;
        }}
        .conclusion-reason {{
            font-size: 13px;
            color: #334155;
            line-height: 1.5;
        }}
        
        /* Process Section */
        .process-section {{
            margin-bottom: 12px;
        }}
        .process-title {{
            font-size: 12px;
            color: #64748b;
            margin-bottom: 8px;
            font-weight: 500;
        }}
        .process-grid {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .process-card {{
            background: #fafafa;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 10px 12px;
        }}
        .process-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .process-card-title {{
            font-size: 12px;
            font-weight: 600;
            color: #475569;
        }}
        .process-card-tag {{
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: 500;
        }}
        .process-card-reason {{
            font-size: 12px;
            color: #475569;
            line-height: 1.4;
            white-space: pre-wrap;
        }}
        
        /* Chart */
        .chart-container {{
            margin: 12px 0;
            border: 1px solid #e5e8ec;
            border-radius: 4px;
            overflow: hidden;
        }}
        .chart-container img {{
            display: block;
            width: 100%;
            height: auto;
        }}
        
        /* Warning */
        .warning-box {{
            background: #fef3c7;
            border: 1px solid #fcd34d;
            border-radius: 4px;
            padding: 10px 12px;
            margin-top: 12px;
            font-size: 12px;
            color: #92400e;
            line-height: 1.5;
        }}
        .warning-box ol {{
            margin: 0;
            padding-left: 18px;
        }}
        .warning-box li {{
            margin: 2px 0;
        }}
        
        /* Glossary */
        .glossary-section {{
            background: #f8f9fa;
            padding: 16px 24px;
        }}
        .glossary-title {{
            font-size: 13px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .glossary-grid {{
            display: grid;
            gap: 8px;
        }}
        .glossary-item {{
            display: flex;
            gap: 8px;
            font-size: 12px;
            line-height: 1.4;
        }}
        .glossary-term {{
            font-weight: 600;
            color: #2c3e50;
            min-width: 60px;
            flex-shrink: 0;
        }}
        .glossary-def {{
            color: #64748b;
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 14px 24px;
            font-size: 11px;
            color: #94a3b8;
            background: #f8f9fa;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-brand">FundPilot 定投助手</div>
            <div class="header-date">{date_str}</div>
        </div>
        
        <!-- Summary Section -->
        <div class="section">
            <div class="section-title">今日决策总览</div>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>基金</th>
                        <th>今日涨跌</th>
                        <th>估值水平</th>
                        <th style="text-align: right;">操作建议</th>
                    </tr>
                </thead>
                <tbody>
                    {summary_rows}
                </tbody>
            </table>
        </div>
        
        <!-- Fund Details -->
        <div class="section">
            <div class="section-title">基金分析详情</div>
            {fund_sections}
        </div>
        
        <!-- Glossary -->
        <div class="glossary-section">
            <div class="glossary-title">术语说明</div>
            <div class="glossary-grid">
                <div class="glossary-item">
                    <span class="glossary-term">估值分位</span>
                    <span class="glossary-def">当前价格在历史区间中的位置。0%=历史最低，100%=历史最高。类似考试成绩排名，85%意味着超过了85%的历史价格。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">均线偏离</span>
                    <span class="glossary-def">当前价格与过去60天平均价格的差距。偏离过大通常预示价格可能回归均值。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">量化策略</span>
                    <span class="glossary-def">基于数学模型和历史数据的客观规则判断，类似体检报告根据指标给出标准化建议。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">深度分析</span>
                    <span class="glossary-def">结合市场环境、持仓结构等因素的综合逻辑推理，类似医生问诊综合多种因素给出建议。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">置信度</span>
                    <span class="glossary-def">对该建议的确定程度。高=很有把握，中=有一定把握，低=参考性建议。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">操作建议</span>
                    <span class="glossary-def">综合量化策略与深度分析后的最终建议。当两者分歧时，系统会采取保守策略以控制风险。</span>
                </div>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            本报告由系统自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。
        </div>
    </div>
</body>
</html>"""


SUMMARY_ROW_TEMPLATE = """<tr>
    <td>
        <div style="font-weight: 500;">{fund_name}</div>
        <div style="font-size: 12px; color: #94a3b8;">{fund_code}</div>
    </td>
    <td style="color: {change_color}; font-weight: 500;">{estimate_change}</td>
    <td style="color: {zone_color};">{zone_label}</td>
    <td style="text-align: right;">
        <span class="decision-tag" style="background: {decision_bg}; color: {decision_color};">{decision}</span>
    </td>
</tr>"""


FUND_SECTION_TEMPLATE = """<div class="fund-card">
    <div class="fund-header">
        <div class="fund-name">{fund_name} <span class="fund-meta">({fund_code} · {fund_type} · {asset_label})</span></div>
    </div>
    <div class="fund-body">
        <!-- Metrics -->
        <div class="metrics-grid">
            <div class="metric-item">
                <div class="metric-label">今日涨跌</div>
                <div class="metric-value" style="color: {change_color};">{estimate_change}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">估值分位</div>
                <div class="metric-value" style="color: {zone_color};">{percentile_250:.0f}%</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">均线偏离</div>
                <div class="metric-value">{ma_deviation:+.2f}%</div>
            </div>
        </div>
        
        <!-- Conclusion -->
        <div class="conclusion-box">
            <div class="conclusion-header">
                <span class="conclusion-label">综合建议</span>
                <span class="conclusion-decision" style="color: {decision_color};">{decision}</span>
            </div>
            <div class="conclusion-reason">{reasoning}</div>
        </div>
        
        <!-- Decision Process -->
        <div class="process-section">
            <div class="process-title">决策过程</div>
            <div class="process-grid">
                <div class="process-card">
                    <div class="process-card-header">
                        <span class="process-card-title">量化策略 (置信度: {strategy_confidence_pct})</span>
                        <span class="process-card-tag" style="background: {strategy_tag_bg}; color: {strategy_tag_color};">{strategy_decision}</span>
                    </div>
                    <div class="process-card-reason">{strategy_reasoning}</div>
                </div>
                <div class="process-card">
                    <div class="process-card-header">
                        <span class="process-card-title">深度分析 (置信度: {ai_confidence})</span>
                        <span class="process-card-tag" style="background: {ai_tag_bg}; color: {ai_tag_color};">{ai_decision}</span>
                    </div>
                    <div class="process-card-reason">{ai_reasoning}</div>
                </div>
            </div>
        </div>
        
        <!-- Chart -->
        <div class="chart-container">
            <img src="cid:{chart_cid}" alt="走势图">
        </div>
        
        <!-- Warning -->
        {warning_html}
    </div>
</div>"""


def generate_combined_email_html(
    reports: list[FundReport],
    time_str: str,
    market_summary: str = ""
) -> str:
    """生成 v5.0 专业版邮件"""
    today = datetime.now()
    weekday_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
    date_str = f"{today.year}年{today.month}月{today.day}日 周{weekday_map[today.weekday()]}"
    
    # Summary Rows
    summary_rows = []
    for report in reports:
        summary_rows.append(SUMMARY_ROW_TEMPLATE.format(
            fund_name=report.fund_name,
            fund_code=report.fund_code,
            estimate_change=_format_change(report.estimate_change),
            change_color=_get_change_color(report.estimate_change),
            zone_label=_get_zone_label(report.zone),
            zone_color=_get_zone_color(report.zone),
            decision=report.decision,
            decision_color=_get_decision_color(report.decision),
            decision_bg=_get_decision_bg(report.decision)
        ))
    
    # Fund Sections
    fund_sections = []
    for i, report in enumerate(reports):
        # Warning - format as numbered list
        warning_html = ""
        if report.warnings:
            if len(report.warnings) == 1:
                warning_html = f'<div class="warning-box">{report.warnings[0]}</div>'
            else:
                # Use circled numbers for multiple warnings
                nums = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
                warning_items = "".join(
                    f'<div>{nums[i] if i < len(nums) else str(i+1)+"."} {w}</div>'
                    for i, w in enumerate(report.warnings)
                )
                warning_html = f'<div class="warning-box">{warning_items}</div>'
        
        # Strategy tag colors
        strategy_tag_bg = _get_decision_bg(report.strategy_decision or report.decision)
        strategy_tag_color = _get_decision_color(report.strategy_decision or report.decision)
        
        # AI tag colors
        ai_tag_bg = _get_decision_bg(report.ai_decision or report.decision)
        ai_tag_color = _get_decision_color(report.ai_decision or report.decision)
        
        fund_sections.append(FUND_SECTION_TEMPLATE.format(
            fund_name=report.fund_name,
            fund_code=report.fund_code,
            fund_type=_get_fund_type_label(report.fund_type),
            asset_label=_get_asset_label(report.asset_class),
            
            estimate_change=_format_change(report.estimate_change),
            change_color=_get_change_color(report.estimate_change),
            
            percentile_250=report.percentile_250,
            zone_color=_get_zone_color(report.zone),
            ma_deviation=report.ma_deviation,
            
            decision=report.decision,
            decision_color=_get_decision_color(report.decision),
            reasoning=report.reasoning or "系统综合判断",
            
            strategy_decision=report.strategy_decision or report.decision,
            strategy_confidence_pct=f"{report.strategy_confidence:.0%}" if report.strategy_confidence else "—",
            strategy_reasoning=report.strategy_reasoning or "规则判断",
            strategy_tag_bg=strategy_tag_bg,
            strategy_tag_color=strategy_tag_color,
            
            ai_decision=report.ai_decision or report.decision,
            ai_confidence=_confidence_to_pct(report.ai_confidence),
            ai_reasoning=report.ai_reasoning or "深度分析中",
            ai_tag_bg=ai_tag_bg,
            ai_tag_color=ai_tag_color,
            
            chart_cid=report.chart_cid or f"chart_{i}",
            warning_html=warning_html
        ))
    
    return COMBINED_EMAIL_TEMPLATE.format(
        date_str=date_str,
        summary_rows="".join(summary_rows),
        fund_sections="".join(fund_sections)
    )


def generate_combined_email_subject(reports: list[FundReport], time_str: str = "") -> str:
    """生成邮件标题"""
    if not reports:
        return "[FundPilot] 今日无基金数据"
    
    today = datetime.now()
    date_short = f"{today.month:02d}.{today.day:02d}"
    
    # 统计各决策数量
    decisions = {}
    for r in reports:
        d = r.decision
        decisions[d] = decisions.get(d, 0) + 1
    
    # 生成决策摘要
    summary_parts = []
    for d, count in decisions.items():
        summary_parts.append(f"{count}{d}")
    
    return f"[Fund Pilot] 投资决策 ({date_short}) - {'、'.join(summary_parts)}"
