"""
FundPilot-AI 量化指标单元测试
更新：测试 250 日分位值计算
"""

import pytest
from strategy.indicators import (
    calculate_percentile,
    calculate_ma,
    calculate_ma_deviation,
    calculate_drawdown,
    calculate_all_metrics,
    get_percentile_zone,
    PERCENTILE_WINDOW,
    MA_WINDOW
)


class TestPercentile:
    """分位值计算测试"""
    
    def test_middle_value(self):
        """测试中间值"""
        prices = [1.0, 1.5, 2.0]  # min=1, max=2
        result = calculate_percentile(1.5, prices)
        assert result == 50.0
    
    def test_min_value(self):
        """测试最小值"""
        prices = [1.0, 1.5, 2.0]
        result = calculate_percentile(1.0, prices)
        assert result == 0.0
    
    def test_max_value(self):
        """测试最大值"""
        prices = [1.0, 1.5, 2.0]
        result = calculate_percentile(2.0, prices)
        assert result == 100.0
    
    def test_below_min(self):
        """测试低于最小值（限制在 0）"""
        prices = [1.0, 1.5, 2.0]
        result = calculate_percentile(0.5, prices)
        assert result == 0.0
    
    def test_above_max(self):
        """测试高于最大值（限制在 100）"""
        prices = [1.0, 1.5, 2.0]
        result = calculate_percentile(2.5, prices)
        assert result == 100.0
    
    def test_equal_prices(self):
        """测试所有价格相等（避免除零）"""
        prices = [1.0, 1.0, 1.0]
        result = calculate_percentile(1.0, prices)
        assert result == 50.0
    
    def test_empty_prices(self):
        """测试空列表"""
        result = calculate_percentile(1.0, [])
        assert result == 50.0


class TestMA:
    """均线计算测试"""
    
    def test_normal(self):
        """测试正常计算"""
        prices = [1.0, 2.0, 3.0]
        result = calculate_ma(prices, 60)
        assert result == 2.0
    
    def test_window_limit(self):
        """测试窗口限制"""
        prices = list(range(1, 101))  # 1-100
        result = calculate_ma(prices, 60)
        # 取前 60 个：1-60，平均 30.5
        assert result == 30.5
    
    def test_empty(self):
        """测试空列表"""
        result = calculate_ma([], 60)
        assert result == 0.0


class TestMADeviation:
    """均线偏离度计算测试"""
    
    def test_above_ma(self):
        """测试高于均线"""
        result = calculate_ma_deviation(1.1, 1.0)
        assert result == pytest.approx(10.0)
    
    def test_below_ma(self):
        """测试低于均线"""
        result = calculate_ma_deviation(0.9, 1.0)
        assert result == pytest.approx(-10.0)
    
    def test_equal_ma(self):
        """测试等于均线"""
        result = calculate_ma_deviation(1.0, 1.0)
        assert result == 0.0
    
    def test_zero_ma(self):
        """测试均线为零（避免除零）"""
        result = calculate_ma_deviation(1.0, 0.0)
        assert result == 0.0


class TestDrawdown:
    """回撤计算测试"""
    
    def test_no_drawdown(self):
        """测试无回撤"""
        result = calculate_drawdown(2.0, 2.0)
        assert result == 0.0
    
    def test_with_drawdown(self):
        """测试有回撤"""
        result = calculate_drawdown(0.8, 1.0)
        assert result == pytest.approx(20.0)
    
    def test_above_peak(self):
        """测试高于峰值（无负回撤）"""
        result = calculate_drawdown(1.2, 1.0)
        assert result == 0.0


class TestPercentileZone:
    """分位区间测试"""
    
    def test_golden_pit(self):
        """测试黄金坑"""
        assert get_percentile_zone(10) == "黄金坑"
        assert get_percentile_zone(19.9) == "黄金坑"
    
    def test_undervalued(self):
        """测试低估区"""
        assert get_percentile_zone(20) == "低估区"
        assert get_percentile_zone(39.9) == "低估区"
    
    def test_reasonable(self):
        """测试合理区"""
        assert get_percentile_zone(50) == "合理区"
    
    def test_overvalued(self):
        """测试高估区"""
        assert get_percentile_zone(85) == "高估区"


class TestCalculateAllMetrics:
    """综合指标计算测试"""
    
    def test_full_metrics(self):
        """测试完整指标计算"""
        prices = [float(i) for i in range(100, 0, -1)]  # 100 条数据
        metrics = calculate_all_metrics(50.0, prices, daily_change=2.5)
        
        assert metrics.max_250 == 100.0
        assert metrics.min_250 == 1.0
        assert 0 <= metrics.percentile_250 <= 100
        assert metrics.daily_change == 2.5
    
    def test_window_config(self):
        """测试窗口配置"""
        assert PERCENTILE_WINDOW == 250
        assert MA_WINDOW == 60
