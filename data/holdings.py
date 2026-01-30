"""
FundPilot-AI 持仓穿透分析模块
获取基金重仓股信息及实时行情
"""

from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import akshare as ak
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import get_logger
from core.database import get_database
from core.config import get_config, FundConfig

logger = get_logger("holdings")

# 股票行情 API（新浪）
STOCK_QUOTE_API = "http://hq.sinajs.cn/list={stock_code}"


@dataclass
class StockHolding:
    """重仓股信息"""
    stock_code: str      # 股票代码
    stock_name: str      # 股票名称
    weight: float        # 持仓占比 (%)
    change: Optional[float] = None  # 今日涨跌幅 (%)


@dataclass
class HoldingsInsight:
    """持仓洞察"""
    holdings: list[StockHolding]
    top_gainers: list[str]   # 领涨股 (如 "中芯国际 +3.2%")
    top_losers: list[str]    # 领跌股
    summary: str             # 汇总描述


def _normalize_stock_code(code: str) -> str:
    """规范化股票代码（添加市场前缀）"""
    code = code.strip()
    if code.startswith(("sh", "sz")):
        return code
    # 6 开头上海，其他深圳
    if code.startswith("6"):
        return f"sh{code}"
    else:
        return f"sz{code}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)
def _fetch_stock_quote(stock_code: str) -> Optional[float]:
    """
    获取股票实时涨跌幅
    
    Args:
        stock_code: 股票代码（如 sh600000）
    
    Returns:
        涨跌幅百分比，失败返回 None
    """
    try:
        url = STOCK_QUOTE_API.format(stock_code=stock_code)
        headers = {"Referer": "http://finance.sina.com.cn"}
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = "gbk"
        
        # 解析响应: var hq_str_sh600000="浦发银行,11.50,11.49,11.55,...";
        content = response.text
        if "=" not in content or '""' in content:
            return None
        
        data = content.split('"')[1].split(",")
        if len(data) < 4:
            return None
        
        # 今开、昨收、现价
        yesterday_close = float(data[2])
        current_price = float(data[3])
        
        if yesterday_close == 0:
            return None
        
        change = (current_price - yesterday_close) / yesterday_close * 100
        return round(change, 2)
        
    except Exception as e:
        logger.debug(f"获取股票 {stock_code} 行情失败: {e}")
        return None


def fetch_fund_holdings(fund_code: str, underlying_etf: Optional[str] = None) -> list[tuple[str, str, float]]:
    """
    获取基金重仓股
    
    Args:
        fund_code: 基金代码
        underlying_etf: ETF 联接基金的底层 ETF 代码
    
    Returns:
        [(股票代码, 股票名称, 持仓占比), ...]
    """
    try:
        # ETF 联接基金穿透到底层 ETF
        target_code = underlying_etf or fund_code
        
        logger.info(f"获取基金 {target_code} 持仓信息...")
        
        # 尝试获取 ETF 持仓
        try:
            df = ak.fund_portfolio_hold_em(symbol=target_code, date="")
        except Exception:
            # 如果失败，尝试开放式基金持仓
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date="")
        
        if df is None or df.empty:
            logger.warning(f"基金 {target_code} 未获取到持仓数据")
            return []
        
        # 取前 10 大重仓股
        df = df.head(10)
        
        result = []
        for _, row in df.iterrows():
            stock_code = str(row.get("股票代码", ""))
            stock_name = str(row.get("股票名称", ""))
            weight = float(row.get("占净值比例", 0))
            
            if stock_code and stock_name:
                result.append((stock_code, stock_name, weight))
        
        logger.info(f"基金 {target_code} 获取到 {len(result)} 只重仓股")
        return result
        
    except Exception as e:
        logger.error(f"获取基金 {fund_code} 持仓失败: {e}")
        return []


def get_holdings_with_quotes(fund_config: FundConfig) -> Optional[HoldingsInsight]:
    """
    获取持仓及实时行情
    
    Args:
        fund_config: 基金配置
    
    Returns:
        HoldingsInsight 对象
    """
    db = get_database()
    
    # 获取持仓（优先从缓存）
    holdings_data = db.get_holdings(fund_config.code)
    
    if not holdings_data:
        # 从 API 获取
        holdings_data = fetch_fund_holdings(fund_config.code, fund_config.underlying_etf)
        if holdings_data:
            db.save_holdings(fund_config.code, holdings_data)
    
    if not holdings_data:
        return None
    
    # 并发获取股票行情
    holdings = []
    stock_codes = [(code, name, weight) for code, name, weight in holdings_data]
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {}
        for code, name, weight in stock_codes:
            norm_code = _normalize_stock_code(code)
            future = executor.submit(_fetch_stock_quote, norm_code)
            future_map[future] = (code, name, weight)
        
        for future in as_completed(future_map):
            code, name, weight = future_map[future]
            try:
                change = future.result()
            except Exception:
                change = None
            holdings.append(StockHolding(code, name, weight, change))
    
    # 按涨跌幅排序
    holdings_with_change = [h for h in holdings if h.change is not None]
    holdings_with_change.sort(key=lambda x: x.change, reverse=True)
    
    # 生成洞察
    top_gainers = [f"{h.stock_name} ({h.change:+.1f}%)" for h in holdings_with_change[:3] if h.change > 0]
    top_losers = [f"{h.stock_name} ({h.change:+.1f}%)" for h in holdings_with_change[-3:] if h.change < 0][::-1]
    
    # 统计涨跌家数
    up_count = len([h for h in holdings_with_change if h.change > 0])
    down_count = len([h for h in holdings_with_change if h.change < 0])
    
    if down_count > up_count:
        summary = f"前十大重仓股中 {down_count} 只下跌，整体偏弱。"
    elif up_count > down_count:
        summary = f"前十大重仓股中 {up_count} 只上涨，整体偏强。"
    else:
        summary = "前十大重仓股涨跌互现，表现分化。"
    
    return HoldingsInsight(
        holdings=holdings,
        top_gainers=top_gainers,
        top_losers=top_losers,
        summary=summary
    )
