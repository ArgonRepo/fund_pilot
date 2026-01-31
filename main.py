"""
FundPilot-AI 基金智能定投决策系统
程序入口
"""

import os
import sys
import time

# 强制设置时区
os.environ['TZ'] = 'Asia/Shanghai'
try:
    time.tzset()  # 使时区设置生效（某些系统需要）
except AttributeError:
    pass  # Windows 系统没有 tzset

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import get_config
from core.logger import logger
from core.database import get_database
from scheduler.jobs import run_decision_task, run_alert_task


def init():
    """初始化系统"""
    logger.info("="*60)
    logger.info("FundPilot-AI 基金智能定投决策系统")
    logger.info("="*60)
    
    # 加载配置
    config = get_config()
    logger.info(f"已加载 {len(config.funds)} 只基金配置")
    for fund in config.funds:
        logger.info(f"  - {fund.name} ({fund.code}) [{fund.type}]")
    
    # 初始化数据库
    db = get_database()
    logger.info(f"数据库初始化完成")
    
    logger.info(f"预警时间: {config.scheduler.alert_time}")
    logger.info(f"决策时间: {config.scheduler.decision_time}")
    logger.info("="*60)


def create_scheduler() -> BlockingScheduler:
    """创建调度器"""
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


def main():
    """主入口"""
    # 初始化
    init()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'run':
            # 立即运行决策任务（用于测试）
            logger.info("手动触发决策任务...")
            run_decision_task()
            return
        
        elif command == 'alert':
            # 立即运行预警任务
            logger.info("手动触发预警任务...")
            run_alert_task()
            return
        
        elif command == 'test':
            # 测试模式：检查配置和数据获取
            logger.info("运行测试模式...")
            test_mode()
            return
        
        else:
            print(f"未知命令: {command}")
            print("可用命令: run, alert, test")
            return
    
    # 启动调度器
    scheduler = create_scheduler()
    
    logger.info("调度器启动，等待任务触发...")
    logger.info("按 Ctrl+C 退出")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器已停止")


def test_mode():
    """测试模式"""
    from data.fund_valuation import fetch_fund_valuation
    from data.market import get_market_context
    
    config = get_config()
    
    logger.info("测试数据获取...")
    
    # 测试估值获取
    for fund in config.funds[:2]:  # 只测试前两只
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


if __name__ == '__main__':
    main()
