"""
FundPilot-AI 配置加载器
从 .env 文件加载所有配置
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


@dataclass
class FundConfig:
    """基金配置"""
    code: str
    name: str
    type: str  # "Bond" 或 "ETF_Feeder"
    underlying_etf: Optional[str] = None  # ETF 联接基金对应的底层 ETF
    asset_class: Optional[str] = None     # 资产类别: GOLD_ETF / COMMODITY_CYCLE / BOND_ENHANCED 等


@dataclass
class DeepSeekConfig:
    """DeepSeek API 配置"""
    api_key: str
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"


@dataclass
class EmailConfig:
    """邮件配置"""
    smtp_server: str
    smtp_port: int
    sender: str
    password: str
    receivers: list[str] = field(default_factory=list)


@dataclass
class SchedulerConfig:
    """调度配置"""
    timezone: str = "Asia/Shanghai"
    alert_time: str = "14:30"
    decision_time: str = "14:45"


@dataclass
class AppConfig:
    """应用总配置"""
    deepseek: DeepSeekConfig
    email: EmailConfig
    scheduler: SchedulerConfig
    funds: list[FundConfig] = field(default_factory=list)


def _parse_fund_list(fund_list_str: str) -> list[FundConfig]:
    """解析基金列表 JSON 字符串"""
    if not fund_list_str:
        return []
    try:
        funds_data = json.loads(fund_list_str)
        return [
            FundConfig(
                code=f["code"],
                name=f["name"],
                type=f["type"],
                underlying_etf=f.get("underlying_etf"),
                asset_class=f.get("asset_class")  # 资产类别
            )
            for f in funds_data
        ]
    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"基金列表配置格式错误: {e}")


def _parse_receivers(receivers_str: str) -> list[str]:
    """解析收件人列表（逗号分隔）"""
    if not receivers_str:
        return []
    return [r.strip() for r in receivers_str.split(",") if r.strip()]


def load_config() -> AppConfig:
    """加载配置"""
    # DeepSeek 配置
    deepseek = DeepSeekConfig(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    
    # 邮件配置
    email = EmailConfig(
        smtp_server=os.getenv("SMTP_SERVER", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "465")),
        sender=os.getenv("EMAIL_SENDER", ""),
        password=os.getenv("EMAIL_PASSWORD", ""),
        receivers=_parse_receivers(os.getenv("EMAIL_RECEIVERS", ""))
    )
    
    # 调度配置
    scheduler = SchedulerConfig(
        timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
        alert_time=os.getenv("ALERT_TIME", "14:30"),
        decision_time=os.getenv("DECISION_TIME", "14:45")
    )
    
    # 基金列表
    funds = _parse_fund_list(os.getenv("FUND_LIST", "[]"))
    
    return AppConfig(
        deepseek=deepseek,
        email=email,
        scheduler=scheduler,
        funds=funds
    )


# 全局配置实例（延迟加载）
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取配置单例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
