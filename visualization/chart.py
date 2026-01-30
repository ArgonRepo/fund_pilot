"""
FundPilot-AI 可视化模块
生成 "10+1" 趋势图
"""

import io
from datetime import date
from typing import Optional

import matplotlib
matplotlib.use('Agg')  # 无窗口模式

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

from core.logger import get_logger

logger = get_logger("chart")

# 尝试使用中文字体
try:
    # macOS
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC']
except Exception:
    pass

plt.rcParams['axes.unicode_minus'] = False

# 颜色配置
COLOR_UP = '#e74c3c'       # 涨 - 红色
COLOR_DOWN = '#27ae60'     # 跌 - 绿色
COLOR_MA60 = '#3498db'     # MA60 - 蓝色
COLOR_GRID = '#ecf0f1'     # 网格线


def generate_trend_chart(
    fund_name: str,
    history_10d: list[tuple[date, float]],
    estimate_today: float,
    ma_60: float,
    estimate_change: Optional[float] = None
) -> bytes:
    """
    生成 "10+1" 趋势图
    
    Args:
        fund_name: 基金名称
        history_10d: 前 10 个交易日净值 [(日期, 净值), ...]（按日期升序）
        estimate_today: 今日预估净值
        ma_60: 60日均线
        estimate_change: 预估涨跌幅
    
    Returns:
        PNG 图片字节流
    """
    if not history_10d:
        logger.warning("没有历史数据，无法生成图表")
        return b""
    
    # 准备数据
    dates = [d for d, _ in history_10d]
    navs = [nav for _, nav in history_10d]
    
    # 今日数据
    today = date.today()
    last_nav = navs[-1]
    
    # 判断涨跌颜色
    if estimate_today >= last_nav:
        today_color = COLOR_UP
        line_style = '--'
    else:
        today_color = COLOR_DOWN
        line_style = '--'
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
    
    # 绘制历史净值（实线）
    ax.plot(dates, navs, 
            color='#2c3e50', 
            linewidth=2, 
            marker='o', 
            markersize=5,
            label='历史净值')
    
    # 绘制今日预估（虚线）
    ax.plot([dates[-1], today], [last_nav, estimate_today],
            color=today_color,
            linewidth=2,
            linestyle=line_style,
            marker='o',
            markersize=8,
            label=f'今日预估 ({estimate_change:+.2f}%)' if estimate_change else '今日预估')
    
    # 绘制 MA60 参考线
    ax.axhline(y=ma_60, 
               color=COLOR_MA60, 
               linestyle='-.', 
               linewidth=1.5,
               label=f'MA60 ({ma_60:.4f})')
    
    # 标注今日预估值
    ax.annotate(f'{estimate_today:.4f}',
                xy=(today, estimate_today),
                xytext=(10, 10),
                textcoords='offset points',
                fontsize=10,
                color=today_color,
                fontweight='bold')
    
    # 设置标题
    title = f'{fund_name} 走势图'
    if estimate_change is not None:
        title += f' | 今日{estimate_change:+.2f}%'
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    
    # 设置坐标轴
    ax.set_xlabel('日期', fontsize=10)
    ax.set_ylabel('净值', fontsize=10)
    
    # 日期格式
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45)
    
    # 网格
    ax.grid(True, linestyle='--', alpha=0.3, color=COLOR_GRID)
    ax.set_axisbelow(True)
    
    # 图例
    ax.legend(loc='upper left', fontsize=9)
    
    # Y 轴范围留白
    all_values = navs + [estimate_today, ma_60]
    y_min, y_max = min(all_values), max(all_values)
    margin = (y_max - y_min) * 0.1
    ax.set_ylim(y_min - margin, y_max + margin)
    
    # 调整布局
    plt.tight_layout()
    
    # 输出为字节流
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    buf.seek(0)
    
    plt.close(fig)
    
    logger.info(f"生成趋势图: {fund_name}")
    return buf.getvalue()


def generate_simple_chart(
    fund_name: str,
    navs: list[float],
    current: float,
    ma_60: float
) -> bytes:
    """
    生成简化趋势图（仅数值，无日期）
    
    Args:
        fund_name: 基金名称
        navs: 历史净值列表
        current: 当前/预估净值
        ma_60: 60日均线
    
    Returns:
        PNG 图片字节流
    """
    # 创建图表
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    
    # X 轴为序号
    x = list(range(len(navs)))
    x_current = len(navs)
    
    # 绘制历史
    ax.plot(x, navs, color='#2c3e50', linewidth=2, marker='o', markersize=4)
    
    # 绘制当前
    color = COLOR_UP if current >= navs[-1] else COLOR_DOWN
    ax.plot([x[-1], x_current], [navs[-1], current], 
            color=color, linewidth=2, linestyle='--', marker='o', markersize=6)
    
    # MA60
    ax.axhline(y=ma_60, color=COLOR_MA60, linestyle='-.', linewidth=1.5)
    
    ax.set_title(f'{fund_name}', fontsize=12, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    buf.seek(0)
    plt.close(fig)
    
    return buf.getvalue()
