"""
FundPilot-AI 系统启动引导
封装系统初始化和调度器创建逻辑
"""

import os
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import get_config
from core.logger import logger
from core.database import get_database
from scheduler.jobs import run_decision_task, run_alert_task


def init_system():
    """初始化系统环境"""
    # 强制设置时区
    os.environ['TZ'] = 'Asia/Shanghai'
    try:
        import time
        time.tzset()
    except AttributeError:
        pass  # Windows 不需要

    logger.info("="*60)
    logger.info("FundPilot-AI 基金智能定投决策系统")
    logger.info(f"当前系统时间: {datetime.now()} (时区: {os.environ.get('TZ', '未设置')})")
    logger.info("="*60)
    
    # 加载配置
    config = get_config()
    logger.info(f"已加载 {len(config.funds)} 只基金配置")
    for fund in config.funds:
        logger.info(f"  - {fund.name} ({fund.code}) [{fund.type}]")
    
    # 初始化数据库
    db = get_database()
    logger.info(f"数据库初始化完成: {db.db_path}")
    
    logger.info(f"预警时间: {config.scheduler.alert_time}")
    logger.info(f"决策时间: {config.scheduler.decision_time}")
    logger.info("="*60)


def create_scheduler() -> BlockingScheduler:
    """创建并配置调度器"""
    config = get_config()
    
    scheduler = BlockingScheduler(timezone=config.scheduler.timezone)
    
    # 解析时间
    alert_hour, alert_minute = map(int, config.scheduler.alert_time.split(':'))
    decision_hour, decision_minute = map(int, config.scheduler.decision_time.split(':'))
    
    # 添加预警任务（周一至周五）
    scheduler.add_job(
        run_alert_task,
        CronTrigger(
            day_of_week='mon-fri',
            hour=alert_hour,
            minute=alert_minute,
            timezone=config.scheduler.timezone
        ),
        id='alert_task',
        name='预警任务',
        replace_existing=True
    )
    
    # 添加决策任务（周一至周五）
    scheduler.add_job(
        run_decision_task,
        CronTrigger(
            day_of_week='mon-fri',
            hour=decision_hour,
            minute=decision_minute,
            timezone=config.scheduler.timezone
        ),
        id='decision_task',
        name='决策任务',
        replace_existing=True
    )
    
    return scheduler


def handle_cli_command():
    """处理命令行参数"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'run':
            logger.info("手动触发决策任务...")
            run_decision_task()
            sys.exit(0)
        
        elif command == 'alert':
            logger.info("手动触发预警任务...")
            run_alert_task()
            sys.exit(0)
        
        elif command == 'test':
            logger.info("运行测试模式...")
            _run_test_mode()
            sys.exit(0)
        
        else:
            print(f"未知命令: {command}")
            print("可用命令: run, alert, test")
            sys.exit(1)


def _run_test_mode():
    """内部测试模式逻辑"""
    from data.fund_valuation import fetch_fund_valuation
    from data.market import get_market_context
    
    config = get_config()
    logger.info("测试数据获取...")
    
    # 测试估值获取
    if config.funds:
        for fund in config.funds[:2]:
            logger.info(f"测试获取 {fund.name} 估值...")
            valuation = fetch_fund_valuation(fund.code)
            if valuation:
                logger.info(f"  估值: {valuation.estimate_change:+.2f}%, 时间: {valuation.estimate_time}")
            else:
                logger.warning(f"  获取失败")
    
    # 测试市场数据
    logger.info("测试获取市场数据...")
    market = get_market_context()
    logger.info(f"  {market.summary}")
    
    logger.info("测试完成")
