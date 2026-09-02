"""
FundPilot 持仓穿透分析模块
获取基金重仓股信息及实时行情（使用腾讯财经接口，云服务器兼容）
"""

import time
from dataclasses import dataclass
from typing import Optional

import akshare as ak

from core.logger import get_logger
from core.database import get_database
from core.config import FundConfig
from core.http_client import get_text, request_stats

logger = get_logger("holdings")

# 腾讯财经股票行情 API（云服务器可靠访问）
TENCENT_QUOTE_API = "http://qt.gtimg.cn/q={codes}"

# AKShare 请求间隔（秒）
AKSHARE_REQUEST_INTERVAL = 1.0


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


def _batch_fetch_stock_quotes(stock_codes: list[str]) -> dict[str, Optional[float]]:
    """
    批量获取股票实时涨跌幅（通过腾讯财经接口，一次请求）

    Args:
        stock_codes: 股票代码列表（如 ["sh600519", "sz000001"]）

    Returns:
        {stock_code: 涨跌幅} 字典
    """
    results = {}
    if not stock_codes:
        return results

    url = TENCENT_QUOTE_API.format(codes=",".join(stock_codes))

    try:
        text = get_text(url, source="default", timeout=10, encoding="gbk")

        if not text:
            return {code: None for code in stock_codes}

        for line in text.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line or '""' in line:
                continue

            try:
                # 格式: v_sh600519="1~贵州茅台~600519~1800.00~1790.00~..."
                prefix = line.split("=")[0].strip()
                code = prefix.split("_")[-1]  # sh600519

                data = line.split('"')[1].split("~")
                if len(data) < 5:
                    continue

                yesterday_close = float(data[4])
                current_price = float(data[3])

                if yesterday_close == 0:
                    results[code] = None
                    continue

                change = (current_price - yesterday_close) / yesterday_close * 100
                results[code] = round(change, 2)

            except Exception:
                continue

    except Exception as e:
        logger.warning(f"批量获取股票行情失败: {e}")

    # 补充未获取到的代码
    for code in stock_codes:
        if code not in results:
            results[code] = None

    return results


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

        # AkShare 请求间隔
        time.sleep(AKSHARE_REQUEST_INTERVAL)

        # 尝试获取 ETF 持仓
        try:
            df = ak.fund_portfolio_hold_em(symbol=target_code, date="")
        except Exception:
            # 如果失败，尝试开放式基金持仓
            time.sleep(AKSHARE_REQUEST_INTERVAL)
            df = ak.fund_portfolio_hold_em(symbol=fund_code, date="")

        if df is None or df.empty:
            request_stats.record_failure()
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

        request_stats.record_success()
        logger.info(f"基金 {target_code} 获取到 {len(result)} 只重仓股")
        return result

    except Exception as e:
        request_stats.record_failure()
        logger.error(f"获取基金 {fund_code} 持仓失败: {e}")
        return []


def fetch_holdings_weighted_change(fund_code: str, underlying_etf: Optional[str] = None) -> Optional[tuple[float, float]]:
    """
    持仓加权盘中涨跌（估值引擎宕机时的推算口径，与养基宝等工具同原理）

    取最新一期前十大重仓股，按「占净值比例 × 实时涨跌」加权求和；
    未披露部分按 0 处理（保守口径，倾向低估波动，季报调仓滞后也会引入误差）。

    Args:
        fund_code: 基金代码
        underlying_etf: ETF 联接基金的底层 ETF 代码（穿透取 ETF 的股票持仓）

    Returns:
        (加权涨跌%, 覆盖权重%) 或 None（持仓/行情均不可用时）
    """
    try:
        time.sleep(AKSHARE_REQUEST_INTERVAL)
        df = ak.fund_portfolio_hold_em(symbol=underlying_etf or fund_code, date="")

        if df is None or df.empty:
            logger.warning(f"持仓推算: 基金 {fund_code} 无持仓数据")
            return None

        # AkShare 返回多期合并数据，按「季度」列取最新一期
        if "季度" in df.columns:
            latest_period = df["季度"].iloc[0]
            df = df[df["季度"] == latest_period]

        holdings: list[tuple[str, str, float]] = []
        for _, row in df.head(10).iterrows():
            code = str(row.get("股票代码", "")).strip()
            name = str(row.get("股票名称", "")).strip()
            try:
                weight = float(row.get("占净值比例", 0) or 0)
            except (TypeError, ValueError):
                weight = 0.0
            if code and name and weight > 0:
                holdings.append((code, name, weight))

        if not holdings:
            return None

        # 批量获取重仓股实时行情（腾讯，一次请求）
        norm_codes = [_normalize_stock_code(c) for c, _, _ in holdings]
        quotes = _batch_fetch_stock_quotes(norm_codes)

        weighted = 0.0
        covered = 0.0
        for (code, name, weight), norm_code in zip(holdings, norm_codes):
            change = quotes.get(norm_code)
            if change is not None:
                weighted += weight * change / 100.0
                covered += weight

        # 全部行情缺失（如债基持仓为债券，无股票行情）视为不可推算
        if covered <= 0:
            logger.info(f"持仓推算: 基金 {fund_code} 重仓股均无实时行情（可能为债券持仓），跳过")
            return None

        logger.info(f"持仓推算: 基金 {fund_code} 加权涨跌 {weighted:+.2f}%（覆盖净值 {covered:.1f}%）")
        return (weighted, covered)

    except Exception as e:
        logger.warning(f"持仓推算: 基金 {fund_code} 失败: {e}")
        return None


def get_holdings_with_quotes(fund_config: FundConfig) -> Optional[HoldingsInsight]:
    """
    获取持仓及实时行情

    Args:
        fund_config: 基金配置

    Returns:
        HoldingsInsight 对象
    """
    from datetime import datetime

    db = get_database()

    # 持仓缓存过期时间（90天，持仓通常每季度更新）
    HOLDINGS_CACHE_TTL_DAYS = 90

    # 检查缓存是否过期
    cache_updated_at = db.get_holdings_updated_at(fund_config.code)
    cache_expired = True

    if cache_updated_at:
        age_days = (datetime.now() - cache_updated_at).days
        cache_expired = age_days > HOLDINGS_CACHE_TTL_DAYS
        if cache_expired:
            logger.info(f"基金 {fund_config.code} 持仓缓存已过期 ({age_days} 天)，刷新中...")

    # 获取持仓数据
    holdings_data = None

    if not cache_expired:
        # 缓存有效，使用缓存
        holdings_data = db.get_holdings(fund_config.code)

    if not holdings_data:
        # 缓存过期或不存在，从 API 获取
        holdings_data = fetch_fund_holdings(fund_config.code, fund_config.underlying_etf)
        if holdings_data:
            db.save_holdings(fund_config.code, holdings_data)

    if not holdings_data:
        return None

    # 批量获取所有重仓股行情（一次请求）
    norm_codes = [_normalize_stock_code(code) for code, _, _ in holdings_data]
    logger.info(f"批量获取 {len(norm_codes)} 只重仓股行情...")
    quotes = _batch_fetch_stock_quotes(norm_codes)

    holdings = []
    for (code, name, weight), norm_code in zip(holdings_data, norm_codes):
        change = quotes.get(norm_code)
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
