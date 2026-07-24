"""
FundPilot 实时估值获取模块
从东方财富「净值估算」接口获取盘中实时估值

数据源: api.fund.eastmoney.com/FundGuZhi/GetFundGZList
- 与已下线的天天基金 fundgz.1234567.com.cn 同源（天天基金属东方财富旗下，共用估值引擎）
- 分页拉取全市场基金估值表（全市场约 2.3 万只），模块级缓存（TTL 5 分钟），整轮任务只请求 1 次

字段映射（与 FundValuation 数据类保持一致）:
  gsz   -> estimate_nav     盘中预估净值
  gszzl -> estimate_change  预估涨跌幅 (%)
  dwjz  -> nav              基准（上一确认）单位净值
  gxrq  -> 估算交易日，用于新鲜度判断

时效性说明:
  该接口仅返回估算「日期」(gxrq)，不含分钟级时间戳（原天天基金 JSONP 的 gztime 已随接口下线消失）。
  因此新鲜度检测由"分钟级"退化为"日期级"：估算交易日不是今天即视为过期。
  预警(12:30)/决策(14:40)均在 A 股盘中触发，此时估值表为盘中实时刷新状态。
"""

from datetime import datetime, date
from dataclasses import dataclass
from typing import Optional

from core.logger import get_logger
from core.http_client import get, request_stats

logger = get_logger("fund_valuation")

# 东方财富「净值估算」接口（全量基金估值表）
FUND_GZ_API = "https://api.fund.eastmoney.com/FundGuZhi/GetFundGZList"


@dataclass
class FundValuation:
    """基金实时估值数据"""
    fund_code: str           # 基金代码
    fund_name: str           # 基金名称
    nav: float               # 基准（上一确认）单位净值
    estimate_nav: float      # 预估净值
    estimate_change: float   # 预估涨跌幅 (%)
    estimate_time: datetime  # 估值时间（估算交易日）
    is_stale: bool = False   # 数据是否失效（估算交易日非今日）


# ============================================================
# 全量估值表会话级缓存（一次任务周期内只拉取一次）
# ============================================================

_estimate_table: Optional[dict[str, dict]] = None
_estimate_table_time: Optional[datetime] = None
_estimate_table_day: Optional[str] = None  # 估算交易日 gxrq
_CACHE_TTL_SECONDS = 300  # 缓存有效期 5 分钟

# 估值表分页参数
# 全市场基金约 2.3 万只，单页 pageSize 设为 5 万通常一页即可取全；
# 分页 + 不足一页即停 作为未来基金数增长的自适应与截断防御。
_PAGE_SIZE = 50000
_MAX_PAGES = 3  # 安全上限：3 页 × 5 万 = 15 万，远超现实基金总数


def clear_estimate_cache():
    """清除估值表缓存（供测试或强制刷新使用）"""
    global _estimate_table, _estimate_table_time, _estimate_table_day
    _estimate_table = None
    _estimate_table_time = None
    _estimate_table_day = None


def _is_cache_valid() -> bool:
    """检查缓存是否在有效期内"""
    if _estimate_table is None or _estimate_table_time is None:
        return False
    age = (datetime.now() - _estimate_table_time).total_seconds()
    return age < _CACHE_TTL_SECONDS


