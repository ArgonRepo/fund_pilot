"""
FundPilot-AI 基金智能定投决策系统
程序入口
"""

from core.logger import logger
from core.bootstrap import init_system, create_scheduler, handle_cli_command


def main():
    """主入口"""
    # 1. 检查命令行参数
    handle_cli_command()
    
    # 2. 初始化系统
    init_system()
    
    # 3. 启动调度器
    scheduler = create_scheduler()
    
    logger.info("调度器启动，等待任务触发...")
    logger.info("按 Ctrl+C 退出")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器已停止")


if __name__ == '__main__':
    main()
