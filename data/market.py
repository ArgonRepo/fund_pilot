"""
FundPilot 市场环境数据模块
获取大盘指数实时行情
"""

from dataclasses import dataclass
from typing import Optional

from core.logger import get_logger
from data.http_client import get_text, request_stats

logger = get_logger("market")

# 新浪指数行情 API
INDEX_QUOTE_API = "http://hq.sinajs.cn/list={index_codes}"

# 常用指数代码
INDEX_CODES = {
    "上证指数": "sh000001",
    "沪深300": "sh000300",
    "创业板指": "sz399006",
    "中证500": "sh000905"
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


def _parse_index_quote(content: str, code: str) -> Optional[tuple[str, float, float]]:
    """
    解析指数行情
    
    Returns:
        (名称, 当前点位, 涨跌幅) 或 None
    """
    try:
        # 格式: var hq_str_sh000001="上证指数,3000.00,2990.00,3010.00,...";
        for line in content.split(";"):
            if code not in line:
                continue
            
            if "=" not in line or '""' in line:
                continue
            
            data = line.split('"')[1].split(",")
            if len(data) < 4:
                continue
            
            name = data[0]
            yesterday_close = float(data[2])
            current = float(data[3])
            
            if yesterday_close == 0:
                continue
            
            change = (current - yesterday_close) / yesterday_close * 100
            return (name, current, round(change, 2))
            
    except Exception as e:
        logger.debug(f"解析指数 {code} 失败: {e}")
    
    return None


def fetch_market_indices() -> dict[str, MarketIndex]:
    """
    获取市场指数行情
    
    Returns:
        {指数名称: MarketIndex}
    """
    codes = list(INDEX_CODES.values())
    url = INDEX_QUOTE_API.format(index_codes=",".join(codes))
    
    try:
        # 使用统一客户端
        text = get_text(url, source="sina", timeout=5, encoding="gbk")
        
        if not text:
            request_stats.record_failure()
            logger.warning("获取市场指数失败")
            return {}
        
        results = {}
        for name, code in INDEX_CODES.items():
            parsed = _parse_index_quote(text, code)
            if parsed:
                idx_name, current, change = parsed
                results[name] = MarketIndex(
                    name=name,
                    code=code,
                    current=current,
                    change=change
                )
        
        request_stats.record_success()
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
