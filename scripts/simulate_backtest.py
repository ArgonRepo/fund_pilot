import sys
import os
from datetime import datetime, timedelta
import random

# 添加项目根目录到 path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_database
from notification.email_template import generate_combined_email_html, FundReport
from strategy.asset_config import AssetClass

def mock_db_data():
    db = get_database()
    
    # 清空现有日志以避免污染
    with db.get_connection() as conn:
        conn.execute("DELETE FROM decision_log")
    
    print("已清空现有决策日志...")

    funds = [
        {"code": "000216", "name": "华安黄金ETF联接A", "type": "ETF_Feeder", "asset": "GOLD_ETF"},
        {"code": "004432", "name": "南方有色金属ETF联接A", "type": "ETF_Feeder", "asset": "COMMODITY_CYCLE"},
        {"code": "000000", "name": "招商双债增强A", "type": "Bond", "asset": "BOND_ENHANCED"},
    ]

    # 1. 华安黄金 - 高准确率 (80%)
    # 模拟 10 条，8条成功，2条失败
    print(f"正在生成 {funds[0]['name']} 历史数据 (高准确率)...")
    for i in range(12, 0, -1):
        dt = datetime.now() - timedelta(days=i*7) # 每周一条
        
        # 成功案例
        if i > 2:
            is_success = True if i % 5 != 0 else False # 模拟少量失败
            decision = "正常定投"
            ret = 1.5 if is_success else -3.0
        # 待验证案例 (最近2条)
        else:
            is_success = None
            decision = "暂停定投"
            ret = None
            
        db.save_decision_log(
            fund_code=funds[0]["code"],
            fund_name=funds[0]["name"],
            fund_type=funds[0]["type"],
            asset_class=funds[0]["asset"],
            decision_time=dt,
            estimate_change=0.5,
            percentile_250=30.0,
            ma_60=1.2,
            ai_decision=decision,
            decision_nav=1.0,
            ai_reasoning="Mock Reasoning",
            raw_context="{}"
        )
        
        # 如果不是最近2条，手动更新为已验证
        if i > 2:
            # 获取刚插入的 ID
            with db.get_connection() as conn:
                cur = conn.execute("SELECT MAX(id) FROM decision_log")
                did = cur.fetchone()[0]
            
            db.update_decision_validation(
                decision_id=did,
                actual_nav_t5=1.0 * (1 + ret/100),
                actual_return_t5=ret,
                is_success=is_success
            )

    # 2. 南方有色 - 一般准确率 (50%)
    print(f"正在生成 {funds[1]['name']} 历史数据 (一般准确率)...")
    for i in range(10, 0, -1):
        dt = datetime.now() - timedelta(days=i*5)
        
        if i > 2:
            is_success = True if i % 2 == 0 else False
            decision = "双倍补仓" if i % 3 == 0 else "正常定投"
            ret = 2.0 if is_success else -1.5
        else:
            is_success = None
            decision = "正常定投"
            ret = None
            
        db.save_decision_log(
            fund_code=funds[1]["code"],
            fund_name=funds[1]["name"],
            fund_type=funds[1]["type"],
            asset_class=funds[1]["asset"],
            decision_time=dt,
            estimate_change=-0.5,
            percentile_250=10.0,
            ma_60=-2.0,
            ai_decision=decision,
            decision_nav=1.0,
            ai_reasoning="Mock Reasoning",
            raw_context="{}"
        )
        
        if i > 2:
            with db.get_connection() as conn:
                cur = conn.execute("SELECT MAX(id) FROM decision_log")
                did = cur.fetchone()[0]
            db.update_decision_validation(did, 1.0, ret, is_success)

    print("数据库 Mock 完成。")
    return funds

def generate_report(funds):
    print("正在生成测试报告...")
    reports = []
    
    # 手动构造今日报告数据
    for f in funds:
        r = FundReport(
            fund_name=f["name"],
            fund_code=f["code"],
            fund_type=f["type"],
            decision="正常定投",
            reasoning="这是今日的模拟决策，用于展示邮件主体内容...",
            estimate_change=0.52,
            percentile_250=35.0,
            ma_deviation=-1.2,
            zone="低估区",
            holdings_summary="茅台 5%, 五粮液 3%",
            top_gainers=["茅台 +2%"],
            top_losers=["宁德 -1%"],
            chart_cid=None,
            
            # Smart fields
            warnings=["趋势向下"],
            percentile_60=30.0,
            percentile_500=40.0,
            volatility_60=15.5,
            percentile_consensus="低估",
            trend_direction="震荡",
            
            strategy_decision="正常定投",
            strategy_confidence=0.8,
            strategy_reasoning="分位低估",
            
            ai_decision="正常定投",
            ai_confidence="高",
            ai_reasoning="基本面良好",
            
            final_confidence="高",
            synthesis_method="一致",
            asset_class=f["asset"],
            buy_multiplier=1.2
        )
        reports.append(r)
        
    html = generate_combined_email_html(reports, time_str=datetime.now().strftime("%H:%M"))
    
    output_path = os.path.join(os.path.dirname(__file__), "test_report.html")
    with open(output_path, "w") as f:
        f.write(html)
        
    print(f"报告已生成: {output_path}")
    return output_path

if __name__ == "__main__":
    funds = mock_db_data()
    path = generate_report(funds)
    
    # 尝试打开（仅限 Mac）
    try:
        os.system(f"open {path}")
    except:
        pass
