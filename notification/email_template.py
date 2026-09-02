"""
FundPilot 邮件模板模块 v5.0
专业、简洁、透明的投资决策报告
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class FundReport:
    """单只基金报告数据"""
    fund_name: str
    fund_code: str
    fund_type: str
    decision: str                                    # 最终决策
    reasoning: str                                   # 决策理由
    estimate_change: Optional[float]
    percentile_250: float  # 250 日分位值（主要参考）
    ma_deviation: float
    zone: str
    error: Optional[str] = None             # 取数失败原因（非空表示本次未生成决策）
    holdings_summary: Optional[str] = None
    top_gainers: Optional[list[str]] = None
    top_losers: Optional[list[str]] = None
    chart_cid: Optional[str] = None
    warnings: Optional[list[str]] = None           # 风险提示列表
    percentile_60: Optional[float] = None          # 60日分位值
    percentile_1250: Optional[float] = None         # 1250日分位值
    volatility_60: Optional[float] = None          # 60日年化波动率
    percentile_consensus: Optional[str] = None     # 多周期共识
    trend_direction: Optional[str] = None          # 趋势方向
    strategy_decision: Optional[str] = None        # 策略决策
    strategy_confidence: Optional[float] = None    # 策略置信度
    strategy_reasoning: Optional[str] = None       # 策略理由
    asset_class: Optional[str] = None              # 资产类型
    buy_multiplier: Optional[float] = None         # 建议补仓倍数 (1.0=正常, 2.0=双倍, 0=暂停)
    # QDII 美股期货参考
    nq_change_pct: Optional[float] = None          # 期货涨跌幅
    nq_data_source: Optional[str] = None           # 数据来源
    nq_futures_symbol: Optional[str] = None        # 期货代码 (NQ=F / ES=F)
    # 估值口径: eastmoney=官方表 / etf_proxy=ETF代理(基本准确) / holdings_weighted=持仓推算(可能不准) / last_nav=前日净值
    estimate_source: Optional[str] = None
    # 其他
    previous_change: Optional[float] = None        # 昨日估值涨跌幅
    recent_5_changes: list[tuple[str, float]] = field(default_factory=list) # 过去5交易日涨跌幅
    recent_5_estimates: list[tuple[str, float | None]] = field(default_factory=list) # 对应日期的盘中估值回溯


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
    return {"Bond": "债券型", "ETF_Feeder": "ETF联接", "QDII": "QDII"}.get(fund_type, fund_type)


def _format_change(change: float) -> str:
    return f"{change:+.2f}%"


def _get_change_color(change: Optional[float]) -> str:
    if change is None:
        return "#94a3b8"
    if change > 0:
        return "#c0392b"
    elif change < 0:
        return "#27ae60"
    return "#2c3e50"


# 估值口径徽标：官方估值引擎下线期间，标注盘中估值的来源与可靠性
# ETF代理=底层ETF实时价折算（基本准确）；持仓推算=前十大重仓加权估算（可能不准）；前日净值=无盘中数据
_SOURCE_BADGES = {
    "etf_proxy": ("ETF代理", "#E3F2FD", "#1565C0"),
    "holdings_weighted": ("持仓推算", "#FFF3E0", "#E65100"),
    "last_nav": ("前日净值", "#EEEEEE", "#616161"),
}


def _get_source_badge(source: Optional[str]) -> str:
    """估值口径徽标 HTML（官方估值 eastmoney 返回空串，不额外标注）"""
    if not source or source == "eastmoney":
        return ""
    text, bg, fg = _SOURCE_BADGES.get(source, ("", "", ""))
    if not text:
        return ""
    return (
        f'<span style="font-size:10px;background:{bg};color:{fg};'
        f'padding:1px 4px;border-radius:3px;margin-left:4px;white-space:nowrap;">{text}</span>'
    )


def _format_multiplier(multiplier: float | None) -> str:
    """格式化补仓倍数显示"""
    if multiplier is None:
        return "—"
    if multiplier == 0:
        return "暂停"
    if multiplier == 1.0:
        return "1x (正常)"
    return f"{multiplier:.1f}x"


def _get_zone_label(zone: str) -> str:
    """估值区间标签"""
    labels = {
        "低估区": "低估",
        "合理区": "合理",
        "偏高区": "偏高",
        "高估区": "高估",
        "极端低估": "极低",
        "极端高估": "极高",
        "机会区": "机会",
        "正常区": "正常",
        "熔断": "熔断",
    }
    return labels.get(zone, zone or "—")


def _get_zone_color(zone: str) -> str:
    colors = {
        "低估区": "#27ae60",
        "极端低估": "#1e8449",
        "合理区": "#2c3e50",
        "正常区": "#2c3e50",
        "偏高区": "#e67e22",
        "高估区": "#c0392b",
        "极端高估": "#922b21",
        "机会区": "#2980b9",
        "熔断": "#8e44ad",
    }
    return colors.get(zone, "#7f8c8d")


def _get_asset_label(asset_class: str) -> str:
    labels = {
        "GOLD_ETF": "黄金",
        "COMMODITY_CYCLE": "周期",
        "BOND_ENHANCED": "固收+",
        "BOND_PURE": "纯债",
        "US_EQUITY_INDEX": "美股",
        "DEFAULT_ETF": "ETF",
        "DEFAULT_BOND": "债基",
    }
    return labels.get(asset_class, "基金")






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
                        <th style="white-space: nowrap;">实时估值</th>
                        <th style="white-space: nowrap;">估值水平</th>
                        <th style="white-space: nowrap;">定投倍数</th>
                        <th style="text-align: right; white-space: nowrap;">操作建议</th>
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
                    <span class="glossary-term">多周期分位</span>
                    <span class="glossary-def">分别计算 60/250/1250 日区间内当前价格的排名。0%=历史最低，100%=历史最高。三个周期交叉验证可避免单一周期锚定偏误。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">多周期共识</span>
                    <span class="glossary-def">综合短/中/长期分位的加权判断（长期权重最高）。强低估=多周期一致看低，分歧=各周期信号不一致。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">60日均线偏离</span>
                    <span class="glossary-def">当前价格与过去60天平均价格的差距。偏离过大通常预示价格可能回归均值。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">定投倍数</span>
                    <span class="glossary-def">建议的定投金额倍数。1.0x=正常定投额，2.0x=双倍，0.5x=减半，0=暂停。策略根据分位、共识和资产特性综合计算。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">置信度</span>
                    <span class="glossary-def">策略对该建议的确定程度。越高代表指标信号越明确，熔断场景下会显著降低。</span>
                </div>
                <div class="glossary-item">
                    <span class="glossary-term">估值口径</span>
                    <span class="glossary-def">官方盘中估值暂不可用期间：ETF代理=按底层ETF实时价折算（基本准确）；持仓推算=按前十大重仓股加权估算（季报滞后、未披露部分按0计，可能不准，仅供参考）；前日净值=无盘中数据时展示上一确认日净值。</span>
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
        <div style="font-weight: 500; font-size: 13px;">{fund_name}</div>
        <div style="font-size: 11px; margin-top: 2px; color: #94a3b8;">{fund_code}</div>
    </td>
    <td style="color: {change_color}; font-weight: 500; white-space: nowrap;">{estimate_change}</td>
    <td style="color: {zone_color}; white-space: nowrap;">{zone_label}</td>
    <td style="font-weight: 600; color: #0369a1; white-space: nowrap;">{multiplier_display}</td>
    <td style="text-align: right; white-space: nowrap;">
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
                <div class="metric-label">实时估值</div>
                <div class="metric-value" style="color: {change_color};">{estimate_change}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">60日分位</div>
                <div class="metric-value">{percentile_60:.0f}%</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">250日分位</div>
                <div class="metric-value" style="color: {zone_color};">{percentile_250:.0f}%</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">1250日分位</div>
                <div class="metric-value">{percentile_1250:.0f}%</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">60日均线偏离</div>
                <div class="metric-value">{ma_deviation:+.2f}%</div>
            </div>
        </div>
        {recent_changes_html}
        <!-- Consensus -->
        <div style="background: #f1f5f9; border-radius: 4px; padding: 6px 12px; margin-bottom: 12px; font-size: 13px;">
            <span style="color: #64748b;">多周期共识:</span>
            <strong style="color: {consensus_color}; margin-left: 4px;">{consensus_label}</strong>
        </div>
        {nq_reference_html}
        
        {holdings_html}
        
        <!-- Decision -->
        <div class="conclusion-box">
            <div class="conclusion-header">
                <span class="conclusion-label">策略建议</span>
                <span class="conclusion-decision" style="color: {decision_color};">{decision}</span>
                <span style="font-size: 12px; color: #64748b; margin-left: 8px;">置信度: <strong>{strategy_confidence_pct}</strong></span>
                <span style="font-size: 12px; color: #64748b; margin-left: 8px;">倍数: <strong style="color: #0369a1;">{buy_multiplier_display}</strong></span>
            </div>
            <div class="conclusion-reason">{reasoning}</div>
        </div>
        
        <!-- Chart -->
        <div class="chart-container">
            <img src="cid:{chart_cid}" alt="走势图">
        </div>
        
        <!-- Warning -->
        {warning_html}
    </div>
</div>"""


