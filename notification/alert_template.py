"""
FundPilot 盘中预警邮件模板
12:30 发送的上午数据快照，客观数据为主，不含决策建议
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AlertFundData:
    """预警基金数据"""
    fund_name: str
    fund_code: str
    fund_type: str
    estimate_change: Optional[float]       # 今日实时估值涨跌
    percentile_250: float        # 250日分位
    ma_deviation: float          # 均线偏离
    zone: str                    # 估值区间
    drawdown: float              # 60日回撤
    error: Optional[str] = None  # 取数失败原因（非空表示该基金本次数据缺失）
    holdings_txt: Optional[str] = None # 持仓概览 (前3大重仓+涨跌)
    percentile_60: Optional[float] = None   # 60日分位
    percentile_1250: Optional[float] = None  # 1250日分位
    volatility_60: Optional[float] = None   # 60日年化波动率
    percentile_consensus: Optional[str] = None  # 多周期共识
    # QDII 美股期货参考 (NQ=F / ES=F)
    nq_change_pct: Optional[float] = None
    nq_data_source: Optional[str] = None
    nq_market_status: Optional[str] = None
    nq_futures_symbol: Optional[str] = None
    # 估值口径: eastmoney=官方表 / etf_proxy=ETF代理(基本准确) / holdings_weighted=持仓推算(可能不准) / last_nav=前日净值
    estimate_source: Optional[str] = None


@dataclass
class MarketData:
    """市场数据"""
    shanghai_price: float
    shanghai_change: float
    hs300_price: float
    hs300_change: float


# 涨跌颜色
def _get_change_color(change: float) -> str:
    if change > 0:
        return "#D32F2F"  # 红涨
    elif change < 0:
        return "#388E3C"  # 绿跌
    return "#333333"


def _format_change(change: float) -> str:
    return f"{change:+.2f}%"


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


def _get_zone_style(zone: str) -> tuple[str, str]:
    """获取区间样式 (背景色, 文字色)"""
    styles = {
        "黄金坑": ("#FFEBEE", "#C62828"),
        "低估区": ("#E8F5E9", "#2E7D32"),
        "合理区": ("#F5F5F5", "#616161"),
        "偏高区": ("#FFF3E0", "#E65100"),
        "高估区": ("#FFEBEE", "#C62828"),
        "机会区": ("#E8F5E9", "#2E7D32"),
        "正常区": ("#F5F5F5", "#616161"),
        "熔断": ("#F3E5F5", "#7B1FA2"),
    }
    return styles.get(zone, ("#F5F5F5", "#616161"))


def _get_consensus_style(consensus: str) -> tuple[str, str]:
    """获取共识标签样式 (背景色, 文字色)"""
    styles = {
        "强低估": ("#E8F5E9", "#1B5E20"),
        "弱低估": ("#F1F8E9", "#33691E"),
        "分歧": ("#F5F5F5", "#616161"),
        "弱高估": ("#FFF3E0", "#E65100"),
        "强高估": ("#FFEBEE", "#B71C1C"),
    }
    return styles.get(consensus or "", ("#F5F5F5", "#616161"))


def _get_fund_type_short(fund_type: str) -> str:
    return {"Bond": "债", "ETF_Feeder": "ETF", "QDII": "QDII"}.get(fund_type, "")


# ============================================================
# 盘中预警邮件模板
# ============================================================

ALERT_EMAIL_TEMPLATE = """<!DOCTYPE html>
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
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background: #fff;
        }}
        
        /* 头部 - 与决策邮件风格统一 */
        .header {{
            background: #2c3e50;
            color: #ffffff;
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-brand {{
            font-size: 16px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        .header-date {{
            font-size: 12px;
            color: rgba(255,255,255,0.7);
        }}
        
        /* 市场概况 */
        .market-section {{
            padding: 20px 24px;
            background: #fafafa;
            border-bottom: 1px solid #eee;
        }}
        .section-title {{
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }}
        .market-grid {{
            display: table;
            width: 100%;
        }}
        .market-item {{
            display: table-cell;
            width: 50%;
            padding: 12px 16px;
            background: #fff;
            border-radius: 6px;
            text-align: center;
        }}
        .market-item:first-child {{
            margin-right: 8px;
        }}
        .market-name {{
            font-size: 12px;
            color: #888;
            margin-bottom: 4px;
        }}
        .market-price {{
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
        }}
        .market-change {{
            font-size: 13px;
            font-weight: 500;
            margin-top: 2px;
        }}
        
        /* 估值表格 */
        .data-section {{
            padding: 20px 24px;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .data-table th {{
            text-align: left;
            padding: 10px 8px;
            font-weight: 500;
            color: #888;
            border-bottom: 2px solid #eee;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .data-table td {{
            padding: 12px 8px;
            border-bottom: 1px solid #f0f0f0;
            vertical-align: middle;
        }}
        .data-table tr:last-child td {{
            border-bottom: none;
        }}
        .fund-name-cell {{
            font-weight: 500;
            color: #1a1a1a;
        }}
        .fund-type-badge {{
            display: inline-block;
            font-size: 10px;
            color: #888;
            background: #f0f0f0;
            padding: 1px 5px;
            border-radius: 3px;
            margin-left: 6px;
        }}
        .zone-badge {{
            display: inline-block;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 3px;
        }}
        .text-right {{
            text-align: right;
        }}
        .text-center {{
            text-align: center;
        }}
        
        /* 页脚 */
        .footer {{
            padding: 16px 24px;
            background: #fafafa;
            border-top: 1px solid #eee;
            text-align: center;
        }}
        .footer-note {{
            font-size: 12px;
            color: #666;
            margin-bottom: 8px;
        }}
        .footer-text {{
            font-size: 10px;
            color: #999;
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
        <div class="header">
            <div class="header-brand">FundPilot 盘中快报</div>
            <div class="header-date">{date_str}</div>
        </div>
        <div class="market-section">
            <div class="market-grid">
                <div class="market-item" style="margin-right: 8px;">
                    <div class="market-name">上证指数 ({shanghai_price})</div>
                    <div class="market-change" style="color: {shanghai_color};">{shanghai_change}</div>
                </div>
                <div class="market-item">
                    <div class="market-name">沪深300 ({hs300_price})</div>
                    <div class="market-change" style="color: {hs300_color};">{hs300_change}</div>
                </div>
            </div>
        </div>
        
        <div class="data-section">
            <div class="section-title">基金估值概况</div>
            <table class="data-table">
                <tr>
                    <th>基金</th>
                    <th class="text-right">实时估值</th>
                    <th class="text-center">250日分位</th>
                    <th class="text-center">共识</th>
                    <th class="text-center">区间</th>
                </tr>
                {fund_rows}
            </table>
        </div>
        
        <div class="data-section" style="padding-top: 0;">
            <div class="section-title">量化指标</div>
            <table class="data-table">
                <tr>
                    <th>基金</th>
                    <th class="text-right">60日均线偏离</th>
                    <th class="text-right">60日最大回撤</th>
                    <th class="text-right">60日波动率</th>
                </tr>
                {metrics_rows}
            </table>
        </div>

        <div class="data-section" style="padding-top: 0;">
            <div class="section-title">持仓动态 (Top 3)</div>
            <table class="data-table">
                <tr>
                    <th>基金</th>
                    <th>重仓股表现</th>
                </tr>
                {holdings_rows}
            </table>
        </div>
        
        <div class="glossary-section">
            <div class="glossary-title">术语说明</div>
            <table class="glossary-table">
                <tr>
                    <td class="term-cell">250日分位</td>
                    <td>当前价格在过去一年内的位置。0%表示一年最低，100%表示一年最高。类似于"历史打折力度"。</td>
                </tr>
                <tr>
                    <td class="term-cell">多周期共识</td>
                    <td>综合短/中/长期分位的加权判断（长期权重最高）。强低估=多周期一致看低，分歧=信号不一致。</td>
                </tr>
                <tr>
                    <td class="term-cell">均线偏离</td>
                    <td>当前价格相对于近 60 天平均价的偏离。正值=高于均线（走强），负值=低于均线（走弱）。</td>
                </tr>
                <tr>
                    <td class="term-cell">60日波动率</td>
                    <td>近 60 个交易日的年化波动率。数值越大，价格越动，定投的分散效果越明显。</td>
                </tr>
                <tr>
                    <td class="term-cell">估值区间</td>
                    <td>根据资产类型动态划分：黄金坑→低估→合理→偏高→高估。不同资产的分界线不同。</td>
                </tr>
                <tr>
                    <td class="term-cell">估值口径</td>
                    <td>官方盘中估值暂不可用期间：ETF代理=按底层ETF实时价折算（基本准确）；持仓推算=按前十大重仓股加权估算（季报滞后、未披露部分按0计，可能不准，仅供参考）；前日净值=无盘中数据时展示上一确认日净值。</td>
                </tr>
            </table>
        </div>
        
        <div class="footer">
            <div class="footer-note">完整决策报告将于 14:45 发送</div>
            <div class="footer-text">FundPilot · 量化定投决策系统</div>
        </div>
    </div>
</body>
</html>"""


FUND_ROW_TEMPLATE = """<tr>
    <td class="fund-name-cell">{fund_name}<span class="fund-type-badge">{fund_type}</span></td>
    <td class="text-right" style="color: {change_color}; font-weight: 500;">{estimate_change}</td>
    <td class="text-center" style="font-weight: 500;">{p250:.0f}%</td>
    <td class="text-center"><span class="zone-badge" style="background: {consensus_bg}; color: {consensus_color};">{consensus}</span></td>
    <td class="text-center"><span class="zone-badge" style="background: {zone_bg}; color: {zone_color};">{zone}</span></td>
</tr>"""


METRICS_ROW_TEMPLATE = """<tr>
    <td class="fund-name-cell">{fund_name_short}</td>
    <td class="text-right" style="color: {deviation_color};">{ma_deviation}</td>
    <td class="text-right">{drawdown}</td>
    <td class="text-right">{volatility}</td>
</tr>"""


HOLDINGS_ROW_TEMPLATE = """<tr>
    <td class="fund-name-cell">{fund_name_short}</td>
    <td style="font-size: 12px; color: #666; line-height: 1.4;">{holdings_txt}</td>
</tr>"""


# 取数失败行：仅基金名 + 跨列失败提示（主估值表5列，跨4列）
ALERT_FAILED_ROW_TEMPLATE = """<tr>
    <td class="fund-name-cell">{fund_name}<span class="fund-type-badge">{fund_type}</span></td>
    <td colspan="4" style="color:#94a3b8; font-style:italic;">⚠️ 数据获取失败：{error}</td>
</tr>"""


def generate_alert_email_html(
    funds: list[AlertFundData],
    market: Optional[MarketData],
    time_str: str
) -> str:
    """
    生成盘中预警邮件 HTML
    
    Args:
        funds: 基金数据列表
        market: 市场数据
        time_str: 时间字符串
    
    Returns:
        HTML 字符串
    """
    today = datetime.now()
    date_str = f"{today.month}月{today.day}日 {time_str}"
    
    # 市场数据
    if market:
        shanghai_price = f"{market.shanghai_price:,.2f}"
        shanghai_change = _format_change(market.shanghai_change)
        shanghai_color = _get_change_color(market.shanghai_change)
        hs300_price = f"{market.hs300_price:,.2f}"
        hs300_change = _format_change(market.hs300_change)
        hs300_color = _get_change_color(market.hs300_change)
    else:
        shanghai_price = "--"
        shanghai_change = "--"
        shanghai_color = "#888"
        hs300_price = "--"
        hs300_change = "--"
        hs300_color = "#888"
    
    # 基金估值行
    fund_rows = []
    for fund in funds:
        # 失败基金：仅在估值表标注失败原因（与 funds.json 对齐，不静默吞掉）
        if fund.error:
            name = fund.fund_name
            if len(name) > 10:
                name = name[:9] + "…"
            fund_rows.append(ALERT_FAILED_ROW_TEMPLATE.format(
                fund_name=name,
                fund_type=_get_fund_type_short(fund.fund_type),
                error=fund.error
            ))
            continue

        zone_bg, zone_color = _get_zone_style(fund.zone)
        
        # 基金名称截断
        name = fund.fund_name
        if len(name) > 10:
            name = name[:9] + "…"
        
        # QDII有期货则显示期货值，否则显示失败
        if fund.fund_type == "QDII":
            if fund.nq_change_pct is not None:
                display_change = fund.nq_change_pct
                display_label = _format_change(display_change)
            else:
                display_change = None
                display_label = '<span style="color:#94a3b8">失败</span>'
        else:
            # 估值降级链：官方/ETF代理/持仓推算 → 前日净值（徽标标注口径）
            if fund.estimate_change is not None:
                display_change = fund.estimate_change
                display_label = _format_change(display_change) + _get_source_badge(fund.estimate_source)
            else:
                display_change = None
                display_label = '<span style="color:#94a3b8">失败</span>'
        
        fund_rows.append(FUND_ROW_TEMPLATE.format(
            fund_name=name,
            fund_type=_get_fund_type_short(fund.fund_type),
            estimate_change=display_label,
            change_color=_get_change_color(display_change),
            p250=fund.percentile_250,
            consensus=fund.percentile_consensus or "—",
            consensus_bg=_get_consensus_style(fund.percentile_consensus or "")[0],
            consensus_color=_get_consensus_style(fund.percentile_consensus or "")[1],
            zone=fund.zone,
            zone_bg=zone_bg,
            zone_color=zone_color
        ))
    
    # 量化指标行
    metrics_rows = []
    holdings_rows = []
    
    for fund in funds:
        # 失败基金无指标/持仓数据，跳过这两张表（避免渲染误导性的 0 值）
        if fund.error:
            continue

        name = fund.fund_name
        if len(name) > 8:
            name = name[:7] + "…"

        metrics_rows.append(METRICS_ROW_TEMPLATE.format(
            fund_name_short=name,
            ma_deviation=_format_change(fund.ma_deviation),
            deviation_color=_get_change_color(fund.ma_deviation),
            drawdown=f"{fund.drawdown:.2f}%",
            volatility=f"{fund.volatility_60:.1f}%" if fund.volatility_60 else "—"
        ))
        
        # 仅当有持仓信息时显示
        if fund.holdings_txt:
            holdings_rows.append(HOLDINGS_ROW_TEMPLATE.format(
                fund_name_short=name,
                holdings_txt=fund.holdings_txt
            ))
    
    return ALERT_EMAIL_TEMPLATE.format(
        date_str=date_str,
        fund_count=len(funds),
        shanghai_price=shanghai_price,
        shanghai_change=shanghai_change,
        shanghai_color=shanghai_color,
        hs300_price=hs300_price,
        hs300_change=hs300_change,
        hs300_color=hs300_color,
        fund_rows="\n".join(fund_rows),
        metrics_rows="\n".join(metrics_rows),
        holdings_rows="\n".join(holdings_rows)
    )


def generate_alert_email_subject() -> str:
    """生成盘中预警邮件标题"""
    today = datetime.now()
    date_str = today.strftime("%y.%m.%d")
    return f"[Fund Pilot] 盘中预警 ({date_str})"
