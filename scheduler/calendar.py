"""
FundPilot-AI 交易日过滤模块
判断当前日期是否为 A 股交易日
"""

from datetime import date, datetime
from typing import Optional

from chinese_calendar import is_workday, is_holiday

from core.logger import get_logger

logger = get_logger("calendar")


def is_trading_day(check_date: Optional[date] = None) -> bool:
    """
    判断是否为 A 股交易日
    
    交易日条件：
    1. 周一至周五
    2. 非法定节假日
    
    Args:
        check_date: 要检查的日期，默认今天
    
    Returns:
        是否为交易日
    """
    if check_date is None:
        check_date = date.today()
    
    # 周末直接返回 False
    if check_date.weekday() >= 5:  # 5=周六, 6=周日
        logger.debug(f"{check_date} 是周末，非交易日")
        return False
    
    # 检查节假日
    try:
        if is_holiday(check_date):
            logger.debug(f"{check_date} 是法定节假日，非交易日")
            return False
        
        if not is_workday(check_date):
            logger.debug(f"{check_date} 非工作日，非交易日")
            return False
            
    except Exception as e:
        # chinesecalendar 可能不支持某些日期，保守起见返回 True
        logger.warning(f"无法判断 {check_date} 是否为节假日: {e}")
        # 周一至周五默认认为是交易日
        return True
    
    logger.debug(f"{check_date} 是交易日")
    return True


def should_run_task() -> bool:
    """
    判断是否应该运行任务
    
    条件：今天是交易日
    
    Returns:
        是否应该运行
    """
    today = date.today()
    
    if not is_trading_day(today):
        logger.info(f"今天 {today} 非交易日，跳过任务")
        return False
    
    logger.info(f"今天 {today} 是交易日，可以运行任务")
    return True