# 取数失败总览行（summary 表 5 列：基金/估值/水平/倍数/操作，跨 4 列）
FAILED_SUMMARY_ROW_TEMPLATE = """<tr>
    <td>
        <div style="font-weight: 500; font-size: 13px;">{fund_name}</div>
        <div style="font-size: 11px; margin-top: 2px; color: #94a3b8;">{fund_code}</div>
    </td>
    <td colspan="4" style="color:#94a3b8; font-style:italic;">⚠️ 数据获取失败：{error}</td>
</tr>"""


# 取数失败详情卡片（无图表/指标/决策，仅标注失败原因）
FAILED_FUND_SECTION_TEMPLATE = """<div class="fund-card">
    <div class="fund-header">
        <div class="fund-name">{fund_name} <span class="fund-meta">({fund_code} · {fund_type})</span></div>
    </div>
    <div class="fund-body">
        <div class="warning-box">
            ⚠️ 数据获取失败，本次未生成决策建议。<br>
            <span style="font-size:12px;">原因：{error}</span>
        </div>
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
        # 取数失败的基金：总览标注失败，与 funds.json 对齐（不静默吞掉）
        if report.error:
            summary_rows.append(FAILED_SUMMARY_ROW_TEMPLATE.format(
                fund_name=report.fund_name,
                fund_code=report.fund_code,
                error=report.error
            ))
            continue
        # QDII有期货则显示期货值，否则显示失败
        if report.fund_type == "QDII":
            if report.nq_change_pct is not None:
                display_change = report.nq_change_pct
                display_label = _format_change(display_change)
            else:
                display_change = None
                display_label = "失败"
        else:
            # 估值降级链：官方/ETF代理/持仓推算 → 前日净值（徽标标注口径）
            if report.estimate_change is not None:
                display_change = report.estimate_change
                display_label = _format_change(display_change) + _get_source_badge(report.estimate_source)
            else:
                display_change = None
                display_label = "失败"
        
        summary_rows.append(SUMMARY_ROW_TEMPLATE.format(
            fund_name=report.fund_name,
            fund_code=report.fund_code,
            estimate_change=display_label,
            change_color=_get_change_color(display_change),
            zone_label=_get_zone_label(report.zone),
            zone_color=_get_zone_color(report.zone),
            multiplier_display=_format_multiplier(report.buy_multiplier),
            decision=report.decision,
            decision_color=_get_decision_color(report.decision),
            decision_bg=_get_decision_bg(report.decision)
        ))
    
    # Fund Sections
    fund_sections = []
    for i, report in enumerate(reports):
        # 取数失败的基金：渲染失败卡片，跳过正常指标/图表/决策渲染
        if report.error:
            fund_sections.append(FAILED_FUND_SECTION_TEMPLATE.format(
                fund_name=report.fund_name,
                fund_code=report.fund_code,
                fund_type=_get_fund_type_label(report.fund_type),
                error=report.error
            ))
            continue
        # Warning - format as numbered list
        warning_html = ""
        if report.warnings:
            if len(report.warnings) == 1:
                warning_html = f'<div class="warning-box">{report.warnings[0]}</div>'
            else:
                # Use circled numbers for multiple warnings
                nums = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
                warning_items = "".join(
                    f'<div>{nums[wi] if wi < len(nums) else str(wi+1)+"."} {w}</div>'
                    for wi, w in enumerate(report.warnings)
                )
                warning_html = f'<div class="warning-box">{warning_items}</div>'
                
        # Holdings rendering
        holdings_html = ""
        if report.top_gainers or report.top_losers:
            h_parts = []
            if report.top_gainers:
                h_parts.extend([f'<span style="color:#D32F2F">{g}</span>' for g in report.top_gainers])
            if report.top_losers:
                h_parts.extend([f'<span style="color:#388E3C">{l}</span>' for l in report.top_losers])
            if h_parts:
                holdings_str = "&nbsp; &middot; &nbsp;".join(h_parts)
                holdings_html = f'''
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px 14px; margin: 12px 0; border-radius: 6px;">
            <div style="font-size: 12px; color: #64748b; margin-bottom: 4px; font-weight: 500;">重点持仓表现:</div>
            <div style="font-size: 13px; font-weight: 500;">{holdings_str}</div>
        </div>'''
        
        # 期货参考 HTML (QDII 专用，动态显示 NQ=F 或 ES=F)
        futures_html = ""
        if report.nq_change_pct is not None:
            f_color = "#c0392b" if report.nq_change_pct > 0 else "#27ae60" if report.nq_change_pct < 0 else "#2c3e50"
            f_symbol = report.nq_futures_symbol or "NQ=F"
            source_label = f"📡 {f_symbol} 期货"
            fallback_note = ""
            futures_html = f'''
        <div style="background: #f0f9ff; border-left: 3px solid #0ea5e9; padding: 8px 12px; margin: 8px 0 12px 0; border-radius: 0 4px 4px 0; font-size: 12px;">
            <span style="color: #64748b;">{source_label}{fallback_note}:</span>
            <strong style="color: {f_color}; margin-left: 6px;">{report.nq_change_pct:+.2f}%</strong>
            <span style="color: #94a3b8; margin-left: 8px; font-size: 11px;">仅供盘中参考</span>
        </div>'''
        
        # QDII: 指标卡片
        if report.fund_type == "QDII":
            if report.nq_change_pct is not None:
                card_change = report.nq_change_pct
                card_label = _format_change(card_change)
            else:
                card_change = None
                card_label = "失败"
        else:
            if report.estimate_change is not None:
                card_change = report.estimate_change
                card_label = _format_change(card_change) + _get_source_badge(report.estimate_source)
            else:
                card_change = None
                card_label = "失败"
                
        # 过去5个交易日走势 + 估值回溯
        if report.recent_5_changes:
            recent_html_parts = []
            has_estimates = bool(report.recent_5_estimates) and len(report.recent_5_estimates) == len(report.recent_5_changes)
            
            for i, (date_str, change) in enumerate(report.recent_5_changes):
                color = _get_change_color(change)
                sign = "+" if change > 0 else ""
                val_str = f"{sign}{change:.2f}%"
                
                if has_estimates:
                    _, est_change = report.recent_5_estimates[i]
                    if est_change is not None:
                        est_color = _get_change_color(est_change)
                        est_sign = "+" if est_change > 0 else ""
                        est_val = f"{est_sign}{est_change:.2f}%"
                    else:
                        est_color = "#94a3b8"
                        est_val = "—"
                        
                    html = f'''
            <div class="metric-item" style="padding: 8px 10px;">
                <div class="metric-label" style="border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">{date_str}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="font-size: 11px; color: #64748b;">净值</span>
                    <span style="font-size: 13px; font-weight: 600; color: {color};">{val_str}</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; color: #64748b;">估值</span>
                    <span style="font-size: 13px; font-weight: 600; color: {est_color};">{est_val}</span>
                </div>
            </div>'''
                else:
                    html = f'''
            <div class="metric-item">
                <div class="metric-label">{date_str}</div>
                <div class="metric-value" style="color: {color}; font-size: 14px;">{val_str}</div>
            </div>'''
                recent_html_parts.append(html)
                
            title_text = "近5日净值与估值回溯" if has_estimates else "近5日确认净值"
            recent_changes_html = f"""
        <div style="font-size: 11px; color: #94a3b8; margin-bottom: 6px;">{title_text}</div>
        <div class="metrics-grid">
            {"".join(recent_html_parts)}
        </div>"""
        else:
            recent_changes_html = ""
        
        # Consensus display
        consensus_label = report.percentile_consensus or "—"
        consensus_colors = {
            "强低估": "#1e8449", "弱低估": "#27ae60",
            "分歧": "#7f8c8d",
            "弱高估": "#e67e22", "强高估": "#c0392b"
        }
        consensus_color = consensus_colors.get(consensus_label, "#2c3e50")
        
        fund_sections.append(FUND_SECTION_TEMPLATE.format(
            fund_name=report.fund_name,
            fund_code=report.fund_code,
            fund_type=_get_fund_type_label(report.fund_type),
            asset_label=_get_asset_label(report.asset_class),
            
            estimate_change=card_label,
            change_color=_get_change_color(card_change),
            
            percentile_60=report.percentile_60 or 0,
            percentile_250=report.percentile_250,
            percentile_1250=report.percentile_1250 or 0,
            zone_color=_get_zone_color(report.zone),
            ma_deviation=report.ma_deviation,
            recent_changes_html=recent_changes_html,
            
            consensus_label=consensus_label,
            consensus_color=consensus_color,
            
            decision=report.decision,
            decision_color=_get_decision_color(report.decision),
            reasoning=report.reasoning or "策略判断",
            
            strategy_confidence_pct=f"{report.strategy_confidence:.0%}" if report.strategy_confidence else "—",
            holdings_html=holdings_html,
            
            chart_cid=report.chart_cid or f"chart_{i}",
            warning_html=warning_html,
            buy_multiplier_display=_format_multiplier(report.buy_multiplier),
            nq_reference_html=futures_html
        ))
    
    return COMBINED_EMAIL_TEMPLATE.format(
        date_str=date_str,
        summary_rows="".join(summary_rows),
        fund_sections="".join(fund_sections)
    )


def generate_combined_email_subject(reports: list[FundReport], time_str: str = "") -> str:
    """生成邮件标题（取数失败的报告不参与决策统计，保持标题简洁）"""
    if not reports:
        return "[FundPilot] 今日无基金数据"

    today = datetime.now()
    date_short = f"{today.month:02d}.{today.day:02d}"

    # 仅统计成功生成决策的报告（失败报告计入邮件正文，但不进标题）
    valid_reports = [r for r in reports if not r.error]
    if not valid_reports:
        return f"[Fund Pilot] 投资决策 ({date_short}) - 数据全部获取失败"

    # 统计各决策数量
    decisions = {}
    for r in valid_reports:
        d = r.decision
        decisions[d] = decisions.get(d, 0) + 1

    # 生成决策摘要
    summary_parts = [f"{count}{d}" for d, count in decisions.items()]

    return f"[Fund Pilot] 投资决策 ({date_short}) - {'、'.join(summary_parts)}"
