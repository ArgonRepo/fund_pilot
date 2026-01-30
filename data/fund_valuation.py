"""
FundPilot 实时估值获取模块
从天天基金获取盘中实时估值
"""

import re
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from core.logger import get_logger
from data.http_client import get_text, request_stats

logger = get_logger("fund_valuation")

# 天天基金估值 API
FUND_GZ_API = "http://fundgz.1234567.com.cn/js/{fund_code}.js"

# 数据失效阈值（分钟）
STALE_THRESHOLD_MINUTES = 30


@dataclass
class FundValuation:
    """基金实时估值数据"""
    fund_code: str           # 基金代码
    fund_name: str           # 基金名称
    nav: float               # 上一日净值
    estimate_nav: float      # 预估净值
    estimate_change: float   # 预估涨跌幅 (%)
    estimate_time: datetime  # 估值时间
    is_stale: bool = False   # 数据是否失效


def _parse_jsonp(jsonp_str: str) -> dict:
    """解析 JSONP 格式响应"""
    # 格式: jsonpgz({...})
    match = re.search(r'jsonpgz\((.*)\)', jsonp_str)
    if not match:
        raise ValueError(f"无法解析 JSONP 响应: {jsonp_str[:100]}")
    return json.loads(match.group(1))


def _check_stale(estimate_time: datetime) -> bool:
    """检查数据是否失效（超过 30 分钟）"""
    now = datetime.now()
    diff_minutes = (now - estimate_time).total_seconds() / 60
    return diff_minutes > STALE_THRESHOLD_MINUTES


def fetch_fund_valuation(fund_code: str) -> Optional[FundValuation]:
    """
    获取基金实时估值
    
    Args:
        fund_code: 基金代码
    
    Returns:
        FundValuation 对象，失败返回 None
    """
    url = FUND_GZ_API.format(fund_code=fund_code)
    
    try:
        logger.info(f"获取基金 {fund_code} 实时估值...")
        
        # 使用统一客户端（自带重试、UA轮换、延时）
        text = get_text(url, source="tiantian", timeout=10)
        
        if not text:
            request_stats.record_failure()
            logger.warning(f"基金 {fund_code} 估值获取失败")
            return None
        
        # 解析 JSONP
        data = _parse_jsonp(text)
        
        # 解析估值时间
        # gztime 格式: "2024-01-15 14:30"
        estimate_time = datetime.strptime(data["gztime"], "%Y-%m-%d %H:%M")
        
        # 检查数据新鲜度
        is_stale = _check_stale(estimate_time)
        if is_stale:
            logger.warning(f"基金 {fund_code} 估值数据已过期: {data['gztime']}")
        
        valuation = FundValuation(
            fund_code=data["fundcode"],
            fund_name=data["name"],
            nav=float(data["dwjz"]),  # 上一日净值
            estimate_nav=float(data["gsz"]),  # 预估净值
            estimate_change=float(data["gszzl"]),  # 预估涨跌幅
            estimate_time=estimate_time,
            is_stale=is_stale
        )
        
        request_stats.record_success()
        logger.info(f"基金 {fund_code} 估值: {valuation.estimate_change:+.2f}% (时间: {data['gztime']})")
        return valuation
        
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        request_stats.record_failure()
        logger.error(f"解析基金 {fund_code} 估值数据失败: {e}")
        return None
    except Exception as e:
        request_stats.record_failure()
        logger.error(f"获取基金 {fund_code} 估值失败: {e}")
        return None


def fetch_multiple_valuations(fund_codes: list[str]) -> dict[str, Optional[FundValuation]]:
    """
    批量获取多只基金估值
    
    Args:
        fund_codes: 基金代码列表
    
    Returns:
        {fund_code: FundValuation} 字典
    """
    results = {}
    for code in fund_codes:
        results[code] = fetch_fund_valuation(code)
    return results
