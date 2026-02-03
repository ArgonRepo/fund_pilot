"""
模拟回测数据脚本 (v3.0 双轨验证)
用于测试 T+1 方向 + T+5 收益 双轨验证展示

运行: python scripts/simulate_backtest.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import datetime, timedelta
from core.database import get_database
from strategy.asset_config import AssetClass
from notification.email_template import (
    generate_combined_email_html,
    FundReport
)


def mock_db_data():
    """模拟历史决策数据 (双轨验证)"""
    db = get_database()
    
    # 清空旧数据
    with db.get_connection() as conn:
        conn.execute("DELETE FROM decision_log")
    print("已清空现有决策日志...")
    
    # 基金配置
    funds = [
        {
            "code": "000216",
            "name": "华安黄金ETF联接A",
            "type": "ETF_Feeder",
            "asset_class": AssetClass.GOLD_ETF.value,
            "t1_accuracy": 0.75,  # 高方向准确率
            "t5_accuracy": 0.80   # 高收益成功率
        },
        {
            "code": "004432",
            "name": "南方有色金属ETF联接A",
            "type": "ETF_Feeder",
            "asset_class": AssetClass.COMMODITY_CYCLE.value,
            "t1_accuracy": 0.55,  # 一般方向准确率
            "t5_accuracy": 0.50   # 一般收益成功率
        }
    ]
    
    decision_types = ["双倍补仓", "正常定投", "暂停定投", "正常定投"]  # 加权分布
    
    for fund in funds:
        print(f"\n正在生成 {fund['name']} 历史数据 (T+1准确率={fund['t1_accuracy']:.0%}, T+5成功率={fund['t5_accuracy']:.0%})...")
        
        base_nav = 1.0 + random.uniform(-0.1, 0.2)
        
        # 生成最近 15 条决策记录
        for i in range(15, 0, -1):
            decision = random.choice(decision_types)
            if decision == "观望":
                continue
            
            decision_time = datetime.now() - timedelta(days=i)
            nav = base_nav + random.uniform(-0.02, 0.02)
            
            # 保存决策记录
            db.save_decision_log(
                fund_code=fund["code"],
                fund_name=fund["name"],
                fund_type=fund["type"],
                asset_class=fund["asset_class"],
                decision_time=decision_time,
                estimate_change=random.uniform(-1.5, 1.5),
                percentile_250=random.uniform(20, 80),
                ma_60=random.uniform(90, 110),
                ai_decision=decision,
                decision_nav=nav
            )
            
            # 获取刚插入的记录 ID
            with db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT id FROM decision_log WHERE fund_code = ? ORDER BY id DESC LIMIT 1",
                    (fund["code"],)
                )
                row = cursor.fetchone()
                if not row:
                    continue
                decision_id = row["id"]
            
            # T+1 方向验证 (如果决策时间超过1天)
            if i > 1:
                ret_t1 = random.uniform(-2.0, 2.0)
                
                # 根据设定的准确率模拟方向正确性
                if random.random() < fund["t1_accuracy"]:
                    # 正确的方向
                    if decision == "双倍补仓":
                        ret_t1 = abs(ret_t1) if ret_t1 < 0 else ret_t1  # 确保是涨
                    elif decision == "暂停定投":
                        ret_t1 = -abs(ret_t1) if ret_t1 > 0 else ret_t1  # 确保是跌
                    # 正常定投: 大多数情况都算对
                    direction_correct = True
                else:
                    # 错误的方向
                    if decision == "双倍补仓":
                        ret_t1 = -abs(ret_t1)  # 结果跌了
                    elif decision == "暂停定投":
                        ret_t1 = abs(ret_t1)  # 结果涨了
                    direction_correct = False
                
                nav_t1 = nav * (1 + ret_t1 / 100)
                db.update_t1_validation(
                    decision_id=decision_id,
                    nav_t1=nav_t1,
                    return_t1=ret_t1,
                    direction_correct=direction_correct
                )
            
            # T+5 收益验证 (如果决策时间超过5天)
            if i > 5:
                ret_t5 = random.uniform(-3.0, 3.0)
                
                # 根据设定的成功率模拟
                if random.random() < fund["t5_accuracy"]:
                    # 成功
                    if decision == "双倍补仓":
                        ret_t5 = abs(ret_t5)  # 正收益
                    elif decision == "正常定投":
                        ret_t5 = max(ret_t5, -2.0)  # 不太差
                    elif decision == "暂停定投":
                        ret_t5 = -abs(ret_t5)  # 负收益 (避开了下跌)
                    is_success = True
                else:
                    # 失败
                    if decision == "双倍补仓":
                        ret_t5 = -abs(ret_t5)  # 负收益
                    elif decision == "暂停定投":
                        ret_t5 = abs(ret_t5)  # 正收益 (错过了上涨)
                    is_success = False
                
                nav_t5 = nav * (1 + ret_t5 / 100)
                db.update_t5_validation(
                    decision_id=decision_id,
                    nav_t5=nav_t5,
                    return_t5=ret_t5,
                    is_success=is_success
                )
    
    print("\n数据库 Mock 完成。")


def generate_test_report():
    """生成测试报告"""
    # 构造 FundReport 数据 (使用实际的字段)
    reports = [
        FundReport(
            fund_code="000216",
            fund_name="华安黄金ETF联接A",
            fund_type="ETF_Feeder",
            estimate_change=0.32,
            percentile_250=58.9,
            ma_deviation=5.2,
            zone="neutral",
            decision="正常定投",
            reasoning="黄金处于中性区间，建议正常定投",
            buy_multiplier=1.0
        ),
        FundReport(
            fund_code="004432",
            fund_name="南方有色金属ETF联接A",
            fund_type="ETF_Feeder",
            estimate_change=-0.45,
            percentile_250=38.7,
            ma_deviation=-3.8,
            zone="low",
            decision="双倍补仓",
            reasoning="有色金属处于低位，建议加大投资",
            buy_multiplier=2.0
        )
    ]
    
    html = generate_combined_email_html(reports, time_str="14:45")
    
    output_path = os.path.join(os.path.dirname(__file__), "test_report.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"报告已生成: {output_path}")


if __name__ == "__main__":
    # 先重建数据库结构
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fundpilot.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print("已删除旧数据库...")
    
    mock_db_data()
    print("\n正在生成测试报告...")
    generate_test_report()
