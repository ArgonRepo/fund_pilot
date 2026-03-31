"""
FundPilot 美股市场数据模块
获取美股期货数据（NQ=F 纳指100 / ES=F 标普500），用于 QDII 基金辅助决策

数据源优先级（多源降级）:
1. AKShare futures_global_spot_em (东方财富全球期货)
2. AKShare stock_us_spot_em (东方财富美股)
3. yfinance NQ=F/ES=F (Yahoo 期货，容易被限流)

反爬策略:
- 会话级缓存: 同一次任务周期内只请求一次
- 多源降级: 主源失败自动切换备用源
- 请求前延时: 避免连续请求触发限流
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.logger import get_logger

logger = get_logger("us_market")


@dataclass
class USFuturesData:
    """美股期货数据（通用，适用于 NQ/ES 等）"""
    price: float                # 当前价格
    change_pct: float           # 涨跌幅 (%)
    previous_close: float       # 前收盘价
    timestamp: datetime         # 数据时间
    data_source: str            # 数据来源标识
    futures_symbol: str = ""    # 期货代码标识 (NQ=F / ES=F)
    market_status: str = ""     # 市场状态描述
    is_fallback: bool = False   # 是否为降级数据


# 向后兼容别名
NQFuturesData = USFuturesData


# ============================================================
# 会话级缓存（同一进程生命周期内避免重复请求）
# ============================================================

_nq_cache: Optional[USFuturesData] = None
_nq_cache_time: Optional[datetime] = None
_es_cache: Optional[USFuturesData] = None
_es_cache_time: Optional[datetime] = None
_CACHE_TTL_SECONDS = 300  # 缓存有效期 5 分钟


def _is_cache_valid(cache_data, cache_time) -> bool:
    """检查缓存是否在有效期内"""
    if cache_data is None or cache_time is None:
        return False
    age = (datetime.now() - cache_time).total_seconds()
    return age < _CACHE_TTL_SECONDS


def clear_nq_cache():
    """清除 NQ 缓存（供测试或强制刷新使用）"""
    global _nq_cache, _nq_cache_time
    _nq_cache = None
    _nq_cache_time = None


def clear_es_cache():
    """清除 ES 缓存"""
    global _es_cache, _es_cache_time
    _es_cache = None
    _es_cache_time = None


def _get_market_status() -> str:
    """判断市场状态（北京时间）"""
    now_hour = datetime.now().hour
    if 6 <= now_hour < 21:
        return "盘前交易 (期货)"
    elif 21 <= now_hour or now_hour < 5:
        return "正式交易 (期货)"
    else:
        return "盘后交易 (期货)"


# ============================================================
# 数据源 1: AKShare 全球期货 (东方财富)
# ============================================================

def _fetch_via_akshare_futures(keywords: list[str], symbol: str) -> Optional[USFuturesData]:
    """通过 AKShare 全球期货接口获取期货数据"""
    try:
        import akshare as ak

        logger.info(f"数据源1: AKShare 全球期货 ({symbol})...")
        time.sleep(1.0)

        df = ak.futures_global_spot_em()

        if df is None or df.empty:
            logger.debug("AKShare 全球期货: 返回数据为空")
            return None

        # 查找相关期货（尝试多种名称匹配）
        target_row = None

        for keyword in keywords:
            mask = df["名称"].str.contains(keyword, case=False, na=False)
            if mask.any():
                target_row = df[mask].iloc[0]
                break

        if target_row is None:
            logger.debug(f"AKShare 全球期货: 未找到 {symbol} 相关数据")
            return None

        current = float(target_row.get("最新价", 0))
        change_pct = float(target_row.get("涨跌幅", 0))
        # 从涨跌幅反推前收盘价
        if change_pct != 0 and current > 0:
            previous_close = current / (1 + change_pct / 100)
        else:
            previous_close = current

        if current <= 0:
            return None

        result = USFuturesData(
            price=round(current, 2),
            change_pct=round(change_pct, 2),
            previous_close=round(previous_close, 2),
            timestamp=datetime.now(),
            data_source="akshare_futures_global",
            futures_symbol=symbol,
            market_status=_get_market_status(),
            is_fallback=False
        )

        logger.info(f"{symbol} 期货 (AKShare): {result.price:.2f} ({result.change_pct:+.2f}%)")
        return result

    except Exception as e:
        logger.debug(f"AKShare 全球期货 {symbol} 失败: {e}")
        return None


# ============================================================
# 数据源 2: AKShare 美股实时 (东方财富)
# ============================================================

def _fetch_via_akshare_us_stock(keywords: list[str], symbol: str) -> Optional[USFuturesData]:
    """通过 AKShare 美股接口获取 ETF 替代数据"""
    try:
        import akshare as ak

        logger.info(f"数据源2: AKShare 美股 ({symbol})...")
        time.sleep(1.5)

        df = ak.stock_us_spot_em()

        if df is None or df.empty:
            logger.debug("AKShare 美股: 返回数据为空")
            return None

        target_row = None
        for keyword in keywords:
            mask = df["名称"].str.contains(keyword, case=False, na=False) | \
                   df["代码"].str.contains(keyword, case=False, na=False)
            if mask.any():
                target_row = df[mask].iloc[0]
                break

        if target_row is None:
            logger.debug(f"AKShare 美股: 未找到 {symbol} 替代数据")
            return None

        current = float(target_row.get("最新价", 0))
        change_pct = float(target_row.get("涨跌幅", 0))
        if change_pct != 0 and current > 0:
            previous_close = current / (1 + change_pct / 100)
        else:
            previous_close = current

        if current <= 0:
            return None

        result = USFuturesData(
            price=round(current, 2),
            change_pct=round(change_pct, 2),
            previous_close=round(previous_close, 2),
            timestamp=datetime.now(),
            data_source="akshare_us_stock",
            futures_symbol=symbol,
            market_status=_get_market_status(),
            is_fallback=True
        )

        logger.info(f"{symbol} 替代 (AKShare 美股): {result.price:.2f} ({result.change_pct:+.2f}%)")
        return result

    except Exception as e:
        logger.debug(f"AKShare 美股 {symbol} 失败: {e}")
        return None


# ============================================================
# 数据源 3: yfinance (Yahoo Finance) - 最后降级
# ============================================================

def _fetch_via_yfinance(yf_symbol: str, symbol: str) -> Optional[USFuturesData]:
    """通过 yfinance 获取期货数据（容易被限流）"""
    try:
        import yfinance as yf

        logger.info(f"数据源3: yfinance {yf_symbol}...")
        time.sleep(2.0)

        ticker = yf.Ticker(yf_symbol)
        info = ticker.fast_info

        current_price = info.last_price
        previous_close = info.previous_close

        if not current_price or not previous_close:
            logger.debug(f"yfinance: {yf_symbol} 数据不完整")
            return None

        change_pct = (current_price - previous_close) / previous_close * 100

        result = USFuturesData(
            price=round(current_price, 2),
            change_pct=round(change_pct, 2),
            previous_close=round(previous_close, 2),
            timestamp=datetime.now(),
            data_source=f"yfinance_{yf_symbol.lower().replace('=', '')}",
            futures_symbol=symbol,
            market_status=_get_market_status(),
            is_fallback=False
        )

        logger.info(f"{yf_symbol} (yfinance): {result.price:.2f} ({result.change_pct:+.2f}%)")
        return result

    except Exception as e:
        error_msg = str(e)
        if any(kw in error_msg for kw in ["Rate", "429", "Too Many", "subscriptable"]):
            logger.warning(f"yfinance 被限流: {e}")
        else:
            logger.debug(f"yfinance {yf_symbol} 失败: {e}")
        return None


# ============================================================
# 主入口：多源降级获取
# ============================================================

# ============================================================
# NQ (纳指100) 期货配置
# ============================================================

_NQ_AKSHARE_KEYWORDS = ["纳指", "纳斯达克", "NQ", "NASDAQ"]
_NQ_US_STOCK_KEYWORDS = ["QQQ", "纳斯达克"]
_NQ_YF_SYMBOL = "NQ=F"
_NQ_SYMBOL = "NQ=F"


# ============================================================
# ES (标普500) 期货配置
# ============================================================

_ES_AKSHARE_KEYWORDS = ["标普", "S&P", "SP500", "美国标普"]
_ES_US_STOCK_KEYWORDS = ["SPY", "标普"]
_ES_YF_SYMBOL = "ES=F"
_ES_SYMBOL = "ES=F"


def fetch_nq_futures() -> Optional[USFuturesData]:
    """
    获取 NQ (纳指100) 期货/指数数据（带缓存 + 多源降级）

    优先级: AKShare 全球期货 → AKShare 美股 → yfinance

    Returns:
        USFuturesData 数据，全部失败返回 None
    """
    global _nq_cache, _nq_cache_time

    # 1. 检查缓存
    if _is_cache_valid(_nq_cache, _nq_cache_time):
        logger.info(f"使用 NQ 缓存数据 ({_nq_cache.change_pct:+.2f}%)")
        return _nq_cache

    # 2. 按优先级尝试各数据源
    sources = [
        ("AKShare全球期货", lambda: _fetch_via_akshare_futures(_NQ_AKSHARE_KEYWORDS, _NQ_SYMBOL)),
        ("AKShare美股", lambda: _fetch_via_akshare_us_stock(_NQ_US_STOCK_KEYWORDS, _NQ_SYMBOL)),
        ("yfinance", lambda: _fetch_via_yfinance(_NQ_YF_SYMBOL, _NQ_SYMBOL)),
    ]

    for source_name, fetch_func in sources:
        try:
            result = fetch_func()
            if result is not None:
                # 更新缓存
                _nq_cache = result
                _nq_cache_time = datetime.now()
                return result
        except Exception as e:
            logger.warning(f"{source_name} 异常: {e}")
            continue

    logger.warning("所有纳指数据源均失败")
    return None


def fetch_es_futures() -> Optional[USFuturesData]:
    """
    获取 ES (标普500) 期货/指数数据（带缓存 + 多源降级）

    优先级: AKShare 全球期货 → AKShare 美股 → yfinance

    Returns:
        USFuturesData 数据，全部失败返回 None
    """
    global _es_cache, _es_cache_time

    # 1. 检查缓存
    if _is_cache_valid(_es_cache, _es_cache_time):
        logger.info(f"使用 ES 缓存数据 ({_es_cache.change_pct:+.2f}%)")
        return _es_cache

    # 2. 按优先级尝试各数据源
    sources = [
        ("AKShare全球期货", lambda: _fetch_via_akshare_futures(_ES_AKSHARE_KEYWORDS, _ES_SYMBOL)),
        ("AKShare美股", lambda: _fetch_via_akshare_us_stock(_ES_US_STOCK_KEYWORDS, _ES_SYMBOL)),
        ("yfinance", lambda: _fetch_via_yfinance(_ES_YF_SYMBOL, _ES_SYMBOL)),
    ]

    for source_name, fetch_func in sources:
        try:
            result = fetch_func()
            if result is not None:
                _es_cache = result
                _es_cache_time = datetime.now()
                return result
        except Exception as e:
            logger.warning(f"{source_name} 异常: {e}")
            continue

    logger.warning("所有标普数据源均失败")
    return None


def fetch_us_futures_for_fund(fund_name: str) -> Optional[USFuturesData]:
    """
    根据基金名称自动选择对应的美股期货数据

    - 标普/S&P/500 → ES=F
    - 纳指/纳斯达克/NASDAQ → NQ=F
    - 其他 QDII → 默认 NQ=F

    Args:
        fund_name: 基金名称

    Returns:
        USFuturesData 数据，全部失败返回 None
    """
    name_lower = fund_name.lower()
    if any(kw in name_lower for kw in ["标普", "s&p", "sp500", "500"]):
        logger.info(f"基金 '{fund_name}' 匹配 ES=F (标普500期货)")
        return fetch_es_futures()
    else:
        logger.info(f"基金 '{fund_name}' 匹配 NQ=F (纳指100期货)")
        return fetch_nq_futures()
