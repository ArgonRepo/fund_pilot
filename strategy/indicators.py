"""
FundPilot-AI 量化指标计算模块
计算分位值、均线偏离度、回撤、波动率等核心指标

重要更新 v2.0：
- 多周期分位值（60日/250日/500日）交叉验证，避免锚定偏误
- 增加历史波动率计算，用于动态阈值调整
- 增加市场体制识别辅助指标
"""

from dataclasses import dataclass
from typing import Optional
import math


# 窗口配置
PERCENTILE_WINDOW_SHORT = 60    # 短期分位窗口：60 日
PERCENTILE_WINDOW_MID = 250     # 中期分位窗口：250 日（约 1 年）
PERCENTILE_WINDOW_LONG = 500    # 长期分位窗口：500 日（约 2 年）
MA_WINDOW = 60                  # 均线计算窗口：60 日


@dataclass
class QuantMetrics:
    """量化指标集合"""
    # 多周期分位值
    percentile_60: float          # 60日分位值 (0-100) - 短期
    percentile_250: float         # 250日分位值 (0-100) - 中期（主要参考）
    percentile_500: float         # 500日分位值 (0-100) - 长期
    
    # 均线相关
    ma_60: float                  # 60日均线
    ma_deviation: float           # 均线偏离度 (%)
    
    # 极值
    max_250: float                # 250日最高
    min_250: float                # 250日最低
    
    # 回撤
    drawdown: Optional[float]     # 回撤幅度 (%) - 基于 250 日最高点
    drawdown_60: Optional[float]  # 60日回撤幅度 (%) - 短期风险指标
    
    # 波动率
    volatility_60: float          # 60日年化波动率 (%)
    
    # 当日涨跌
    daily_change: Optional[float] # 当日涨跌幅 (%)
    
    @property
    def percentile_consensus(self) -> str:
        """
        多周期分位共识判断（使用默认阈值40/60）
        
        Returns:
            共识状态: "强低估" / "弱低估" / "分歧" / "弱高估" / "强高估"
        """
        return get_percentile_consensus(self, 40.0, 60.0)
    
    def get_consensus_with_thresholds(self, low_threshold: float, high_threshold: float) -> str:
        """
        多周期分位共识判断（自定义阈值）
        
        Args:
            low_threshold: 低估阈值（如30%）
            high_threshold: 高估阈值（如70%）
        
        Returns:
            共识状态
        """
        return get_percentile_consensus(self, low_threshold, high_threshold)
    
    @property
    def trend_direction(self) -> str:
        """
        趋势方向判断（短期 vs 长期分位差异）
        
        Returns:
            趋势: "上升趋势" / "下降趋势" / "震荡"
        """
        diff = self.percentile_60 - self.percentile_500
        if diff > 20:
            return "上升趋势"
        elif diff < -20:
            return "下降趋势"
        else:
            return "震荡"


def get_percentile_consensus(
    metrics: QuantMetrics, 
    low_threshold: float = 40.0,
    high_threshold: float = 60.0
) -> str:
    """
    多周期分位共识判断（支持动态阈值）
    
    Args:
        metrics: 量化指标
        low_threshold: 低估阈值（如30%用于周期资产）
        high_threshold: 高估阈值（如70%用于周期资产）
    
    Returns:
        共识状态: "强低估" / "弱低估" / "分歧" / "弱高估" / "强高估"
    """
    short_low = metrics.percentile_60 < low_threshold
    mid_low = metrics.percentile_250 < low_threshold
    long_low = metrics.percentile_500 < low_threshold
    
    short_high = metrics.percentile_60 > high_threshold
    mid_high = metrics.percentile_250 > high_threshold
    long_high = metrics.percentile_500 > high_threshold
    
    low_count = sum([short_low, mid_low, long_low])
    high_count = sum([short_high, mid_high, long_high])
    
    if low_count == 3:
        return "强低估"
    elif low_count >= 2:
        return "弱低估"
    elif high_count == 3:
        return "强高估"
    elif high_count >= 2:
        return "弱高估"
    else:
        return "分歧"


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


