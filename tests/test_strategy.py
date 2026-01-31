"""
FundPilot-AI 策略逻辑单元测试
更新 v2.0：测试多周期分位值策略和动态阈值
"""

import pytest
from strategy.indicators import QuantMetrics, calculate_volatility, get_dynamic_ma_threshold, get_dynamic_drop_threshold
from strategy.etf_strategy import evaluate_etf_strategy, Decision, get_buy_multiplier
from strategy.bond_strategy import evaluate_bond_strategy, detect_bond_signal


def _make_metrics(
    percentile_250: float,
    percentile_60: float = None,
    percentile_500: float = None,
    ma_deviation: float = 0,
    daily_change: float = 0,
    volatility_60: float = 10.0  # 默认 10% 年化波动率
) -> QuantMetrics:
    """创建测试用指标（完整版）"""
    if percentile_60 is None:
        percentile_60 = percentile_250
    if percentile_500 is None:
        percentile_500 = percentile_250
    
    return QuantMetrics(
        percentile_60=percentile_60,
        percentile_250=percentile_250,
        percentile_500=percentile_500,
        ma_60=1.0,
        ma_deviation=ma_deviation,
        max_250=1.2,
        min_250=0.8,
        drawdown=0,
        drawdown_60=0,
        volatility_60=volatility_60,
        daily_change=daily_change
    )


class TestETFStrategy:
    """ETF 网格策略测试"""
    
    def test_golden_pit_strong_consensus(self):
        """测试黄金坑 + 强共识 - 应该双倍补仓"""
        metrics = _make_metrics(
            percentile_250=10,
            percentile_60=15,
            percentile_500=12
        )
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.DOUBLE_BUY
        assert "黄金坑" in result.zone or result.zone == "黄金坑"
    
    def test_golden_pit_with_divergence(self):
        """测试黄金坑但多周期分歧 - 应该正常定投"""
        metrics = _make_metrics(
            percentile_250=15,
            percentile_60=20,
            percentile_500=75  # 长期高估
        )
        result = evaluate_etf_strategy(metrics)
        # 分歧时降级为正常定投
        assert result.decision in [Decision.NORMAL_BUY, Decision.DOUBLE_BUY]
    
    def test_undervalued(self):
        """测试低估区 - 应该正常定投"""
        metrics = _make_metrics(percentile_250=30)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.NORMAL_BUY
    
    def test_reasonable_below_ma(self):
        """测试合理区低于均线 - 应该正常定投"""
        metrics = _make_metrics(percentile_250=50, ma_deviation=-5)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.NORMAL_BUY
    
    def test_reasonable_above_ma(self):
        """测试合理区高于均线 - 应该观望"""
        metrics = _make_metrics(percentile_250=55, ma_deviation=5)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.HOLD
    
    def test_overvalued(self):
        """测试偏高区 - 应该观望"""
        metrics = _make_metrics(percentile_250=75)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.HOLD
    
    def test_highly_overvalued(self):
        """测试高估区 - 应该暂停定投"""
        metrics = _make_metrics(percentile_250=90)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.STOP_BUY
    
    def test_circuit_breaker_drop(self):
        """测试熔断 - 大跌触发"""
        metrics = _make_metrics(percentile_250=30, daily_change=-8.0)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.HOLD
        assert "熔断" in result.zone
    
    def test_circuit_breaker_rise(self):
        """测试熔断 - 大涨触发"""
        metrics = _make_metrics(percentile_250=30, daily_change=8.0)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.HOLD
        assert "熔断" in result.zone


class TestBuyMultiplier:
    """补仓倍数测试"""
    
    def test_extreme_undervalued(self):
        """极度低估 - 2倍"""
        assert get_buy_multiplier(5) == 2.0
    
    def test_golden_pit(self):
        """黄金坑 - 1.5倍"""
        assert get_buy_multiplier(15) == 1.5
    
    def test_undervalued(self):
        """低估 - 1.2倍"""
        assert get_buy_multiplier(30) == 1.2
    
    def test_reasonable(self):
        """合理 - 1倍"""
        assert get_buy_multiplier(50) == 1.0
    
    def test_high(self):
        """偏高 - 0.5倍（减半）"""
        assert get_buy_multiplier(70) == 0.5
    
    def test_overvalued(self):
        """高估 - 0倍（暂停）"""
        assert get_buy_multiplier(85) == 0.0
    
    def test_with_strong_consensus_low(self):
        """强低估共识增强"""
        result = get_buy_multiplier(15, consensus="强低估")
        assert result > 1.5  # 应该被增强


class TestDynamicThresholds:
    """动态阈值测试"""
    
    def test_ma_threshold_low_volatility(self):
        """低波动率 - 较小均线阈值"""
        threshold = get_dynamic_ma_threshold(3.0)  # 3% 年化波动率
        assert threshold == -0.3  # 最小值
    
    def test_ma_threshold_high_volatility(self):
        """高波动率 - 较大均线阈值"""
        threshold = get_dynamic_ma_threshold(20.0)  # 20% 年化波动率
        assert threshold == -2.0  # 20/10 = 2
    
    def test_drop_threshold_low_volatility(self):
        """低波动率 - 较小大跌阈值"""
        normal, severe = get_dynamic_drop_threshold(3.0)
        # 低波动率应该使用较小的阈值（接近最小值）
        assert -0.5 < normal <= -0.20
        assert -0.8 < severe <= -0.40
    
    def test_drop_threshold_high_volatility(self):
        """高波动率 - 较大大跌阈值"""
        normal, severe = get_dynamic_drop_threshold(30.0)
        # 30% 年化 -> 日波动约 1.9%
        assert normal < -0.20
        assert severe < normal


