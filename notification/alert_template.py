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
    estimate_change: float       # 今日估值涨跌
    percentile_250: float        # 250日分位
    ma_deviation: float          # 均线偏离
    zone: str                    # 估值区间
    drawdown: float              # 60日回撤


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
    }
    return styles.get(zone, ("#F5F5F5", "#616161"))


def _get_fund_type_short(fund_type: str) -> str:
    return {"Bond": "债", "ETF_Feeder": "ETF"}.get(fund_type, "")


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
        
        /* 头部 */
        .header {{
            padding: 28px 24px 20px;
            border-bottom: 1px solid #eee;
        }}
        .header-badge {{
            display: inline-block;
            background: #FFF3E0;
            color: #E65100;
            font-size: 11px;
            font-weight: 500;
            padding: 3px 8px;
            border-radius: 3px;
            margin-bottom: 8px;
        }}
        .header-title {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 4px;
        }}
        .header-meta {{
            font-size: 12px;
            color: #888;
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
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="header-badge">盘中预警</div>
            <div class="header-title">上午数据快照</div>
            <div class="header-meta">{date_str} · {fund_count} 只基金</div>
        </div>
        
        <div class="market-section">
            <div class="section-title">市场概况</div>
            <div class="market-grid">
                <div class="market-item" style="margin-right: 8px;">
                    <div class="market-name">上证指数</div>
                    <div class="market-price">{shanghai_price}</div>
                    <div class="market-change" style="color: {shanghai_color};">{shanghai_change}</div>
                </div>
                <div class="market-item">
                    <div class="market-name">沪深300</div>
                    <div class="market-price">{hs300_price}</div>
                    <div class="market-change" style="color: {hs300_color};">{hs300_change}</div>
                </div>
            </div>
        </div>
        
        <div class="data-section">
            <div class="section-title">基金实时估值</div>
            <table class="data-table">
                <tr>
                    <th>基金</th>
                    <th class="text-right">今日估值</th>
                    <th class="text-center">分位</th>
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
                    <th class="text-right">均线偏离</th>
                    <th class="text-right">60日回撤</th>
                </tr>
                {metrics_rows}
            </table>
        </div>
        
        <div class="footer">
            <div class="footer-note">📊 完整决策报告将于 14:45 发送</div>
            <div class="footer-text">FundPilot · 量化定投决策系统</div>
        </div>
    </div>
</body>
</html>"""


FUND_ROW_TEMPLATE = """<tr>
    <td class="fund-name-cell">{fund_name}<span class="fund-type-badge">{fund_type}</span></td>
    <td class="text-right" style="color: {change_color}; font-weight: 500;">{estimate_change}</td>
    <td class="text-center" style="font-weight: 500;">{percentile}</td>
    <td class="text-center"><span class="zone-badge" style="background: {zone_bg}; color: {zone_color};">{zone}</span></td>
</tr>"""


METRICS_ROW_TEMPLATE = """<tr>
    <td class="fund-name-cell">{fund_name_short}</td>
    <td class="text-right" style="color: {deviation_color};">{ma_deviation}</td>
    <td class="text-right">{drawdown}</td>
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
        zone_bg, zone_color = _get_zone_style(fund.zone)
        
        # 基金名称截断
        name = fund.fund_name
        if len(name) > 10:
            name = name[:9] + "…"
        
        fund_rows.append(FUND_ROW_TEMPLATE.format(
            fund_name=name,
            fund_type=_get_fund_type_short(fund.fund_type),
            estimate_change=_format_change(fund.estimate_change),
            change_color=_get_change_color(fund.estimate_change),
            percentile=f"{fund.percentile_250:.0f}%",
            zone=fund.zone,
            zone_bg=zone_bg,
            zone_color=zone_color
        ))
    
    # 量化指标行
    metrics_rows = []
    for fund in funds:
        name = fund.fund_name
        if len(name) > 8:
            name = name[:7] + "…"
        
        metrics_rows.append(METRICS_ROW_TEMPLATE.format(
            fund_name_short=name,
            ma_deviation=_format_change(fund.ma_deviation),
            deviation_color=_get_change_color(fund.ma_deviation),
            drawdown=f"{fund.drawdown:.2f}%"
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
        metrics_rows="\n".join(metrics_rows)
    )


def generate_alert_email_subject() -> str:
    """生成盘中预警邮件标题"""
    today = datetime.now()
    date_str = today.strftime("%y.%m.%d")
    return f"[Fund Pilot] 盘中预警 ({date_str})"