def _fetch_estimate_table() -> Optional[tuple[dict[str, dict], str]]:
    """
    拉取东方财富全量基金估值表（带会话级缓存）

    Returns:
        (基金代码 -> 行数据, 估算交易日 gxrq) 或 None
    """
    global _estimate_table, _estimate_table_time, _estimate_table_day

    if _is_cache_valid():
        return _estimate_table, _estimate_table_day

    logger.info("拉取东方财富基金盘中估值表（分页）...")

    extra_headers = {"Referer": "https://fund.eastmoney.com/"}

    table: dict[str, dict] = {}
    gxrq: Optional[str] = None

    for page_index in range(1, _MAX_PAGES + 1):
        params = {
            "type": "1",          # 全部基金
            "sort": "3",
            "orderType": "desc",
            "canbuy": "0",
            "pageIndex": str(page_index),
            "pageSize": str(_PAGE_SIZE),
            "_": str(int(datetime.now().timestamp() * 1000)),
        }

        try:
            response = get(
                FUND_GZ_API,
                source="eastmoney",
                timeout=15,
                params=params,
                headers=extra_headers,
            )
            payload = response.json()
        except Exception as e:
            logger.error(f"获取基金估值表失败（第{page_index}页）: {e}")
            return None

        data = payload.get("Data") or {}
        rows = data.get("list") or []

        # gxrq（估算交易日）各页一致，仅取首页
        if gxrq is None:
            gxrq = data.get("gxrq") or datetime.now().strftime("%Y-%m-%d")

        if not rows:
            # 空页：已无更多数据
            break

        # 构建代码索引（bzdm 为基金代码）
        for row in rows:
            code = str(row.get("bzdm") or "").strip()
            if code:
                table[code] = row

        # 本页不足一页 → 已到末页，停止翻页
        if len(rows) < _PAGE_SIZE:
            break

        if page_index == _MAX_PAGES:
            # 最后一页仍满页：说明实际基金数超过 _MAX_PAGES × _PAGE_SIZE，仍有截断
            logger.warning(
                f"估值表翻页已达上限（{_MAX_PAGES}页，累计 {len(table)} 只），"
                f"可能仍有截断，建议调大 _MAX_PAGES"
            )

    if gxrq is None:
        gxrq = datetime.now().strftime("%Y-%m-%d")

    if not table:
        logger.warning("基金估值表为空")
        return None

    _estimate_table = table
    _estimate_table_time = datetime.now()
    _estimate_table_day = gxrq
    logger.info(f"基金估值表已缓存: {len(table)} 只基金（估算交易日 {gxrq}）")
    return table, gxrq


def _parse_pct(value) -> Optional[float]:
    """解析 '8.94%' / '---' / nan 为 float"""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ("---", "nan", "None", "--"):
        return None
    try:
        return float(s.replace("%", "").replace(",", "").strip())
    except ValueError:
        return None


def _parse_float(value) -> Optional[float]:
    """解析 '3.5937' / '---' / nan 为 float"""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ("---", "nan", "None", "--"):
        return None
    try:
        return float(s.replace(",", "").strip())
    except ValueError:
        return None


def fetch_fund_valuation(fund_code: str) -> Optional[FundValuation]:
    """
    获取基金实时估值（从东方财富全量估值表查询单只基金）

    Args:
        fund_code: 基金代码

    Returns:
        FundValuation 对象，失败返回 None
    """
    fund_code = str(fund_code).strip().zfill(6)

    result = _fetch_estimate_table()
    if result is None:
        request_stats.record_failure()
        return None

    table, gxrq = result
    row = table.get(fund_code)
    if not row:
        logger.warning(f"基金 {fund_code} 不在估值表中（可能为 QDII/未披露估值/已下线）")
        request_stats.record_failure()
        return None

    estimate_nav = _parse_float(row.get("gsz"))
    estimate_change = _parse_pct(row.get("gszzl"))
    nav = _parse_float(row.get("dwjz"))

    if estimate_nav is None or estimate_change is None:
        logger.warning(
            f"基金 {fund_code} 估值数据不完整: gsz={row.get('gsz')!r} gszzl={row.get('gszzl')!r}"
        )
        request_stats.record_failure()
        return None

    # 估算交易日（gxrq）不是今天 → 视为过期（接口未刷新到今日）
    try:
        est_date = datetime.strptime(gxrq, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        est_date = None

    is_stale = False
    if est_date is not None and est_date < date.today():
        is_stale = True
        logger.warning(f"基金 {fund_code} 估值未刷新至今日（估算交易日={gxrq}）")

    estimate_time = datetime.combine(est_date, datetime.now().time()) if est_date else datetime.now()

    request_stats.record_success()

    valuation = FundValuation(
        fund_code=fund_code,
        fund_name=str(row.get("jjjc") or "").strip(),
        nav=nav if nav is not None else estimate_nav,
        estimate_nav=estimate_nav,
        estimate_change=estimate_change,
        estimate_time=estimate_time,
        is_stale=is_stale,
    )
    logger.info(
        f"基金 {fund_code} 估值: {valuation.estimate_change:+.2f}% "
        f"预估净值={valuation.estimate_nav:.4f} 基准净值={valuation.nav:.4f} "
        f"(估算日={gxrq}{'，已过期' if is_stale else ''})"
    )
    return valuation


def fetch_multiple_valuations(fund_codes: list[str]) -> dict[str, Optional[FundValuation]]:
    """
    批量获取多只基金估值（复用同一份估值表缓存）

    Args:
        fund_codes: 基金代码列表

    Returns:
        {fund_code: FundValuation} 字典
    """
    return {code: fetch_fund_valuation(code) for code in fund_codes}
