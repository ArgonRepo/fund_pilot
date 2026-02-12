"""
FundPilot 美股市场数据模块
通过 yfinance 获取纳指100期货 (NQ=F) 实时数据
用于 QDII 基金的盘中参考和辅助决策

数据来源追踪:
- data_source="nq_futures": yfinance NQ=F 期货数据（实时）
- data_source="nq_futures": yfinance NQ=F 历史数据（降级方案）

反爬策略:
- 会话级缓存: 同一次任务周期内只请求一次
- 指数退避重试: 失败后 3/6/12 秒递增等待
- 请求前延时: 避免与其他 yfinance 调用冲突
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.logger import get_logger

logger = get_logger("us_market")


@dataclass
class NQFuturesData:
    """纳指100期货数据"""
    price: float                # 当前价格
    change_pct: float           # 涨跌幅 (%)
    previous_close: float       # 前收盘价
    timestamp: datetime         # 数据时间
    data_source: str            # 数据来源: "nq_futures"
    market_status: str = ""     # 市场状态描述
    is_fallback: bool = False   # 是否为降级数据


# ============================================================
# 会话级缓存（同一进程生命周期内避免重复请求）
# ============================================================

_nq_cache: Optional[NQFuturesData] = None
_nq_cache_time: Optional[datetime] = None
_NQ_CACHE_TTL_SECONDS = 300  # 缓存有效期 5 分钟


def _is_cache_valid() -> bool:
    """检查缓存是否在有效期内"""
    if _nq_cache is None or _nq_cache_time is None:
        return False
    age = (datetime.now() - _nq_cache_time).total_seconds()
    return age < _NQ_CACHE_TTL_SECONDS


def clear_nq_cache():
    """清除缓存（供测试或强制刷新使用）"""
    global _nq_cache, _nq_cache_time
    _nq_cache = None
    _nq_cache_time = None


# ============================================================
# 核心获取逻辑
# ============================================================

def fetch_nq_futures() -> Optional[NQFuturesData]:
    """
    获取 NQ=F (纳指100期货) 实时数据（带缓存）
    
    期货交易时间 (美东): 周日 18:00 - 周五 17:00 (几乎 24 小时)
    北京时间 12:30 / 14:45 时对应美东深夜/凌晨，期货正在交易
    
    Returns:
        NQFuturesData 期货数据，失败返回 None
    """
    global _nq_cache, _nq_cache_time
    
    # 1. 检查缓存
    if _is_cache_valid():
        logger.info(f"使用 NQ=F 缓存数据 ({_nq_cache.change_pct:+.2f}%)")
        return _nq_cache
    
    # 2. 尝试实时获取
    try:
        result = _fetch_nq_realtime()
    except Exception as e:
        logger.warning(f"NQ=F 实时数据重试耗尽: {e}")
        result = None
    
    # 3. 实时失败，尝试历史降级
    if result is None:
        try:
            result = _fetch_nq_fallback_history()
        except Exception as e:
            logger.warning(f"NQ=F 历史数据重试耗尽: {e}")
            result = None
    
    # 4. 更新缓存
    if result is not None:
        _nq_cache = result
        _nq_cache_time = datetime.now()
    
    return result


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=3, min=3, max=15),
    reraise=True
)
def _fetch_nq_realtime() -> Optional[NQFuturesData]:
    """
    实时获取 NQ=F 数据（带重试）
    
    重试策略: 最多 3 次，间隔 3s → 6s → 12s
    """
    try:
        import yfinance as yf
        
        logger.info("获取 NQ=F (纳指100期货) 实时数据...")
        
        # 请求前延时，降低被限流的概率
        time.sleep(1.0)
        
        ticker = yf.Ticker("NQ=F")
        info = ticker.fast_info
        
        current_price = info.last_price
        previous_close = info.previous_close
        
        if not current_price or not previous_close:
            logger.warning("NQ=F 数据不完整")
            return None
        
        change_pct = (current_price - previous_close) / previous_close * 100
        
        # 判断市场状态（北京时间）
        now_hour = datetime.now().hour
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
        error_msg = str(e)
        if "Rate" in error_msg or "429" in error_msg or "Too Many" in error_msg:
            logger.warning(f"NQ=F 被限流，等待重试: {e}")
            raise  # 让 tenacity 处理重试
        else:
            logger.warning(f"yfinance 获取 NQ=F 失败: {e}")
            return None  # 非限流错误直接降级


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True
)
def _fetch_nq_fallback_history() -> Optional[NQFuturesData]:
    """
    降级方案: 从 yfinance 获取 NQ=F 最近的历史收盘数据
    
    重试策略: 最多 2 次，间隔 2s → 4s
    """
    try:
        import yfinance as yf
        
        logger.info("降级: 尝试获取 NQ=F 最近历史数据...")
        
        # 请求前延时
        time.sleep(2.0)
        
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
        error_msg = str(e)
        if "Rate" in error_msg or "429" in error_msg or "Too Many" in error_msg:
            logger.warning(f"NQ=F 历史也被限流，等待重试: {e}")
            raise
        else:
            logger.error(f"NQ=F 历史数据获取失败: {e}")
            return None
