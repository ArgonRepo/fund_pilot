"""
FundPilot 邮件模板模块
专业、简洁的投资决策报告
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


def _get_asset_class_label(asset_class: str) -> str:
    """资产类型标签"""
    labels = {
        "GOLD_ETF": "黄金避险",
        "COMMODITY_CYCLE": "周期商品",
        "BOND_ENHANCED": "固收+",
        "BOND_PURE": "纯债",
        "DEFAULT_ETF": "ETF",
        "DEFAULT_BOND": "债基",
    }
    return labels.get(asset_class, asset_class or "N/A")


# ============================================================
# 主邮件模板 - 简洁专业风格
# ============================================================

# ============================================================
# 主邮件模板 - 现代极简风格 v3.0
# ============================================================

# ============================================================
# 主邮件模板 - v4.0 专业分析师周报风格 (全中文/结构化)
# ============================================================

COMBINED_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* ----------------------------------------------------
           全局样式重置
           ---------------------------------------------------- */
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: "PingFang SC", "Microsoft YaHei", -apple-system, sans-serif;
            background-color: #f0f2f5;
            color: #1f2329;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        
        /* ----------------------------------------------------
           容器与框架
           ---------------------------------------------------- */
        .email-wrapper {{
            max-width: 640px;
            margin: 0 auto;
            background: #ffffff;
            /* 移除多余边框，使用整洁的阴影增强质感 */
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }}
        
        /* ----------------------------------------------------
           顶部品牌栏
           ---------------------------------------------------- */
        .header-bar {{
            background: #1a365d; /* 专业深蓝 */
            padding: 24px 32px;
            color: #ffffff;
            display: flex;
            justify-content: space-between;
            align-items: baseline;
        }}
        .brand-logo {{
            font-size: 20px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .report-meta {{
            font-size: 13px;
            opacity: 0.8;
            font-weight: 500;
        }}
        
        /* ----------------------------------------------------
           决策总览表 (Executive Summary)
           ---------------------------------------------------- */
        .summary-section {{
            padding: 24px 32px;
            background: #fff;
            border-bottom: 8px solid #f0f2f5; /* 分隔条 */
        }}
        .section-title {{
            font-size: 15px;
            font-weight: 700;
            color: #1a365d;
            border-left: 4px solid #c92a2a; /* 醒目红标 */
            padding-left: 10px;
            margin-bottom: 16px;
            text-transform: uppercase;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .summary-table th {{
            text-align: left;
            padding: 8px 4px;
            color: #86909c;
            font-weight: 500;
            border-bottom: 2px solid #f0f2f5;
        }}
        .summary-table td {{
            padding: 12px 4px;
            border-bottom: 1px solid #f7f8fa;
            vertical-align: middle;
        }}
        .sum-code {{ color: #86909c; font-family: monospace; }}
        .sum-name {{ font-weight: 600; color: #1f2329; }}
        .sum-decision-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        /* ----------------------------------------------------
           基金详细分析卡片 (Cohesive Report Block)
           ---------------------------------------------------- */
        .fund-report-block {{
            background: #fff;
            margin-bottom: 8px; /* 块间分隔 */
            border-bottom: 8px solid #f0f2f5;
            padding: 24px 32px;
        }}
        
        /* 标题区 */
        .fund-header-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
        }}
        .fh-main {{
            display: flex;
            flex-direction: column;
        }}
        .fh-name {{
            font-size: 18px;
            font-weight: 700;
            color: #1f2329;
            margin-bottom: 4px;
        }}
        .fh-meta {{
            font-size: 12px;
            color: #86909c;
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        .fh-tag {{
            background: #f7f8fa;
            padding: 1px 6px;
            border-radius: 3px;
            color: #4e5969;
        }}
        
        /* 重点数据指标栏 */
        .key-metrics-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            background: #f8f9fb;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 24px;
        }}
        .km-item {{ text-align: center; }}
        .km-label {{ font-size: 12px; color: #86909c; margin-bottom: 4px; }}
        .km-value {{ font-size: 16px; font-weight: 600; font-family: -apple-system, monospace; }}
        .km-sub {{ font-size: 12px; margin-left: 2px; font-weight: normal; color: #86909c; }}
        
        /* 双轨分析面板 (一体化设计) */
        .analysis-container {{
            border: 1px solid #e5e6eb;
            border-radius: 6px;
            margin-bottom: 24px;
            overflow: hidden;
        }}
        
        /* 1. 量化结论行 */
        .quant-row {{
            background: #fcfdfe;
            padding: 16px 20px;
            border-bottom: 1px solid #e5e6eb;
            display: flex;
            gap: 16px;
        }}
        .qr-label {{ 
            width: 80px; 
            font-size: 13px; 
            font-weight: 700; 
            color: #1a365d; 
            flex-shrink: 0;
            padding-top: 2px;
        }}
        .qr-content {{ font-size: 13px; color: #4e5969; line-height: 1.5; }}
        .qr-highlight {{ color: #1f2329; font-weight: 500; }}
        
        /* 2. AI 深度分析区 */
        .ai-section {{
            padding: 20px;
            background: #fff;
        }}
        .ai-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .ai-title {{ 
            font-size: 13px; 
            font-weight: 700; 
            color: #722ed1; /* 紫色系代表 AI */ 
            display: flex; 
            align-items: center; 
            gap: 6px; 
        }}
        .ai-text {{
            font-size: 14px;
            color: #1f2329;
            line-height: 1.7;
            text-align: justify;
            white-space: pre-wrap; /* 后端可以传换行符 */
        }}
        
        /* 3. 最终决策栏 (整合在分析框底部) */
        .final-decision-bar {{
            background: #1a365d;
            color: #fff;
            padding: 16px 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .fd-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .fd-left {{ font-weight: 700; font-size: 16px; display: flex; align-items: center; gap: 8px; }}
        .fd-right {{ font-size: 12px; opacity: 0.9; }}
        
        .fd-reason-box {{
            background: rgba(255, 255, 255, 0.1);
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 13px;
            line-height: 1.5;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }}
        .fd-tag {{
            background: rgba(255, 255, 255, 0.2);
            padding: 1px 6px;
            border-radius: 3px;
            font-size: 11px;
            white-space: nowrap;
        }}
        
        /* 风险与持仓 */
        .risk-alert {{
            margin-top: 16px;
            padding: 12px 16px;
            background: #fff7e6;
            border: 1px solid #ffd591;
            border-radius: 4px;
            color: #d46b08;
            font-size: 12px;
            display: flex;
            gap: 8px;
        }}
        
        .holdings-table {{
            width: 100%;
            margin-top: 20px;
            font-size: 12px;
            border-top: 1px dashed #e5e6eb;
            padding-top: 16px;
        }}
        .ht-row {{ display: flex; gap: 12px; color: #4e5969; margin-bottom: 4px; }}
        .ht-label {{ font-weight: 600; min-width: 60px; }}
        
        /* 图表容器 */
        .chart-box {{
            margin-top: 24px;
            border: 1px solid #e5e6eb;
            border-radius: 4px;
            padding: 4px;
        }}
        .chart-box img {{ display: block; width: 100%; height: auto; }}
        
        /* ----------------------------------------------------
           底部说明区 (Glossary)
           ---------------------------------------------------- */
        .footer-section {{
            padding: 40px 32px;
            background: #f7f8fa;
            color: #86909c;
            font-size: 12px;
        }}
        .glossary-title {{
            font-size: 13px;
            font-weight: 700;
            color: #4e5969;
            margin-bottom: 12px;
            border-bottom: 1px solid #e5e6eb;
            padding-bottom: 8px;
        }}
        .glossary-list {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
        }}
        .gl-item {{ display: flex; gap: 8px; line-height: 1.5; }}
        .gl-term {{ font-weight: 600; color: #4e5969; white-space: nowrap; }}
        
        /* ----------------------------------------------------
           Utility Colors
           ---------------------------------------------------- */
        .text-red {{ color: #cf1322; }}
        .text-green {{ color: #389e0d; }}
        .text-gray {{ color: #86909c; }}
        .bg-red-light {{ background: #fff1f0; color: #cf1322; }}
        .bg-green-light {{ background: #f6ffed; color: #389e0d; }}
        .bg-blue-light {{ background: #e6f7ff; color: #096dd9; }}
        .bg-gray-light {{ background: #f2f3f5; color: #4e5969; }}
        
    </style>
</head>
<body>
    <div class="email-wrapper">
        <!-- 1. 顶部栏 -->
        <div class="header-bar">
            <div class="brand-logo">FundPilot 智能投顾</div>
            <div class="report-meta">{date_str}</div>
        </div>
        
        <!-- 2. 决策总览 -->
        <div class="summary-section">
            <div class="section-title">今日投资决策总览</div>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th width="20%">代码</th>
                        <th width="35%">基金名称</th>
                        <th width="25%">今日变动</th>
                        <th width="20%" style="text-align:right">操作信号</th>
                    </tr>
                </thead>
                <tbody>
                    {summary_rows}
                </tbody>
            </table>
        </div>
        
        <!-- 3. 详细报告区块 (循环生成) -->
        {fund_sections}
        
        <!-- 4. 底部说明 -->
        <div class="footer-section">
            <div class="glossary-title">指标说明与风险提示</div>
            <div class="glossary-list">
                <div class="gl-item">
                    <span class="gl-term">估值分位</span>
                    <span>反映当前价格在历史（过去250/500天）中的相对位置，0%为历史最低，100%为最高。>80%通常预示高估风险。</span>
                </div>
                <div class="gl-item">
                    <span class="gl-term">智能合成</span>
                    <span>结合「量化规则」与「AI专家」的双重验证机制。当两者分歧时，系统会自动采用保守策略以控制风险。</span>
                </div>
                <div class="gl-item">
                    <span class="gl-term">趋势共识</span>
                    <span>短期（60日）趋势与长期（250日）估值方向的一致性判断。</span>
                </div>
            </div>
            <div style="margin-top: 24px; text-align: center; opacity: 0.6;">
                本报告由 FundPilot 量化系统自动生成，仅供参考，不构成投资建议。<br>
                投资有风险，入市需谨慎。
            </div>
        </div>
    </div>
</body>
</html>"""


