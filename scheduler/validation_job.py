"""
FundPilot-AI 双轨决策验证任务
检查历史决策的实际收益，验证策略有效性

双轨验证:
- T+1 方向验证: 判断趋势方向是否正确
- T+5 收益验证: 最终收益是否符合预期

成功标准 (按决策类型):
T+1 方向:
- 双倍补仓: 方向正确 = 涨了
- 正常定投: 方向正确 = 涨了 或 跌幅<1%
- 暂停定投: 方向正确 = 跌了

T+5 收益:
- 双倍补仓: 收益 >= 0% (权益), >= -0.2% (债券)
- 正常定投: 收益 >= -3% (权益), >= -0.8% (债券)
- 暂停定投: 收益 <= +1% (权益), <= +0.3% (债券)
- 观望: 不纳入统计
"""

from datetime import datetime
from typing import Optional

from core.logger import get_logger
from core.database import get_database
from data.fund_valuation import fetch_fund_valuation
from scheduler.calendar import should_run_task

logger = get_logger("validation")


# T+5 成功阈值配置 (按资产类型)
T5_SUCCESS_THRESHOLDS = {
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
        "正常定投": (-0.5, None),
        "暂停定投": (None, 0.2),
    },
    # 美股QDII: 波动大 + 净值滞后，阈值更宽
    "US_EQUITY_INDEX": {
        "双倍补仓": (0, None),      # T+5 >= 0%
        "正常定投": (-4, None),     # T+5 >= -4% (美股波动大)
        "暂停定投": (None, 2),      # T+5 <= 2%
    },
}

DEFAULT_T5_THRESHOLDS = {
    "双倍补仓": (0, None),
    "正常定投": (-2, None),
    "暂停定投": (None, 1),
}


def evaluate_t1_direction(decision: str, actual_return: float) -> Optional[bool]:
    """
    评估 T+1 方向是否正确
    
    逻辑:
    - 双倍补仓: 预判涨 → 实际涨了 = 正确
    - 正常定投: 中性 → 涨了或小跌<1% = 正确
    - 暂停定投: 预判跌 → 实际跌了 = 正确
    """
    if decision == "观望":
        return None
    
    if decision == "双倍补仓":
        return actual_return >= 0  # 涨了 or 平
    elif decision == "正常定投":
        return actual_return >= -1.0  # 涨了或小跌
    elif decision == "暂停定投":
        return actual_return < 0  # 跌了
    
    return None


def evaluate_t5_success(
    decision: str,
    actual_return: float,
    asset_class: Optional[str] = None
) -> Optional[bool]:
    """
    评估 T+5 投资是否成功
    """
    if decision == "观望":
        return None
    
    thresholds = T5_SUCCESS_THRESHOLDS.get(asset_class, DEFAULT_T5_THRESHOLDS)
    threshold = thresholds.get(decision)
    
    if not threshold:
        logger.warning(f"未知决策类型: {decision}")
        return None
    
    min_return, max_return = threshold
    
    if min_return is not None and max_return is not None:
        return min_return <= actual_return <= max_return
    elif min_return is not None:
        return actual_return >= min_return
    elif max_return is not None:
        return actual_return <= max_return
    
    return None


def run_validation_task():
    """
    运行双轨决策验证任务
    
    流程:
    1. T+1 方向验证: 查询1天前未T+1验证的决策
    2. T+5 收益验证: 查询5天前未T+5验证的决策
    """
    # 非交易日不运行
    if not should_run_task():
        logger.info("非交易日，跳过验证任务")
        return
    
    logger.info("=" * 50)
    logger.info("开始双轨决策验证任务")
    
    db = get_database()
    
    # ========== T+1 方向验证 ==========
    pending_t1 = db.get_pending_t1_validations(days_ago=1)
    
    if pending_t1:
        logger.info(f"[T+1] 找到 {len(pending_t1)} 条待方向验证决策")
        
        for record in pending_t1:
            fund_code = record["fund_code"]
            fund_name = record.get("fund_name", fund_code)
            decision = record["ai_decision"]
            decision_nav = record["decision_nav"]
            decision_id = record["id"]
            
            # 获取当前净值
            valuation = fetch_fund_valuation(fund_code)
            if not valuation:
                logger.warning(f"[T+1] 基金 {fund_code} 获取净值失败，跳过")
                continue
            
            current_nav = valuation.estimate_nav
            actual_return = (current_nav - decision_nav) / decision_nav * 100
            
            direction_correct = evaluate_t1_direction(decision, actual_return)
            
            if direction_correct is not None:
                db.update_t1_validation(
                    decision_id=decision_id,
                    nav_t1=current_nav,
                    return_t1=actual_return,
                    direction_correct=direction_correct
                )
                emoji = "✅" if direction_correct else "❌"
                arrow = "↑" if actual_return >= 0 else "↓"
                logger.info(f"{emoji} [T+1] {fund_name}: {decision} → {arrow}{actual_return:+.2f}%")
    else:
        logger.info("[T+1] 无待验证决策")
    
    # ========== T+5 收益验证 ==========
    pending_t5 = db.get_pending_t5_validations(days_ago=5)
    
    if pending_t5:
        logger.info(f"[T+5] 找到 {len(pending_t5)} 条待收益验证决策")
        
        for record in pending_t5:
            fund_code = record["fund_code"]
            fund_name = record.get("fund_name", fund_code)
            decision = record["ai_decision"]
            decision_nav = record["decision_nav"]
            asset_class = record.get("asset_class")
            decision_id = record["id"]
            
            valuation = fetch_fund_valuation(fund_code)
            if not valuation:
                logger.warning(f"[T+5] 基金 {fund_code} 获取净值失败，跳过")
                continue
            
            current_nav = valuation.estimate_nav
            actual_return = (current_nav - decision_nav) / decision_nav * 100
            
            is_success = evaluate_t5_success(decision, actual_return, asset_class)
            
            if is_success is not None:
                db.update_t5_validation(
                    decision_id=decision_id,
                    nav_t5=current_nav,
                    return_t5=actual_return,
                    is_success=is_success
                )
                emoji = "✅" if is_success else "❌"
                logger.info(f"{emoji} [T+5] {fund_name}: {decision} → {actual_return:+.2f}%")
    else:
        logger.info("[T+5] 无待验证决策")
    
    logger.info("双轨验证任务完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_validation_task()
