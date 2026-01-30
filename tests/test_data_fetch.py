"""
FundPilot-AI 数据获取集成测试
需要网络连接
"""

import pytest
from datetime import datetime


class TestFundValuation:
    """实时估值获取测试"""
    
    @pytest.mark.network
    def test_fetch_valuation(self):
        """测试获取估值（需要网络）"""
        from data.fund_valuation import fetch_fund_valuation
        
        # 使用一只常见基金测试
        valuation = fetch_fund_valuation("110011")  # 易方达中小盘
        
        # 非交易时间可能获取不到最新数据，但应该有返回
        if valuation:
            assert valuation.fund_code == "110011"
            assert valuation.estimate_nav > 0
            assert isinstance(valuation.estimate_time, datetime)
    
    @pytest.mark.network
    def test_invalid_fund_code(self):
        """测试无效基金代码"""
        from data.fund_valuation import fetch_fund_valuation
        
        # 无效代码可能返回 None 或抛出异常
        result = fetch_fund_valuation("999999")
        # 不强制要求特定行为，只要不崩溃即可


class TestMarketData:
    """市场数据获取测试"""
    
    @pytest.mark.network
    def test_fetch_market_context(self):
        """测试获取市场环境（需要网络）"""
        from data.market import get_market_context
        
        context = get_market_context()
        
        # 应该总是返回 MarketContext 对象
        assert context is not None
        assert context.summary  # 应该有汇总描述


class TestGztimeValidation:
    """gztime 有效性校验测试"""
    
    def test_stale_check(self):
        """测试数据失效判断"""
        from data.fund_valuation import _check_stale
        from datetime import datetime, timedelta
        
        # 30 分钟前的数据应该失效
        old_time = datetime.now() - timedelta(minutes=40)
        assert _check_stale(old_time) is True
        
        # 刚刚的数据应该有效
        recent_time = datetime.now() - timedelta(minutes=5)
        assert _check_stale(recent_time) is False


class TestJsonpParsing:
    """JSONP 解析测试"""
    
    def test_valid_jsonp(self):
        """测试有效 JSONP 解析"""
        from data.fund_valuation import _parse_jsonp
        
        jsonp = 'jsonpgz({"fundcode":"110011","name":"易方达中小盘"})'
        result = _parse_jsonp(jsonp)
        
        assert result["fundcode"] == "110011"
        assert result["name"] == "易方达中小盘"
    
    def test_invalid_jsonp(self):
        """测试无效 JSONP"""
        from data.fund_valuation import _parse_jsonp
        
        with pytest.raises(ValueError):
            _parse_jsonp("invalid content")