SUMMARY_ROW_TEMPLATE = """<tr>
    <td class="sum-code">{fund_code}</td>
    <td class="sum-name">{fund_name}</td>
    <td style="color: {change_color}">{estimate_change}</td>
    <td style="text-align: right;">
        <span class="sum-decision-tag" style="background: {decision_bg}; color: {decision_color};">
            {decision}
        </span>
    </td>
</tr>"""


FUND_SECTION_TEMPLATE = """<div class="fund-report-block">
    <!-- 头部 -->
    <div class="fund-header-row">
        <div class="fh-main">
            <div class="fh-name">{fund_name}</div>
            <div class="fh-meta">
                <span class="fh-tag">{asset_class_cn}</span>
                <span>代码：{fund_code}</span>
                <span>类型：{fund_type}</span>
            </div>
        </div>
        <!-- 这里的留空可以放Icon或者留给布局呼吸感 -->
    </div>
    
    <!-- 核心指标 -->
    <div class="key-metrics-grid">
        <div class="km-item">
            <div class="km-label">今日涨跌</div>
            <div class="km-value" style="color: {change_color}">{estimate_change}</div>
        </div>
        <div class="km-item">
            <div class="km-label">估值分位 <span class="km-sub">(250日)</span></div>
            <div class="km-value" style="color: {percentile_color}">{percentile_250:.0f}<span style="font-size:12px">%</span></div>
            <div class="km-sub">{zone}</div>
        </div>
        <div class="km-item">
            <div class="km-label">趋势信号</div>
            <div class="km-value" style="color: {trend_color}">{trend}</div>
        </div>
    </div>
    
    <!-- 双轨分析容器 -->
    <div class="analysis-container">
        <!-- 量化维度 -->
        <div class="quant-row">
            <div class="qr-label">量化模型</div>
            <div class="qr-content">
                <div class="qr-highlight">信号：{strategy_decision} (置信度 {strategy_confidence_pct})</div>
                <div>{strategy_reasoning}</div>
            </div>
        </div>
        
        <!-- AI 维度 -->
        <div class="ai-section">
            <div class="ai-header">
                <div class="ai-title">🧠 深度分析顾问</div>
                <div style="font-size: 12px; color: #86909c;">DeepSeek V3 (置信度 {ai_confidence})</div>
            </div>
            <div class="ai-text">{ai_reasoning}</div>
        </div>
        
        <!-- 最终决策条 (v4.1) -->
        <div class="final-decision-bar">
            <div class="fd-header">
                <div class="fd-left">
                    <span>最终决策：{decision}</span>
                </div>
                <div class="fd-right">
                    综合置信度 {final_confidence}
                </div>
            </div>
            <div class="fd-reason-box">
                <div class="fd-tag">{synthesis_method}</div>
                <div>{reasoning}</div>
            </div>
        </div>
    </div>
    
    <!-- 额外信息 -->
    {risk_warning_html}
    {holdings_html}
    
    <!-- 图表 -->
    <div class="chart-box">
        <img src="cid:{chart_cid}" alt="走势分析图">
    </div>
</div>"""

