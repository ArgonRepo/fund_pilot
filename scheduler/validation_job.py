"""
FundPilot-AI 决策验证任务
检查历史决策的实际收益，验证策略有效性

验证周期: T+3 (决策后3个交易日)
成功标准 (按决策类型):
- 双倍补仓: T+3 >= 0% (权益), >= -0.2% (债券)
- 正常定投: T+3 >= -3% (权益), >= -0.8% (债券)
- 暂停定投: T+3 <= +1% (权益), <= +0.3% (债券)
- 观望: 不纳入统计
"""

from datetime import datetime
from typing import Optional

from core.logger import get_logger
from core.database import get_database
from data.fund_valuation import fetch_fund_valuation
from scheduler.calendar import should_run_task

logger = get_logger("validation")


# 成功阈值配置 (按资产类型)
SUCCESS_THRESHOLDS = {
    # 权益类: 波动大，阈值宽
    "GOLD_ETF": {
        "双倍补仓": (0, None),      # T+5 >= 0%
        "正常定投": (-3, None),     # T+5 >= -3%
        "暂停定投": (None, 1),      # T+5 <= 1%
    },
    "COMMODITY_CYCLE": {
        "双倍补仓": (0, None),
        "正常定投": (-3, None),
        "暂停定投": (None, 1),
    },
    # 债券类: 波动小，阈值紧
    "BOND_ENHANCED": {
        "双倍补仓": (-0.2, None),   # T+5 >= -0.2%
        "正常定投": (-0.8, None),   # T+5 >= -0.8%
        "暂停定投": (None, 0.3),    # T+5 <= 0.3%
    },
    "BOND_PURE": {
        "双倍补仓": (-0.2, None),
        "正常定投": (-0.5, None),   # 纯债更严格
        "暂停定投": (None, 0.2),
    },
}

# 默认阈值 (未知资产类型)
DEFAULT_THRESHOLDS = {
    "双倍补仓": (0, None),
    "正常定投": (-2, None),
    "暂停定投": (None, 1),
}


def evaluate_decision_success(
    decision: str,
    actual_return: float,
    asset_class: Optional[str] = None
) -> Optional[bool]:
    """
    评估决策是否成功
    
    Args:
        decision: 决策类型 (双倍补仓/正常定投/暂停定投/观望)
        actual_return: T+5 实际收益率 (%)
        asset_class: 资产类型
    
    Returns:
        True=成功, False=失败, None=不适用(观望)
    """
    # 观望不纳入统计
    if decision == "观望":
        return None
    
    # 获取阈值
    thresholds = SUCCESS_THRESHOLDS.get(asset_class, DEFAULT_THRESHOLDS)
    threshold = thresholds.get(decision)
    
    if not threshold:
        logger.warning(f"未知决策类型: {decision}")
        return None
    
    min_return, max_return = threshold
    
    # 判断成功条件
    if min_return is not None and max_return is not None:
        return min_return <= actual_return <= max_return
    elif min_return is not None:
        return actual_return >= min_return
    elif max_return is not None:
        return actual_return <= max_return
    
    return None


def run_validation_task():
    """
    运行决策验证任务
    
    流程:
    1. 查询 T+5 天前未验证的决策
    2. 获取当前净值计算实际收益
    3. 判断决策成功/失败
    4. 更新数据库
    """
    # 非交易日不运行
    if not should_run_task():
        logger.info("非交易日，跳过验证任务")
        return
    
    logger.info("=" * 50)
    logger.info("开始决策验证任务")
    
    db = get_database()
    
    # 获取待验证的决策 (T+3)
    pending = db.get_pending_validations(days_ago=3)
    
    if not pending:
        logger.info("没有待验证的决策记录")
        return
    
    logger.info(f"找到 {len(pending)} 条待验证决策")
    
    validated_count = 0
    success_count = 0
    
    for record in pending:
        fund_code = record["fund_code"]
        fund_name = record.get("fund_name", fund_code)
        decision = record["ai_decision"]
        decision_nav = record["decision_nav"]
        asset_class = record.get("asset_class")
        decision_id = record["id"]
        
        # 获取当前净值
        valuation = fetch_fund_valuation(fund_code)
        if not valuation:
            logger.warning(f"基金 {fund_code} 获取净值失败，跳过验证")
            continue
        
        # 计算实际收益率
        current_nav = valuation.estimate_nav
        actual_return = (current_nav - decision_nav) / decision_nav * 100
        
        # 评估成功/失败
        is_success = evaluate_decision_success(decision, actual_return, asset_class)
        
        # 更新数据库
        if is_success is not None:
            db.update_decision_validation(
                decision_id=decision_id,
                actual_nav_t5=current_nav,
                actual_return_t5=actual_return,
                is_success=is_success
            )
            validated_count += 1
            if is_success:
                success_count += 1
            
            result_emoji = "✅" if is_success else "❌"
            logger.info(
                f"{result_emoji} {fund_name}: {decision} -> T+5 {actual_return:+.2f}% "
                f"({'成功' if is_success else '失败'})"
            )
        else:
            # 观望决策也标记为已验证
            db.update_decision_validation(
                decision_id=decision_id,
                actual_nav_t5=current_nav,
                actual_return_t5=actual_return,
                is_success=False  # 观望不计入成功
            )
            logger.info(f"⏸️ {fund_name}: 观望 -> T+5 {actual_return:+.2f}% (不纳入统计)")
    
    logger.info(f"验证完成: {validated_count} 条, 成功 {success_count} 条")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_validation_task()