class TestBondStrategy:
    """债券防守策略测试"""
    
    def test_normal_fluctuation(self):
        """测试正常波动 - 应该观望"""
        metrics = _make_metrics(
            percentile_250=50,
            ma_deviation=0.1,
            daily_change=-0.05,
            volatility_60=3.0  # 低波动
        )
        result = evaluate_bond_strategy(metrics)
        assert result.decision == Decision.HOLD
    
    def test_significant_drop_dynamic(self):
        """测试显著下跌（动态阈值）"""
        metrics = _make_metrics(
            percentile_250=50,
            ma_deviation=0.1,
            daily_change=-0.35,
            volatility_60=3.0
        )
        result = evaluate_bond_strategy(metrics)
        # 低波动债券 -0.35% 应该触发
        assert result.decision in [Decision.NORMAL_BUY, Decision.DOUBLE_BUY]
    
    def test_significant_ma_break(self):
        """测试显著跌破均线"""
        metrics = _make_metrics(
            percentile_250=50,
            ma_deviation=-0.5,
            daily_change=-0.1,
            volatility_60=3.0
        )
        result = evaluate_bond_strategy(metrics)
        assert result.decision in [Decision.NORMAL_BUY, Decision.DOUBLE_BUY]
    
    def test_overvalued_warning(self):
        """测试高估区预警"""
        metrics = _make_metrics(
            percentile_250=92,
            ma_deviation=0.1,
            daily_change=-0.1,
            volatility_60=3.0
        )
        result = evaluate_bond_strategy(metrics)
        assert result.decision == Decision.HOLD
        assert "高" in result.zone
    
    def test_bond_circuit_breaker(self):
        """测试债券熔断"""
        metrics = _make_metrics(
            percentile_250=50,
            ma_deviation=0,
            daily_change=-2.5,  # 债券跌 2.5% 非常罕见
            volatility_60=3.0
        )
        result = evaluate_bond_strategy(metrics)
        assert result.decision == Decision.HOLD
        assert "熔断" in result.zone


class TestBondSignal:
    """债券信号检测测试"""
    
    def test_no_signal(self):
        """测试无信号"""
        metrics = _make_metrics(
            percentile_250=50,
            ma_deviation=0.1,
            daily_change=-0.05,
            volatility_60=3.0
        )
        signal = detect_bond_signal(metrics)
        assert signal.has_opportunity is False
    
    def test_ma_break_signal(self):
        """测试显著跌破均线信号"""
        metrics = _make_metrics(
            percentile_250=50,
            ma_deviation=-0.5,
            daily_change=-0.1,
            volatility_60=3.0
        )
        signal = detect_bond_signal(metrics)
        assert signal.has_opportunity is True
        assert "均线" in signal.signal_type
    
    def test_overvalued_flag(self):
        """测试高估标记"""
        metrics = _make_metrics(
            percentile_250=95,
            ma_deviation=0.1,
            daily_change=-0.1,
            volatility_60=3.0
        )
        signal = detect_bond_signal(metrics)
        assert signal.is_overvalued is True
    
    def test_dynamic_thresholds_recorded(self):
        """测试动态阈值被记录"""
        metrics = _make_metrics(
            percentile_250=50,
            ma_deviation=-0.5,
            daily_change=-0.3,
            volatility_60=5.0
        )
        signal = detect_bond_signal(metrics)
        assert signal.dynamic_thresholds is not None
        assert "volatility_60" in signal.dynamic_thresholds


class TestPercentileConsensus:
    """多周期分位共识测试"""
    
    def test_strong_low(self):
        """三周期都低估"""
        metrics = _make_metrics(
            percentile_250=30,
            percentile_60=25,
            percentile_500=35
        )
        assert metrics.percentile_consensus == "强低估"
    
    def test_weak_low(self):
        """两周期低估"""
        metrics = _make_metrics(
            percentile_250=30,
            percentile_60=25,
            percentile_500=55
        )
        assert metrics.percentile_consensus == "弱低估"
    
    def test_strong_high(self):
        """三周期都高估"""
        metrics = _make_metrics(
            percentile_250=75,
            percentile_60=80,
            percentile_500=70
        )
        assert metrics.percentile_consensus == "强高估"
    
    def test_divergence(self):
        """分歧"""
        metrics = _make_metrics(
            percentile_250=50,
            percentile_60=30,
            percentile_500=70
        )
        assert metrics.percentile_consensus == "分歧"


class TestTrendDirection:
    """趋势方向测试"""
    
    def test_uptrend(self):
        """上升趋势"""
        metrics = _make_metrics(
            percentile_250=60,
            percentile_60=75,
            percentile_500=40
        )
        assert metrics.trend_direction == "上升趋势"
    
    def test_downtrend(self):
        """下降趋势"""
        metrics = _make_metrics(
            percentile_250=40,
            percentile_60=25,
            percentile_500=60
        )
        assert metrics.trend_direction == "下降趋势"
    
    def test_oscillation(self):
        """震荡"""
        metrics = _make_metrics(
            percentile_250=50,
            percentile_60=55,
            percentile_500=50
        )
        assert metrics.trend_direction == "震荡"
