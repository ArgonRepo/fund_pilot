"""
FundPilot 市场环境数据模块
获取大盘指数实时行情（使用腾讯财经接口，云服务器兼容）
"""

from dataclasses import dataclass
from typing import Optional

from core.logger import get_logger
from core.http_client import get_text, request_stats

logger = get_logger("market")

# 腾讯财经行情 API（云服务器可靠访问）
TENCENT_QUOTE_API = "http://qt.gtimg.cn/q={codes}"

# 常用指数代码（腾讯格式）
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


def _parse_tencent_quote(line: str) -> Optional[tuple[str, str, float, float]]:
    """
    解析腾讯行情数据

    腾讯格式: v_sh000001="1~上证指数~000001~3261.56~3256.26~...";
    字段: 市场~名称~代码~当前价~昨收~今开~...~涨跌幅(32)~...

    Returns:
        (代码, 名称, 当前价, 涨跌幅) 或 None
    """
    try:
        if "=" not in line or '""' in line:
            return None

        # 提取代码前缀和数据
        prefix = line.split("=")[0].strip()  # v_sh000001
        code = prefix.split("_")[-1]  # sh000001

        data = line.split('"')[1].split("~")
        if len(data) < 33:
            return None

        name = data[1]
        current = float(data[3])
        yesterday_close = float(data[4])

        if yesterday_close == 0:
            return None

        change = (current - yesterday_close) / yesterday_close * 100
        return (code, name, current, round(change, 2))

    except Exception as e:
        logger.debug(f"解析行情数据失败: {e}")
        return None


def fetch_market_indices() -> dict[str, MarketIndex]:
    """
    获取市场指数行情（通过腾讯财经接口）

    Returns:
        {指数名称: MarketIndex}
    """
    codes = list(INDEX_CODES.values())
    url = TENCENT_QUOTE_API.format(codes=",".join(codes))

    try:
        text = get_text(url, source="default", timeout=5, encoding="gbk")

        if not text:
            request_stats.record_failure()
            logger.warning("获取市场指数失败")
            return {}

        results = {}
        for line in text.strip().split(";"):
            line = line.strip()
            if not line:
                continue

            parsed = _parse_tencent_quote(line)
            if not parsed:
                continue

            code, idx_name, current, change = parsed

            # 匹配到我们关注的指数
            for display_name, idx_code in INDEX_CODES.items():
                if code == idx_code:
                    results[display_name] = MarketIndex(
                        name=display_name,
                        code=code,
                        current=current,
                        change=change
                    )
                    break

        request_stats.record_success()
        logger.info(f"获取到 {len(results)} 个市场指数")
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
