"""
FundPilot-AI 日志系统
使用 RotatingFileHandler 进行日志轮转
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志文件
LOG_FILE = LOG_DIR / "fundpilot.log"

# 日志格式
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "fundpilot", level: int = logging.INFO) -> logging.Logger:
    """
    设置并返回 logger
    
    Args:
        name: logger 名称
        level: 日志级别
    
    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 文件 Handler（轮转：5MB，保留 5 个备份）
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # 控制台 Handler（仅用于开发调试）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# 默认 logger
logger = setup_logger()


def get_logger(name: str) -> logging.Logger:
    """获取子模块 logger"""
    return logging.getLogger(f"fundpilot.{name}")
