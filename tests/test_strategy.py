"""
FundPilot-AI 策略逻辑单元测试
更新：测试 250 日分位值策略和调整后的债券阈值
"""

import pytest
from strategy.indicators import QuantMetrics
from strategy.etf_strategy import evaluate_etf_strategy, Decision, get_buy_multiplier
from strategy.bond_strategy import (
    evaluate_bond_strategy, 
    detect_bond_signal,
    BOND_DROP_THRESHOLD,
    BOND_DROP_SEVERE,
    MA_DEVIATION_THRESHOLD
)


class TestETFStrategy:
    """ETF 网格策略测试"""
    
    def _make_metrics(self, percentile: float, ma_deviation: float = 0, daily_change: float = 0) -> QuantMetrics:
        """创建测试用指标"""
        return QuantMetrics(
            percentile_250=percentile,
            ma_60=1.0,
            ma_deviation=ma_deviation,
            max_250=1.2,
            min_250=0.8,
            drawdown=0,
            drawdown_60=0,
            daily_change=daily_change
        )
    
    def test_golden_pit(self):
        """测试黄金坑 - 应该双倍补仓"""
        metrics = self._make_metrics(10)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.DOUBLE_BUY
        assert result.zone == "黄金坑"
    
    def test_undervalued(self):
        """测试低估区 - 应该正常定投"""
        metrics = self._make_metrics(30)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.NORMAL_BUY
    
    def test_reasonable_below_ma(self):
        """测试合理区低于均线 - 应该正常定投"""
        metrics = self._make_metrics(50, ma_deviation=-5)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.NORMAL_BUY
    
    def test_reasonable_above_ma(self):
        """测试合理区高于均线 - 应该观望"""
        metrics = self._make_metrics(55, ma_deviation=5)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.HOLD
    
    def test_overvalued(self):
        """测试偏高区 - 应该观望"""
        metrics = self._make_metrics(75)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.HOLD
    
    def test_highly_overvalued(self):
        """测试高估区 - 应该暂停定投"""
        metrics = self._make_metrics(90)
        result = evaluate_etf_strategy(metrics)
        assert result.decision == Decision.STOP_BUY


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


class TestBondThresholds:
    """债券阈值配置测试"""
    
    def test_drop_threshold(self):
        """测试大跌阈值配置"""
        assert BOND_DROP_THRESHOLD == -0.30  # 更新后的阈值
    
    def test_severe_threshold(self):
        """测试严重大跌阈值"""
        assert BOND_DROP_SEVERE == -0.50
    
    def test_ma_deviation_threshold(self):
        """测试均线偏离阈值"""
        assert MA_DEVIATION_THRESHOLD == -0.30


class TestBondStrategy:
    """债券防守策略测试"""
    
    def _make_metrics(self, ma_deviation: float = 0, daily_change: float = 0, percentile: float = 50) -> QuantMetrics:
        """创建测试用指标"""
        return QuantMetrics(
            percentile_250=percentile,
            ma_60=1.0,
            ma_deviation=ma_deviation,
            max_250=1.02,
            min_250=0.98,
            drawdown=0,
            drawdown_60=0,
            daily_change=daily_change
        )
    
    def test_normal_fluctuation(self):
        """测试正常波动 - 应该观望"""
        metrics = self._make_metrics(ma_deviation=0.1, daily_change=-0.05)  # -0.05% 不触发
        result = evaluate_bond_strategy(metrics)
        assert result.decision == Decision.HOLD
    
    def test_small_drop_no_trigger(self):
        """测试小幅下跌不触发 - -0.15% 不应触发"""
        metrics = self._make_metrics(ma_deviation=0.1, daily_change=-0.15)
        result = evaluate_bond_strategy(metrics)
        assert result.decision == Decision.HOLD  # 更新后 -0.15% 不触发
    
    def test_significant_drop(self):
        """测试显著下跌 - -0.35% 应触发正常定投"""
        metrics = self._make_metrics(ma_deviation=0.1, daily_change=-0.35)
        result = evaluate_bond_strategy(metrics)
        assert result.decision in [Decision.NORMAL_BUY, Decision.DOUBLE_BUY]
    
    def test_significant_ma_break(self):
        """测试显著跌破均线 - 低于均线 0.5% 应触发"""
        metrics = self._make_metrics(ma_deviation=-0.5, daily_change=-0.1)
        result = evaluate_bond_strategy(metrics)
        assert result.decision in [Decision.NORMAL_BUY, Decision.DOUBLE_BUY]
    
    def test_overvalued_warning(self):
        """测试高估区预警"""
        metrics = self._make_metrics(ma_deviation=0.1, daily_change=-0.1, percentile=92)
        result = evaluate_bond_strategy(metrics)
        assert result.decision == Decision.HOLD
        assert "高" in result.reasoning or "高" in result.zone


class TestBondSignal:
    """债券信号检测测试"""
    
    def test_no_signal(self):
        """测试无信号"""
        metrics = QuantMetrics(
            percentile_250=50,
            ma_60=1.0,
            ma_deviation=0.1,
            max_250=1.02,
            min_250=0.98,
            drawdown=0,
            drawdown_60=0,
            daily_change=-0.05  # 太小，不触发
        )
        signal = detect_bond_signal(metrics)
        assert signal.has_opportunity is False
    
    def test_ma_break_signal(self):
        """测试显著跌破均线信号"""
        metrics = QuantMetrics(
            percentile_250=50,
            ma_60=1.0,
            ma_deviation=-0.5,  # 显著低于均线
            max_250=1.02,
            min_250=0.98,
            drawdown=0,
            drawdown_60=0,
            daily_change=-0.1
        )
        signal = detect_bond_signal(metrics)
        assert signal.has_opportunity is True
        assert "均线" in signal.signal_type
    
    def test_overvalued_flag(self):
        """测试高估标记"""
        metrics = QuantMetrics(
            percentile_250=95,  # 高估区
            ma_60=1.0,
            ma_deviation=0.1,
            max_250=1.02,
            min_250=0.98,
            drawdown=0,
            drawdown_60=0,
            daily_change=-0.1
        )
        signal = detect_bond_signal(metrics)
        assert signal.is_overvalued is True
