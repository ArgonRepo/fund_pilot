"""
FundPilot 历史净值获取模块
从 AkShare 获取基金历史净值数据
"""

import time
from datetime import date
from typing import Optional

import akshare as ak
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import get_logger
from core.database import get_database
from data.http_client import request_stats

logger = get_logger("fund_history")

# 默认获取天数（1年交易日 + 缓冲）
DEFAULT_DAYS = 260

# AkShare 请求间隔（秒）
AKSHARE_REQUEST_INTERVAL = 1.0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _fetch_from_akshare(fund_code: str, days: int = DEFAULT_DAYS) -> list[tuple[date, float, Optional[float]]]:
    """
    从 AkShare 获取历史净值（带重试）
    
    Returns:
        [(日期, 单位净值, 累计净值), ...]
    """
    try:
        logger.info(f"从 AkShare 获取基金 {fund_code} 历史净值...")
        
        # 请求间隔，避免频繁访问
        time.sleep(AKSHARE_REQUEST_INTERVAL)
        
        # 使用 AkShare 获取开放式基金净值
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        
        if df is None or df.empty:
            logger.warning(f"基金 {fund_code} 未获取到历史数据")
            request_stats.record_failure()
            return []
        
        # 取最近 N 天
        df = df.tail(days)
        
        result = []
        for _, row in df.iterrows():
            nav_date = row["净值日期"]
            if isinstance(nav_date, str):
                nav_date = date.fromisoformat(nav_date)
            elif hasattr(nav_date, "date"):
                nav_date = nav_date.date()
            
            nav = float(row["单位净值"])
            acc_nav = float(row.get("累计净值", nav)) if "累计净值" in row else None
            
            result.append((nav_date, nav, acc_nav))
        
        request_stats.record_success()
        logger.info(f"基金 {fund_code} 获取到 {len(result)} 条历史净值")
        return result
        
    except Exception as e:
        request_stats.record_failure()
        logger.error(f"从 AkShare 获取基金 {fund_code} 历史净值失败: {e}")
        raise  # 让 tenacity 重试


def get_fund_history(fund_code: str, days: int = DEFAULT_DAYS, force_refresh: bool = False) -> list[tuple[date, float]]:
    """
    获取基金历史净值（优先从缓存读取）
    
    Args:
        fund_code: 基金代码
        days: 获取天数（默认 260 天，约 1 年）
        force_refresh: 是否强制刷新
    
    Returns:
        [(日期, 净值), ...] 按日期降序（最新在前）
    """
    db = get_database()
    
    # 检查缓存
    if not force_refresh:
        cached = db.get_nav_history(fund_code, days)
        if cached and len(cached) >= days * 0.8:  # 缓存数据足够
            latest_date = cached[0][0]
            today = date.today()
            # 如果最新数据是今天或昨天，使用缓存
            if (today - latest_date).days <= 1:
                logger.info(f"使用缓存数据: 基金 {fund_code}, {len(cached)} 条")
                return cached
    
    # 从 AkShare 获取（带重试）
    try:
        nav_list = _fetch_from_akshare(fund_code, days + 10)  # 多取一些以防节假日
    except Exception as e:
        logger.error(f"获取基金 {fund_code} 历史净值最终失败: {e}")
        nav_list = []
    
    if nav_list:
        # 保存到缓存
        db.save_nav_history_batch(fund_code, nav_list)
        # 返回最近 N 天，降序排列
        return [(d, nav) for d, nav, _ in nav_list[-days:]][::-1]
    
    # 如果获取失败，返回缓存数据
    logger.warning(f"基金 {fund_code} 使用旧缓存数据")
    return db.get_nav_history(fund_code, days)


def calculate_nav_stats(nav_history: list[tuple[date, float]]) -> dict:
    """
    计算净值统计数据
    
    Args:
        nav_history: [(日期, 净值), ...] 
    
    Returns:
        {
            "max": 区间最高,
            "min": 区间最低,
            "avg": 区间均值,
            "latest_nav": 最新净值,
            "latest_date": 最新日期
        }
    """
    if not nav_history:
        return {}
    
    navs = [nav for _, nav in nav_history]
    
    return {
        "max": max(navs),
        "min": min(navs),
        "avg": sum(navs) / len(navs),
        "latest_nav": navs[0],
        "latest_date": nav_history[0][0]
    }


def get_recent_nav(nav_history: list[tuple[date, float]], count: int = 10) -> list[tuple[date, float]]:
    """获取最近 N 天净值（用于图表）"""
    return nav_history[:count]
