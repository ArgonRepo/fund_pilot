"""
FundPilot 配置加载器
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
    type: str  # "Bond" / "ETF_Feeder" / "QDII"
    underlying_etf: Optional[str] = None  # ETF 联接基金对应的底层 ETF
    asset_class: Optional[str] = None     # 资产类别: GOLD_ETF / COMMODITY_CYCLE / BOND_ENHANCED / US_EQUITY_INDEX 等


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
    email: EmailConfig
    scheduler: SchedulerConfig
    funds: list[FundConfig] = field(default_factory=list)



def _parse_receivers(receivers_str: str) -> list[str]:
    """解析收件人列表（逗号分隔）"""
    if not receivers_str:
        return []
    return [r.strip() for r in receivers_str.split(",") if r.strip()]


def load_config() -> AppConfig:
    """加载配置"""
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
    # 仅从 data/funds.json 加载
    funds_json_path = os.path.join(os.getcwd(), "data", "funds.json")
    if os.path.exists(funds_json_path):
        try:
            with open(funds_json_path, "r", encoding="utf-8") as f:
                funds_data = json.load(f)
                funds = [
                    FundConfig(
                        code=f["code"],
                        name=f["name"],
                        type=f["type"],
                        underlying_etf=f.get("underlying_etf"),
                        asset_class=f.get("asset_class")
                    )
                    for f in funds_data
                ]
        except Exception as e:
            raise ValueError(f"加载基金配置文件失败 (data/funds.json): {e}")
    else:
        # 如果文件不存在，返回空列表或抛出错误
        print(f"Warning: Fund config file not found at {funds_json_path}")
        funds = []
    
    return AppConfig(
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
