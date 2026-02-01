"""
FundPilot-AI SQLite 数据库管理
包含历史净值缓存、决策日志、持仓缓存三张表
"""

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from core.logger import get_logger

logger = get_logger("database")

# 数据库文件路径
DB_DIR = Path(__file__).parent.parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_FILE = DB_DIR / "fundpilot.db"


# 建表 SQL
CREATE_TABLES_SQL = """
-- 历史净值缓存表
CREATE TABLE IF NOT EXISTS fund_nav_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code TEXT NOT NULL,
    nav_date DATE NOT NULL,
    nav REAL NOT NULL,
    acc_nav REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, nav_date)
);

-- 决策日志表 (v2.0 - 含回测验证字段)
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code TEXT NOT NULL,
    fund_name TEXT,
    fund_type TEXT,                          -- Bond / ETF_Feeder
    asset_class TEXT,                        -- GOLD_ETF / COMMODITY_CYCLE / BOND_ENHANCED / BOND_PURE
    decision_time TIMESTAMP NOT NULL,
    estimate_change REAL,
    percentile_250 REAL,
    ma_60 REAL,
    ai_decision TEXT NOT NULL,               -- 双倍补仓/正常定投/暂停定投/观望
    ai_reasoning TEXT,
    raw_context TEXT,
    -- v2.0 回测验证字段
    decision_nav REAL,                       -- 决策时净值（估值）
    actual_nav_t5 REAL,                      -- T+5 实际净值
    actual_return_t5 REAL,                   -- T+5 实际收益率 (%)
    is_validated INTEGER DEFAULT 0,          -- 是否已验证 (0/1)
    is_success INTEGER,                      -- 决策是否正确 (0/1/NULL)
    validated_at TIMESTAMP,                  -- 验证时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 持仓映射缓存表
CREATE TABLE IF NOT EXISTS holdings_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    weight REAL,
    updated_at TIMESTAMP,
    UNIQUE(fund_code, stock_code)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_nav_fund_date ON fund_nav_history(fund_code, nav_date);
CREATE INDEX IF NOT EXISTS idx_decision_fund_time ON decision_log(fund_code, decision_time);
CREATE INDEX IF NOT EXISTS idx_decision_validated ON decision_log(is_validated, decision_time);
CREATE INDEX IF NOT EXISTS idx_holdings_fund ON holdings_cache(fund_code);
"""


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with self.get_connection() as conn:
            conn.executescript(CREATE_TABLES_SQL)
            logger.info(f"数据库初始化完成: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()
    
    # ==================== 历史净值操作 ====================
    
    def save_nav_history(self, fund_code: str, nav_date: date, nav: float, acc_nav: Optional[float] = None):
        """保存历史净值"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO fund_nav_history (fund_code, nav_date, nav, acc_nav)
                VALUES (?, ?, ?, ?)
                """,
                (fund_code, nav_date.isoformat(), nav, acc_nav)
            )
    
    def save_nav_history_batch(self, fund_code: str, nav_list: list[tuple[date, float, Optional[float]]]):
        """批量保存历史净值"""
        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO fund_nav_history (fund_code, nav_date, nav, acc_nav)
                VALUES (?, ?, ?, ?)
                """,
                [(fund_code, d.isoformat(), nav, acc) for d, nav, acc in nav_list]
            )
        logger.info(f"批量保存基金 {fund_code} 净值 {len(nav_list)} 条")
    
    def get_nav_history(self, fund_code: str, days: int = 60) -> list[tuple[date, float]]:
        """获取历史净值（按日期降序）"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT nav_date, nav FROM fund_nav_history
                WHERE fund_code = ?
                ORDER BY nav_date DESC
                LIMIT ?
                """,
                (fund_code, days)
            )
            return [(date.fromisoformat(row["nav_date"]), row["nav"]) for row in cursor]
    
    def get_latest_nav_date(self, fund_code: str) -> Optional[date]:
        """获取最新净值日期"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT MAX(nav_date) as latest_date FROM fund_nav_history
                WHERE fund_code = ?
                """,
                (fund_code,)
            )
            row = cursor.fetchone()
            if row and row["latest_date"]:
                return date.fromisoformat(row["latest_date"])
            return None
    
    # ==================== 决策日志操作 ====================
    
    def save_decision_log(
        self,
        fund_code: str,
        fund_name: str,
        fund_type: str,
        asset_class: str,
        decision_time: datetime,
        estimate_change: Optional[float],
        percentile_250: Optional[float],
        ma_60: Optional[float],
        ai_decision: str,
        decision_nav: Optional[float] = None,
        ai_reasoning: Optional[str] = None,
        raw_context: Optional[str] = None
    ):
        """保存决策日志（v2.0 含回测字段）"""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO decision_log 
                (fund_code, fund_name, fund_type, asset_class, decision_time, 
                 estimate_change, percentile_250, ma_60, ai_decision, decision_nav,
                 ai_reasoning, raw_context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (fund_code, fund_name, fund_type, asset_class, decision_time.isoformat(), 
                 estimate_change, percentile_250, ma_60, ai_decision, decision_nav,
                 ai_reasoning, raw_context)
            )
        logger.info(f"保存决策日志: {fund_code} -> {ai_decision}")
    
    def get_pending_validations(self, days_ago: int = 5) -> list[dict]:
        """获取待验证的决策记录（T+N天前未验证的）"""
        cutoff_date = (datetime.now() - timedelta(days=days_ago)).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, fund_code, fund_name, fund_type, asset_class, 
                       decision_time, ai_decision, decision_nav
                FROM decision_log
                WHERE is_validated = 0 
                  AND decision_time < ?
                  AND decision_nav IS NOT NULL
                ORDER BY decision_time ASC
                """,
                (cutoff_date,)
            )
            return [dict(row) for row in cursor]
    
    def update_decision_validation(
        self,
        decision_id: int,
        actual_nav_t5: float,
        actual_return_t5: float,
        is_success: bool
    ):
        """更新决策验证结果"""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE decision_log
                SET actual_nav_t5 = ?,
                    actual_return_t5 = ?,
                    is_validated = 1,
                    is_success = ?,
                    validated_at = ?
                WHERE id = ?
                """,
                (actual_nav_t5, actual_return_t5, 1 if is_success else 0, 
                 datetime.now().isoformat(), decision_id)
            )
        logger.info(f"更新决策验证: ID={decision_id}, 收益={actual_return_t5:.2f}%, 成功={is_success}")
    
    def get_fund_backtest_stats(self, fund_code: str, limit: int = 30) -> dict:
        """获取基金回测统计（最近N条已验证决策）"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_success = 1 THEN 1 ELSE 0 END) as success_count,
                       AVG(actual_return_t5) as avg_return
                FROM (
                    SELECT is_success, actual_return_t5
                    FROM decision_log
                    WHERE fund_code = ? 
                      AND is_validated = 1
                      AND ai_decision != '观望'
                    ORDER BY decision_time DESC
                    LIMIT ?
                )
                """,
                (fund_code, limit)
            )
            row = cursor.fetchone()
            if row and row["total"] and row["total"] > 0:
                return {
                    "total": row["total"],
                    "success": row["success_count"] or 0,
                    "accuracy": (row["success_count"] or 0) / row["total"] * 100,
                    "avg_return": row["avg_return"] or 0
                }
            return {"total": 0, "success": 0, "accuracy": 0, "avg_return": 0}
    
    def get_recent_decisions(self, fund_code: str, limit: int = 20) -> list[dict]:
        """获取最近的决策记录明细"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT decision_time, ai_decision, decision_nav, 
                       actual_nav_t5, actual_return_t5, is_validated, is_success
                FROM decision_log
                WHERE fund_code = ?
                ORDER BY decision_time DESC
                LIMIT ?
                """,
                (fund_code, limit)
            )
            return [dict(row) for row in cursor]
    
    # ==================== 持仓缓存操作 ====================
    
    def save_holdings(self, fund_code: str, holdings: list[tuple[str, str, float]]):
        """保存持仓信息"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            # 先删除旧数据
            conn.execute("DELETE FROM holdings_cache WHERE fund_code = ?", (fund_code,))
            # 插入新数据
            conn.executemany(
                """
                INSERT INTO holdings_cache (fund_code, stock_code, stock_name, weight, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(fund_code, code, name, weight, now) for code, name, weight in holdings]
            )
        logger.info(f"保存基金 {fund_code} 持仓 {len(holdings)} 条")
    
    def get_holdings(self, fund_code: str) -> list[tuple[str, str, float]]:
        """获取持仓信息"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT stock_code, stock_name, weight FROM holdings_cache
                WHERE fund_code = ?
                ORDER BY weight DESC
                """,
                (fund_code,)
            )
            return [(row["stock_code"], row["stock_name"], row["weight"]) for row in cursor]
    
    def get_holdings_updated_at(self, fund_code: str) -> Optional[datetime]:
        """获取持仓缓存的更新时间"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT MAX(updated_at) as updated_at FROM holdings_cache
                WHERE fund_code = ?
                """,
                (fund_code,)
            )
            row = cursor.fetchone()
            if row and row["updated_at"]:
                return datetime.fromisoformat(row["updated_at"])
            return None


# 全局数据库实例
_db: Optional[Database] = None


def get_database() -> Database:
    """获取数据库单例"""
    global _db
    if _db is None:
        _db = Database()
    return _db
