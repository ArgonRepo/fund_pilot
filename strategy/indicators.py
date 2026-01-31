"""
FundPilot-AI 量化指标计算模块
计算分位值、均线偏离度、回撤等核心指标

重要更新：
- 分位值窗口扩展为 250 日（约 1 年交易日），避免短期行情失真
- 均线保持 60 日，兼顾灵敏度
"""

from dataclasses import dataclass
from typing import Optional


# 窗口配置
PERCENTILE_WINDOW = 250  # 分位值计算窗口：250 个交易日（约 1 年）
MA_WINDOW = 60           # 均线计算窗口：60 日


@dataclass
class QuantMetrics:
    """量化指标集合"""
    percentile_250: float         # 250日分位值 (0-100)
    ma_60: float                  # 60日均线
    ma_deviation: float           # 均线偏离度 (%)
    max_250: float                # 250日最高
    min_250: float                # 250日最低
    drawdown: Optional[float]     # 回撤幅度 (%) - 基于 250 日最高点
    drawdown_60: Optional[float]  # 60日回撤幅度 (%) - 短期风险指标
    daily_change: Optional[float] # 当日涨跌幅 (%)


def calculate_percentile(current_price: float, prices: list[float]) -> float:
    """
    计算分位值
    
    公式: (今日价格 - 区间最低) / (区间最高 - 区间最低) * 100
    
    Args:
        current_price: 当前价格（预估净值）
        prices: 历史价格列表
    
    Returns:
        分位值百分比 (0-100)
    """
    if not prices:
        return 50.0
    
    max_price = max(prices)
    min_price = min(prices)
    
    # 避免除零
    if max_price == min_price:
        return 50.0
    
    percentile = (current_price - min_price) / (max_price - min_price) * 100
    
    # 限制在 0-100 范围内
    return max(0, min(100, percentile))


def calculate_ma(prices: list[float], window: int = MA_WINDOW) -> float:
    """
    计算移动平均线
    
    Args:
        prices: 历史价格列表（按时间降序，最新在前）
        window: 窗口大小
    
    Returns:
        移动平均值
    """
    if not prices:
        return 0.0
    
    # 取最近 window 个数据
    recent_prices = prices[:window] if len(prices) > window else prices
    return sum(recent_prices) / len(recent_prices)


def calculate_ma_deviation(current_price: float, ma: float) -> float:
    """
    计算与均线的偏离度
    
    公式: (当前价格 - MA) / MA * 100
    
    Args:
        current_price: 当前价格
        ma: 均线值
    
    Returns:
        偏离度百分比（正值为高于均线，负值为低于均线）
    """
    if ma == 0:
        return 0.0
    return (current_price - ma) / ma * 100


def calculate_drawdown(current_price: float, peak_price: float) -> float:
    """
    计算回撤幅度
    
    公式: (峰值 - 当前价格) / 峰值 * 100
    
    Args:
        current_price: 当前价格
        peak_price: 区间峰值
    
    Returns:
        回撤幅度百分比（正值，越大代表回撤越深）
    """
    if peak_price == 0:
        return 0.0
    return max(0, (peak_price - current_price) / peak_price * 100)


def calculate_all_metrics(
    current_price: float,
    prices_history: list[float],
    daily_change: Optional[float] = None
) -> QuantMetrics:
    """
    计算所有量化指标
    
    Args:
        current_price: 当前价格（预估净值）
        prices_history: 历史价格列表（按时间降序，最新在前，建议 250+ 条）
        daily_change: 当日涨跌幅（可选）
    
    Returns:
        QuantMetrics 包含所有指标
    """
    if not prices_history:
        return QuantMetrics(
            percentile_250=50.0,
            ma_60=current_price,
            ma_deviation=0.0,
            max_250=current_price,
            min_250=current_price,
            drawdown=0.0,
            drawdown_60=0.0,
            daily_change=daily_change
        )
    
    # 取 250 日数据用于分位值计算
    prices_250 = prices_history[:PERCENTILE_WINDOW] if len(prices_history) > PERCENTILE_WINDOW else prices_history
    max_250 = max(prices_250)
    min_250 = min(prices_250)
    
    # 取 60 日数据用于均线和回撤计算
    prices_60 = prices_history[:MA_WINDOW] if len(prices_history) > MA_WINDOW else prices_history
    max_60 = max(prices_60)
    ma_60 = calculate_ma(prices_history, MA_WINDOW)
    
    return QuantMetrics(
        percentile_250=calculate_percentile(current_price, prices_250),
        ma_60=ma_60,
        ma_deviation=calculate_ma_deviation(current_price, ma_60),
        max_250=max_250,
        min_250=min_250,
        drawdown=calculate_drawdown(current_price, max_250),
        drawdown_60=calculate_drawdown(current_price, max_60),
        daily_change=daily_change
    )


def get_percentile_zone(percentile: float) -> str:
    """
    获取分位区间描述
    
    Args:
        percentile: 分位值 (0-100)
    
    Returns:
        区间描述
    """
    if percentile < 20:
        return "黄金坑"
    elif percentile < 40:
        return "低估区"
    elif percentile < 60:
        return "合理区"
    elif percentile < 80:
        return "偏高区"
    else:
        return "高估区"
