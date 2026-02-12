"""
FundPilot 统一 HTTP 客户端
提供反爬虫对抗能力：UA 轮换、Referer 伪装、请求延时、重试机制
"""

import random
import time
from typing import Optional
from functools import wraps

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.logger import get_logger

logger = get_logger("http_client")

# ============================================================
# User-Agent 池
# ============================================================

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Mobile Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]

# ============================================================
# Referer 配置
# ============================================================

REFERER_MAP = {
    "eastmoney": "http://fund.eastmoney.com/",
    "sina": "http://finance.sina.com.cn/",
    "tiantian": "http://fundgz.1234567.com.cn/",
    "default": "https://www.baidu.com/",
}

# ============================================================
# 请求控制
# ============================================================

# 最小请求间隔（秒）
MIN_REQUEST_INTERVAL = 0.3
# 最大请求间隔（秒）
MAX_REQUEST_INTERVAL = 0.8

# 上次请求时间
_last_request_time: float = 0


def get_random_ua() -> str:
    """获取随机 User-Agent"""
    return random.choice(USER_AGENTS)


def get_referer(source: str = "default") -> str:
    """获取 Referer"""
    return REFERER_MAP.get(source, REFERER_MAP["default"])


def _rate_limit():
    """请求频率限制"""
    global _last_request_time
    
    now = time.time()
    elapsed = now - _last_request_time
    
    # 随机间隔，避免固定模式
    interval = random.uniform(MIN_REQUEST_INTERVAL, MAX_REQUEST_INTERVAL)
    
    if elapsed < interval:
        sleep_time = interval - elapsed
        logger.debug(f"请求延时 {sleep_time:.2f}s")
        time.sleep(sleep_time)
    
    _last_request_time = time.time()


def build_headers(
    source: str = "default",
    extra_headers: Optional[dict] = None
) -> dict:
    """
    构建请求头
    
    Args:
        source: 数据源标识（eastmoney/sina/tiantian）
        extra_headers: 额外的请求头
    
    Returns:
        完整的请求头字典
    """
    headers = {
        "User-Agent": get_random_ua(),
        "Referer": get_referer(source),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    
    if extra_headers:
        headers.update(extra_headers)
    
    return headers


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
    reraise=True
)
def get(
    url: str,
    source: str = "default",
    timeout: int = 10,
    encoding: Optional[str] = None,
    rate_limit: bool = True,
    **kwargs
) -> requests.Response:
    """
    发起 GET 请求（带反爬虫措施）
    
    Args:
        url: 请求 URL
        source: 数据源标识
        timeout: 超时时间（秒）
        encoding: 响应编码（如 gbk）
        rate_limit: 是否启用请求频率限制
        **kwargs: 传递给 requests.get 的其他参数
    
    Returns:
        Response 对象
    
    Raises:
        requests.RequestException: 请求失败
    """
    if rate_limit:
        _rate_limit()
    
    headers = build_headers(source, kwargs.pop("headers", None))
    
    logger.debug(f"GET {url[:80]}... UA={headers['User-Agent'][:30]}...")
    
    response = requests.get(url, headers=headers, timeout=timeout, **kwargs)
    response.raise_for_status()
    
    if encoding:
        response.encoding = encoding
    
    return response


def get_text(
    url: str,
    source: str = "default",
    timeout: int = 10,
    encoding: Optional[str] = None,
    rate_limit: bool = True,
    **kwargs
) -> Optional[str]:
    """
    发起 GET 请求并返回文本（失败返回 None）
    
    Args:
        url: 请求 URL
        source: 数据源标识
        timeout: 超时时间（秒）
        encoding: 响应编码
        rate_limit: 是否启用请求频率限制
    
    Returns:
        响应文本，失败返回 None
    """
    try:
        response = get(url, source, timeout, encoding, rate_limit, **kwargs)
        return response.text
    except Exception as e:
        logger.warning(f"请求失败 {url[:50]}...: {e}")
        return None


# ============================================================
# 请求统计（用于失败率监控）
# ============================================================

class RequestStats:
    """请求统计"""
    
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
    
    def record_success(self):
        self.total += 1
        self.success += 1
    
    def record_failure(self):
        self.total += 1
        self.failed += 1
    
    def get_failure_rate(self) -> float:
        """获取失败率 (0-100)"""
        if self.total == 0:
            return 0.0
        return (self.failed / self.total) * 100
    
    def reset(self):
        self.total = 0
        self.success = 0
        self.failed = 0


# 全局统计实例
request_stats = RequestStats()
