"""
FundPilot-AI 量化指标计算模块
计算分位值、均线偏离度、回撤等核心指标
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class QuantMetrics:
    """量化指标集合"""
    percentile_60: float          # 60日分位值 (0-100)
    ma_60: float                  # 60日均线
    ma_deviation: float           # 均线偏离度 (%)
    max_60: float                 # 60日最高
    min_60: float                 # 60日最低
    drawdown: Optional[float]     # 回撤幅度 (%)
    daily_change: Optional[float] # 当日涨跌幅 (%)


def calculate_percentile_60(current_price: float, prices_60d: list[float]) -> float:
    """
    计算 60 日分位值
    
    公式: (今日价格 - 60日最低) / (60日最高 - 60日最低) * 100
    
    Args:
        current_price: 当前价格（预估净值）
        prices_60d: 60 日历史价格列表
    
    Returns:
        分位值百分比 (0-100)
    """
    if not prices_60d:
        return 50.0
    
    max_60 = max(prices_60d)
    min_60 = min(prices_60d)
    
    # 避免除零
    if max_60 == min_60:
        return 50.0
    
    percentile = (current_price - min_60) / (max_60 - min_60) * 100
    
    # 限制在 0-100 范围内
    return max(0, min(100, percentile))


def calculate_ma_60(prices_60d: list[float]) -> float:
    """
    计算 60 日均线
    
    Args:
        prices_60d: 60 日历史价格列表
    
    Returns:
        60 日均线值
    """
    if not prices_60d:
        return 0.0
    return sum(prices_60d) / len(prices_60d)


def calculate_ma_deviation(current_price: float, ma_60: float) -> float:
    """
    计算与 60 日均线的偏离度
    
    公式: (当前价格 - MA60) / MA60 * 100
    
    Args:
        current_price: 当前价格
        ma_60: 60日均线
    
    Returns:
        偏离度百分比（正值为高于均线，负值为低于均线）
    """
    if ma_60 == 0:
        return 0.0
    return (current_price - ma_60) / ma_60 * 100


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
    prices_60d: list[float],
    daily_change: Optional[float] = None
) -> QuantMetrics:
    """
    计算所有量化指标
    
    Args:
        current_price: 当前价格（预估净值）
        prices_60d: 60 日历史价格列表
        daily_change: 当日涨跌幅（可选）
    
    Returns:
        QuantMetrics 包含所有指标
    """
    if not prices_60d:
        return QuantMetrics(
            percentile_60=50.0,
            ma_60=current_price,
            ma_deviation=0.0,
            max_60=current_price,
            min_60=current_price,
            drawdown=0.0,
            daily_change=daily_change
        )
    
    max_60 = max(prices_60d)
    min_60 = min(prices_60d)
    ma_60 = calculate_ma_60(prices_60d)
    
    return QuantMetrics(
        percentile_60=calculate_percentile_60(current_price, prices_60d),
        ma_60=ma_60,
        ma_deviation=calculate_ma_deviation(current_price, ma_60),
        max_60=max_60,
        min_60=min_60,
        drawdown=calculate_drawdown(current_price, max_60),
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
