"""
FundPilot 美股市场数据模块
通过 yfinance 获取纳指100期货 (NQ=F) 实时数据
用于 QDII 基金的盘中参考和辅助决策

数据来源追踪:
- data_source="nq_futures": yfinance NQ=F 期货数据（实时）
- data_source="fund_nav": 天天基金估值数据（T-1 收盘净值，降级方案）
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.logger import get_logger

logger = get_logger("us_market")


@dataclass
class NQFuturesData:
    """纳指100期货数据"""
    price: float                # 当前价格
    change_pct: float           # 涨跌幅 (%)
    previous_close: float       # 前收盘价
    timestamp: datetime         # 数据时间
    data_source: str            # 数据来源: "nq_futures" | "fund_nav"
    market_status: str = ""     # 市场状态描述
    is_fallback: bool = False   # 是否为降级数据


def fetch_nq_futures() -> Optional[NQFuturesData]:
    """
    获取 NQ=F (纳指100期货) 实时数据
    
    期货交易时间 (美东): 周日 18:00 - 周五 17:00 (几乎 24 小时)
    北京时间 12:30 / 14:45 时对应美东深夜/凌晨，期货正在交易
    
    Returns:
        NQFuturesData 期货数据，失败返回 None
    """
    try:
        import yfinance as yf
        
        logger.info("获取 NQ=F (纳指100期货) 实时数据...")
        
        ticker = yf.Ticker("NQ=F")
        info = ticker.fast_info
        
        # 获取关键数据
        current_price = info.last_price
        previous_close = info.previous_close
        
        if not current_price or not previous_close:
            logger.warning("NQ=F 数据不完整，尝试备选方式...")
            return _fetch_nq_fallback_history()
        
        change_pct = (current_price - previous_close) / previous_close * 100
        
        # 判断市场状态
        now_hour = datetime.now().hour  # 北京时间
        if 6 <= now_hour < 21:
            market_status = "盘前交易 (期货)"
        elif 21 <= now_hour or now_hour < 5:
            market_status = "正式交易 (期货)"
        else:
            market_status = "盘后交易 (期货)"
        
        result = NQFuturesData(
            price=current_price,
            change_pct=round(change_pct, 2),
            previous_close=previous_close,
            timestamp=datetime.now(),
            data_source="nq_futures",
            market_status=market_status,
            is_fallback=False
        )
        
        logger.info(f"NQ=F 期货: {current_price:.2f} ({change_pct:+.2f}%) [{market_status}]")
        return result
        
    except Exception as e:
        logger.warning(f"yfinance 获取 NQ=F 失败: {e}")
        return _fetch_nq_fallback_history()


def _fetch_nq_fallback_history() -> Optional[NQFuturesData]:
    """
    降级方案: 从 yfinance 获取 NQ=F 最近的历史收盘数据
    如果实时数据获取失败，使用最近一个交易日的收盘数据
    """
    try:
        import yfinance as yf
        
        logger.info("降级: 尝试获取 NQ=F 最近历史数据...")
        ticker = yf.Ticker("NQ=F")
        hist = ticker.history(period="5d")
        
        if hist.empty or len(hist) < 2:
            logger.warning("NQ=F 历史数据也获取失败")
            return None
        
        latest = hist.iloc[-1]
        prev = hist.iloc[-2]
        
        change_pct = (latest["Close"] - prev["Close"]) / prev["Close"] * 100
        
        result = NQFuturesData(
            price=round(latest["Close"], 2),
            change_pct=round(change_pct, 2),
            previous_close=round(prev["Close"], 2),
            timestamp=datetime.now(),
            data_source="nq_futures",
            market_status="历史收盘 (非实时)",
            is_fallback=True
        )
        
        logger.info(f"NQ=F 历史数据: {result.price:.2f} ({result.change_pct:+.2f}%) [降级]")
        return result
        
    except Exception as e:
        logger.error(f"NQ=F 历史数据也获取失败: {e}")
        return None