def calculate_volatility(prices: list[float], window: int = 60) -> float:
    """
    计算年化波动率
    
    公式: 日收益率标准差 * sqrt(250)
    
    Args:
        prices: 历史价格列表（按时间降序，最新在前）
        window: 计算窗口
    
    Returns:
        年化波动率百分比
    """
    if len(prices) < 2:
        return 0.0
    
    # 取最近 window 个数据
    recent_prices = prices[:window] if len(prices) > window else prices
    
    if len(recent_prices) < 2:
        return 0.0
    
    # 计算日收益率（注意价格是降序的，所以需要反转计算）
    returns = []
    for i in range(len(recent_prices) - 1):
        # prices[i] 是较新的，prices[i+1] 是较旧的
        if recent_prices[i + 1] != 0:
            daily_return = (recent_prices[i] - recent_prices[i + 1]) / recent_prices[i + 1]
            returns.append(daily_return)
    
    if len(returns) < 2:
        return 0.0
    
    # 计算标准差
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance)
    
    # 年化（假设 250 个交易日）
    annualized_volatility = std_dev * math.sqrt(250) * 100
    
    return annualized_volatility


def calculate_all_metrics(
    current_price: float,
    prices_history: list[float],
    daily_change: Optional[float] = None
) -> QuantMetrics:
    """
    计算所有量化指标（增强版）
    
    Args:
        current_price: 当前价格（预估净值）
        prices_history: 历史价格列表（按时间降序，最新在前，建议 500+ 条）
        daily_change: 当日涨跌幅（可选）
    
    Returns:
        QuantMetrics 包含所有指标
    """
    if not prices_history:
        return QuantMetrics(
            percentile_60=50.0,
            percentile_250=50.0,
            percentile_500=50.0,
            ma_60=current_price,
            ma_deviation=0.0,
            max_250=current_price,
            min_250=current_price,
            drawdown=0.0,
            drawdown_60=0.0,
            volatility_60=0.0,
            daily_change=daily_change
        )
    
    # 多周期分位值计算
    prices_60 = prices_history[:PERCENTILE_WINDOW_SHORT] if len(prices_history) > PERCENTILE_WINDOW_SHORT else prices_history
    prices_250 = prices_history[:PERCENTILE_WINDOW_MID] if len(prices_history) > PERCENTILE_WINDOW_MID else prices_history
    prices_500 = prices_history[:PERCENTILE_WINDOW_LONG] if len(prices_history) > PERCENTILE_WINDOW_LONG else prices_history
    
    max_250 = max(prices_250)
    min_250 = min(prices_250)
    max_60 = max(prices_60)
    
    # 均线
    ma_60 = calculate_ma(prices_history, MA_WINDOW)
    
    # 波动率
    volatility_60 = calculate_volatility(prices_history, 60)
    
    return QuantMetrics(
        percentile_60=calculate_percentile(current_price, prices_60),
        percentile_250=calculate_percentile(current_price, prices_250),
        percentile_500=calculate_percentile(current_price, prices_500),
        ma_60=ma_60,
        ma_deviation=calculate_ma_deviation(current_price, ma_60),
        max_250=max_250,
        min_250=min_250,
        drawdown=calculate_drawdown(current_price, max_250),
        drawdown_60=calculate_drawdown(current_price, max_60),
        volatility_60=volatility_60,
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


def get_dynamic_ma_threshold(volatility: float) -> float:
    """
    根据波动率动态计算均线偏离阈值
    
    低波动品种（如债券）使用较小阈值，高波动品种使用较大阈值
    
    Args:
        volatility: 年化波动率 (%)
    
    Returns:
        均线偏离阈值 (%)，负值表示低于均线多少触发
    """
    # 基准：年化波动率的 1/10 作为日均阈值
    # 例如：10% 年化波动率 -> 1% 日阈值
    # 最小 0.3%，最大 5%
    threshold = max(0.3, min(5.0, volatility / 10))
    return -threshold


def get_dynamic_drop_threshold(volatility: float) -> tuple[float, float]:
    """
    根据波动率动态计算大跌阈值
    
    Args:
        volatility: 年化波动率 (%)
    
    Returns:
        (普通大跌阈值, 严重大跌阈值)，均为负值
    """
    # 日波动率 ≈ 年化波动率 / sqrt(250) ≈ 年化波动率 / 15.8
    daily_volatility = volatility / 15.8
    
    # 普通大跌：1.5 倍日波动率
    # 严重大跌：2.5 倍日波动率
    # 最小值限制：债券最低 0.2%/0.4%，最大不超过 5%/8%
    normal_threshold = -max(0.20, min(5.0, daily_volatility * 1.5))
    severe_threshold = -max(0.40, min(8.0, daily_volatility * 2.5))
    
    return normal_threshold, severe_threshold