HOLDINGS_LIST_TEMPLATE = """<div class="holdings-table">
    <div class="ht-row">
        <span class="ht-label">持仓异动：</span>
        <span>{summary}</span>
    </div>
    {details}
</div>"""


def _get_asset_class_cn(asset_class: str) -> str:
    """资产类型中文化"""
    mapping = {
        "BOND_PURE": "纯债",
        "BOND_ENHANCED": "固收+",
        "STOCK_INDEX": "指数宽基",
        "STOCK_ACTIVE": "主动权益",
        "GOLD_ETF": "黄金商品",
        "COMMODITY_CYCLE": "周期商品",
        "REITS": "Reits"
    }
    return mapping.get(asset_class, "其他基金")


def _get_percentile_color(percentile: float) -> str:
    """分位值颜色映射 (低估绿/高估红)"""
    if percentile < 20: return "#389e0d" # Green
    if percentile > 80: return "#cf1322" # Red
    return "#1f2329"

def _map_confidence_cn(conf_str: str) -> str:
    """Confidence Mapping High->90%"""
    if not conf_str: return "-"
    if "高" in conf_str: return "90%"
    if "中" in conf_str: return "70%"
    if "低" in conf_str: return "40%"
    return conf_str

def generate_combined_email_html(
    reports: list[FundReport],
    time_str: str,
    market_summary: str = ""
) -> str:
    """生成 v4.0 专业版邮件"""
    today = datetime.now()
    date_str = f"{today.year}年{today.month}月{today.day}日 (周{today.strftime('%w')})"
    
    # 1. 生成摘要行 (Table Rows)
    summary_rows = []
    for report in reports:
        summary_rows.append(SUMMARY_ROW_TEMPLATE.format(
            fund_code=report.fund_code, # Full code
            fund_name=report.fund_name,
            estimate_change=_format_change(report.estimate_change),
            change_color=_get_change_color(report.estimate_change),
            decision=report.decision,
            decision_color=_get_decision_color(report.decision),
            decision_bg=_get_decision_bg(report.decision)
        ))
        
    # 2. 生成详细报告块
    fund_sections = []
    for i, report in enumerate(reports):
        # 处理持仓信息
        holdings_html = ""
        if report.holdings_summary:
            details_str = ""
            if report.top_gainers or report.top_losers:
                details_str = '<div class="ht-row"><span class="ht-label">详细涨跌：</span><span>'
                parts = []
                if report.top_gainers: parts.append(f"领涨[{', '.join(report.top_gainers[:2])}]")
                if report.top_losers: parts.append(f"领跌[{', '.join(report.top_losers[:2])}]")
                details_str += "，".join(parts) + "</span></div>"
                
            holdings_html = HOLDINGS_LIST_TEMPLATE.format(
                summary=report.holdings_summary,
                details=details_str
            )
            
        # 风险提示
        risk_warning_html = ""
        if report.warnings:
            w_text = "；".join(report.warnings)
            risk_warning_html = f"""<div class="risk-alert">
                <strong>⚠️ 风险预警：</strong>{w_text}
            </div>"""
            
        # 数据准备
        quant_decision = report.strategy_decision or report.decision
        quant_conf = f"{report.strategy_confidence:.0%}" if report.strategy_confidence else "计算中"
        
        # AI 理由换行处理
        ai_reasoning = (report.ai_reasoning or "暂无分析").replace("\n", "\n") # CSS pre-wrap handles this
        
        final_conf_pct = _map_confidence_cn(report.final_confidence or "中")
        
        fund_sections.append(FUND_SECTION_TEMPLATE.format(
            fund_name=report.fund_name,
            fund_code=report.fund_code,
            fund_type=_get_fund_type_label(report.fund_type),
            asset_class_cn=_get_asset_class_cn(report.asset_class),
            
            estimate_change=_format_change(report.estimate_change),
            change_color=_get_change_color(report.estimate_change),
            
            percentile_250=report.percentile_250,
            percentile_color=_get_percentile_color(report.percentile_250),
            zone=report.zone,
            
            trend=report.trend_direction or "无信号",
            trend_color=_get_trend_color(report.trend_direction or ""),
            
            strategy_decision=quant_decision,
            strategy_confidence_pct=quant_conf,
            strategy_reasoning=report.strategy_reasoning or "模型运行正常",
            
            ai_confidence=_map_confidence_cn(report.ai_confidence or "中"),
            ai_reasoning=ai_reasoning,
            
            decision=report.decision,
            synthesis_method=report.synthesis_method or "默认策略",
            final_confidence=final_conf_pct,
            reasoning=report.reasoning or "无合成理由",
            
            risk_warning_html=risk_warning_html,
            holdings_html=holdings_html,
            chart_cid=report.chart_cid or f"chart_{i}"
        ))

    return COMBINED_EMAIL_TEMPLATE.format(
        date_str=date_str,
        summary_rows="".join(summary_rows),
        fund_sections="".join(fund_sections)
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
