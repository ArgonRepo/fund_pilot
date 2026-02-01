"""
FundPilot-AI 资产分类与动态阈值配置
定义资产类型及其对应的策略参数

资产类型说明:
- GOLD_ETF: 黄金ETF联接，避险资产，与股市负相关
- COMMODITY_CYCLE: 周期商品ETF，强周期高波动
- BOND_ENHANCED: 二级债基，含股票仓位
- BOND_PURE: 纯债基金，低波动利率敏感
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AssetClass(Enum):
    """资产类别枚举"""
    GOLD_ETF = "GOLD_ETF"                   # 黄金ETF联接
    COMMODITY_CYCLE = "COMMODITY_CYCLE"     # 周期商品ETF
    BOND_ENHANCED = "BOND_ENHANCED"         # 二级债基
    BOND_PURE = "BOND_PURE"                 # 纯债基金
    DEFAULT_ETF = "DEFAULT_ETF"             # 默认ETF（未分类）
    DEFAULT_BOND = "DEFAULT_BOND"           # 默认债券（未分类）


@dataclass
class StrategyThresholds:
    """策略阈值配置"""
    # 分位区间阈值 [黄金坑, 低估, 高估, 过热]
    zone_thresholds: tuple[float, float, float, float]
    
    # 均线偏离基准阈值（低于此值视为显著偏离）
    ma_base_threshold: float
    
    # 熔断阈值（单日涨跌超过此值暂停决策）
    circuit_breaker_drop: float
    circuit_breaker_rise: float
    
    # 共识判断阈值（用于判断低估/高估）
    consensus_low_threshold: float = 40.0
    consensus_high_threshold: float = 60.0
    
    # AI决策权重（与策略决策合成时的权重）
    ai_weight: float = 0.5
    
    # 描述
    description: str = ""


# 各资产类型的阈值配置
ASSET_THRESHOLDS: dict[AssetClass, StrategyThresholds] = {
    
    AssetClass.GOLD_ETF: StrategyThresholds(
        zone_thresholds=(15.0, 35.0, 65.0, 85.0),  # 更宽容的区间
        ma_base_threshold=-2.5,
        circuit_breaker_drop=-8.0,   # 黄金较稳定，阈值可高些
        circuit_breaker_rise=8.0,
        consensus_low_threshold=35.0,
        consensus_high_threshold=65.0,
        ai_weight=0.6,  # 黄金需要更多定性判断，AI权重高
        description="黄金避险资产：与股市负相关，高估不一定暂停"
    ),
    
    AssetClass.COMMODITY_CYCLE: StrategyThresholds(
        zone_thresholds=(10.0, 30.0, 70.0, 90.0),  # 周期股需极端区间
        ma_base_threshold=-4.0,   # 高波动容忍
        circuit_breaker_drop=-10.0,  # 周期股波动大
        circuit_breaker_rise=10.0,
        consensus_low_threshold=30.0,
        consensus_high_threshold=70.0,
        ai_weight=0.5,  # 平衡
        description="周期商品：强周期高波动，需逆向思维"
    ),
    
    AssetClass.BOND_ENHANCED: StrategyThresholds(
        zone_thresholds=(20.0, 40.0, 60.0, 80.0),  # 标准区间
        ma_base_threshold=-1.5,
        circuit_breaker_drop=-3.0,  # 二级债基波动较大
        circuit_breaker_rise=3.0,
        consensus_low_threshold=40.0,
        consensus_high_threshold=60.0,
        ai_weight=0.4,  # 债券策略更可靠
        description="二级债基：含股票仓位，波动高于纯债"
    ),
    
    AssetClass.BOND_PURE: StrategyThresholds(
        zone_thresholds=(25.0, 45.0, 55.0, 75.0),  # 更敏感的区间
        ma_base_threshold=-0.8,
        circuit_breaker_drop=-1.5,  # 纯债波动小，阈值敏感
        circuit_breaker_rise=1.5,
        consensus_low_threshold=45.0,
        consensus_high_threshold=55.0,
        ai_weight=0.3,  # 纯债规则更可靠
        description="纯债基金：低波动利率敏感"
    ),
    
    AssetClass.DEFAULT_ETF: StrategyThresholds(
        zone_thresholds=(20.0, 40.0, 60.0, 80.0),
        ma_base_threshold=-3.0,
        circuit_breaker_drop=-7.0,
        circuit_breaker_rise=7.0,
        ai_weight=0.5,
        description="默认ETF策略"
    ),
    
    AssetClass.DEFAULT_BOND: StrategyThresholds(
        zone_thresholds=(20.0, 40.0, 60.0, 80.0),
        ma_base_threshold=-1.5,
        circuit_breaker_drop=-3.0,
        circuit_breaker_rise=3.0,
        ai_weight=0.4,
        description="默认债券策略"
    ),
}


def get_thresholds(asset_class: str) -> StrategyThresholds:
    """
    获取资产类型对应的阈值配置
    
    Args:
        asset_class: 资产类型字符串
    
    Returns:
        StrategyThresholds 阈值配置
    """
    try:
        ac = AssetClass(asset_class)
        return ASSET_THRESHOLDS[ac]
    except (ValueError, KeyError):
        # 未知类型，返回默认配置
        return ASSET_THRESHOLDS[AssetClass.DEFAULT_ETF]


def get_zone_name(percentile: float, thresholds: StrategyThresholds) -> str:
    """
    根据分位值和阈值获取区间名称
    
    Args:
        percentile: 分位值 (0-100)
        thresholds: 阈值配置
    
    Returns:
        区间名称
    """
    z = thresholds.zone_thresholds
    if percentile < z[0]:
        return "黄金坑"
    elif percentile < z[1]:
        return "低估区"
    elif percentile < z[2]:
        return "合理区"
    elif percentile < z[3]:
        return "偏高区"
    else:
        return "高估区"


def infer_asset_class(fund_type: str, fund_name: str) -> str:
    """
    根据基金类型和名称推断资产类别（用于未配置 asset_class 的情况）
    
    Args:
        fund_type: 基金类型 ("Bond" / "ETF_Feeder")
        fund_name: 基金名称
    
    Returns:
        推断的资产类别字符串
    """
    name_lower = fund_name.lower()
    
    if fund_type == "ETF_Feeder":
        if "黄金" in fund_name or "gold" in name_lower:
            return AssetClass.GOLD_ETF.value
        elif any(kw in fund_name for kw in ["有色", "金属", "铜", "铝", "锌", "稀土", "钢铁", "煤炭", "石油", "原油"]):
            return AssetClass.COMMODITY_CYCLE.value
        else:
            return AssetClass.DEFAULT_ETF.value
    
    elif fund_type == "Bond":
        # 二级债基通常名称中有"增强"、"回报"、"收益"等词
        if any(kw in fund_name for kw in ["增强", "回报", "收益", "双债", "信用"]):
            return AssetClass.BOND_ENHANCED.value
        else:
            return AssetClass.BOND_PURE.value
    
    return AssetClass.DEFAULT_ETF.value
