"""
FundPilot 持仓穿透分析模块
获取基金重仓股信息及实时行情（使用 AKShare）
"""

import time
from dataclasses import dataclass
from http.client import RemoteDisconnected
from typing import Optional

import akshare as ak
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import ConnectionError, RequestException

from core.logger import get_logger
from core.database import get_database
from core.config import FundConfig
from core.http_client import request_stats

logger = get_logger("holdings")

# AKShare 请求间隔（秒）
AKSHARE_REQUEST_INTERVAL = 1.0


@dataclass
class StockHolding:
    """重仓股信息"""
    stock_code: str      # 股票代码
    stock_name: str      # 股票名称
    weight: float        # 持仓占比 (%)
    change: Optional[float] = None  # 今日涨跌幅 (%)


@dataclass
class HoldingsInsight:
    """持仓洞察"""
    holdings: list[StockHolding]
    top_gainers: list[str]   # 领涨股 (如 "中芯国际 +3.2%")
    top_losers: list[str]    # 领跌股
    summary: str             # 汇总描述


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, RemoteDisconnected, RequestException)),
    reraise=True
)
def _fetch_a_share_spot_em():
    """获取全部 A 股实时行情（带重试）"""
    return ak.stock_zh_a_spot_em()


def _fetch_a_share_spot() -> Optional[pd.DataFrame]:
    """
    获取全部 A 股实时行情（批量）

    Returns:
        DataFrame，失败返回 None
    """
    try:
        time.sleep(AKSHARE_REQUEST_INTERVAL)
        df = _fetch_a_share_spot_em()
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.warning(f"获取 A 股实时行情失败: {e}")
    return None


def _lookup_stock_change(spot_df: Optional[pd.DataFrame], stock_code: str) -> Optional[float]:
    """
    从 A 股行情快照中查询某只股票的涨跌幅

    Args:
        spot_df: A 股实时行情 DataFrame
        stock_code: 股票代码（纯数字，如 600519）

    Returns:
        涨跌幅百分比，找不到返回 None
    """
    if spot_df is None:
        return None

    try:
        # 去掉市场前缀（sh/sz），只保留纯数字代码
        code = stock_code.strip()
        if code.startswith(("sh", "sz")):
            code = code[2:]

        row = spot_df[spot_df["代码"] == code]
        if row.empty:
            return None

        change = float(row.iloc[0].get("涨跌幅", 0))
        return round(change, 2)
    except Exception as e:
        logger.debug(f"查询股票 {stock_code} 行情失败: {e}")
        return None


def fetch_fund_holdings(fund_code: str, underlying_etf: Optional[str] = None) -> list[tuple[str, str, float]]:
    """
    获取基金重仓股

    Args:
        fund_code: 基金代码
        underlying_etf: ETF 联接基金的底层 ETF 代码

    Returns:
        [(股票代码, 股票名称, 持仓占比), ...]
    """
    try:
        # ETF 联接基金穿透到底层 ETF
        target_code = underlying_etf or fund_code

        logger.info(f"获取基金 {target_code} 持仓信息...")

        # AkShare 请求间隔
        time.sleep(AKSHARE_REQUEST_INTERVAL)

        # 尝试获取 ETF 持仓
        try:
            df = ak.fund_portfolio_hold_em(symbol=target_code, date="")
        except Exception:
            # 如果失败，尝试开放式基金持仓
            time.sleep(AKSHARE_REQUEST_INTERVAL)
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date="")

        if df is None or df.empty:
            request_stats.record_failure()
            logger.warning(f"基金 {target_code} 未获取到持仓数据")
            return []

        # 取前 10 大重仓股
        df = df.head(10)

        result = []
        for _, row in df.iterrows():
            stock_code = str(row.get("股票代码", ""))
            stock_name = str(row.get("股票名称", ""))
            weight = float(row.get("占净值比例", 0))

            if stock_code and stock_name:
                result.append((stock_code, stock_name, weight))

        request_stats.record_success()
        logger.info(f"基金 {target_code} 获取到 {len(result)} 只重仓股")
        return result

    except Exception as e:
        request_stats.record_failure()
        logger.error(f"获取基金 {fund_code} 持仓失败: {e}")
        return []


def get_holdings_with_quotes(fund_config: FundConfig) -> Optional[HoldingsInsight]:
    """
    获取持仓及实时行情

    Args:
        fund_config: 基金配置

    Returns:
        HoldingsInsight 对象
    """
    from datetime import datetime

    db = get_database()

    # 持仓缓存过期时间（90天，持仓通常每季度更新）
    HOLDINGS_CACHE_TTL_DAYS = 90

    # 检查缓存是否过期
    cache_updated_at = db.get_holdings_updated_at(fund_config.code)
    cache_expired = True

    if cache_updated_at:
        age_days = (datetime.now() - cache_updated_at).days
        cache_expired = age_days > HOLDINGS_CACHE_TTL_DAYS
        if cache_expired:
            logger.info(f"基金 {fund_config.code} 持仓缓存已过期 ({age_days} 天)，刷新中...")

    # 获取持仓数据
    holdings_data = None

    if not cache_expired:
        # 缓存有效，使用缓存
        holdings_data = db.get_holdings(fund_config.code)

    if not holdings_data:
        # 缓存过期或不存在，从 API 获取
        holdings_data = fetch_fund_holdings(fund_config.code, fund_config.underlying_etf)
        if holdings_data:
            db.save_holdings(fund_config.code, holdings_data)

    if not holdings_data:
        return None

    # 一次性获取全部 A 股实时行情，然后逐个查询
    logger.info("获取 A 股实时行情快照...")
    spot_df = _fetch_a_share_spot()

    holdings = []
    for code, name, weight in holdings_data:
        change = _lookup_stock_change(spot_df, code)
        holdings.append(StockHolding(code, name, weight, change))

    # 按涨跌幅排序
    holdings_with_change = [h for h in holdings if h.change is not None]
    holdings_with_change.sort(key=lambda x: x.change, reverse=True)

    # 生成洞察
    top_gainers = [f"{h.stock_name} ({h.change:+.1f}%)" for h in holdings_with_change[:3] if h.change > 0]
    top_losers = [f"{h.stock_name} ({h.change:+.1f}%)" for h in holdings_with_change[-3:] if h.change < 0][::-1]

    # 统计涨跌家数
    up_count = len([h for h in holdings_with_change if h.change > 0])
    down_count = len([h for h in holdings_with_change if h.change < 0])

    if down_count > up_count:
        summary = f"前十大重仓股中 {down_count} 只下跌，整体偏弱。"
    elif up_count > down_count:
        summary = f"前十大重仓股中 {up_count} 只上涨，整体偏强。"
    else:
        summary = "前十大重仓股涨跌互现，表现分化。"

    return HoldingsInsight(
        holdings=holdings,
        top_gainers=top_gainers,
        top_losers=top_losers,
        summary=summary
    )
