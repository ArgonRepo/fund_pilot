"""
FundPilot 市场环境数据模块
获取大盘指数实时行情（使用 AKShare）
"""

import time
from dataclasses import dataclass
from typing import Optional

import akshare as ak

from core.logger import get_logger
from core.http_client import request_stats

logger = get_logger("market")

# AKShare 请求间隔（秒）
AKSHARE_REQUEST_INTERVAL = 1.0

# 常用指数代码（不含市场前缀）
INDEX_CODES = {
    "上证指数": "000001",
    "沪深300": "000300",
    "创业板指": "399006",
    "中证500": "000905"
}


@dataclass
class MarketIndex:
    """市场指数"""
    name: str           # 指数名称
    code: str           # 指数代码
    current: float      # 当前点位
    change: float       # 涨跌幅 (%)


@dataclass
class MarketContext:
    """市场环境"""
    shanghai_index: Optional[MarketIndex]  # 上证指数
    hs300_index: Optional[MarketIndex]     # 沪深300
    summary: str                           # 市场概述


def fetch_market_indices() -> dict[str, MarketIndex]:
    """
    获取市场指数行情（通过 AKShare 东方财富接口）

    Returns:
        {指数名称: MarketIndex}
    """
    try:
        time.sleep(AKSHARE_REQUEST_INTERVAL)

        # 获取沪深重要指数实时行情
        df = ak.stock_zh_index_spot_em(symbol="沪深重要指数")

        if df is None or df.empty:
            request_stats.record_failure()
            logger.warning("获取市场指数失败: 返回数据为空")
            return {}

        results = {}
        for name, code in INDEX_CODES.items():
            # 按指数代码匹配
            row = df[df["代码"] == code]
            if row.empty:
                logger.debug(f"未找到指数 {name} ({code})")
                continue

            row = row.iloc[0]
            current = float(row.get("最新价", 0))
            change = float(row.get("涨跌幅", 0))

            if current > 0:
                results[name] = MarketIndex(
                    name=name,
                    code=code,
                    current=current,
                    change=round(change, 2)
                )

        request_stats.record_success()
        logger.info(f"获取到 {len(results)} 个市场指数")
        return results

    except Exception as e:
        request_stats.record_failure()
        logger.error(f"获取市场指数失败: {e}")
        return {}


def get_market_context() -> MarketContext:
    """
    获取市场环境上下文

    Returns:
        MarketContext 对象
    """
    try:
        indices = fetch_market_indices()

        shanghai = indices.get("上证指数")
        hs300 = indices.get("沪深300")

        # 生成市场概述
        if shanghai:
            if shanghai.change > 1:
                mood = "大涨"
            elif shanghai.change > 0:
                mood = "上涨"
            elif shanghai.change > -1:
                mood = "下跌"
            else:
                mood = "大跌"
            summary = f"今日 A 股市场整体{mood}，上证指数 {shanghai.change:+.2f}%。"
        else:
            summary = "市场数据获取中..."

        return MarketContext(
            shanghai_index=shanghai,
            hs300_index=hs300,
            summary=summary
        )

    except Exception as e:
        logger.error(f"获取市场环境失败: {e}")
        return MarketContext(
            shanghai_index=None,
            hs300_index=None,
            summary="市场数据暂时无法获取。"
        )
