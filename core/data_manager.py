import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from config import Config


class DataManager:
    def __init__(self, db_path: str = "data/btc_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for interval in Config.KLINE_INTERVALS:
            table_name = f"kline_{interval}"
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL
                )
            """)
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_timestamp_{interval} ON {table_name}(timestamp)")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                leverage INTEGER NOT NULL,
                pnl REAL,
                status TEXT NOT NULL,
                reason TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                balance REAL NOT NULL,
                action TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def save_klines(self, interval: str, klines: List[List]):
        """保存K线数据到数据库（自动去重，保持连续）"""
        if not klines:
            return
        
        conn = sqlite3.connect(self.db_path)
        table_name = f"kline_{interval}"
        
        # 查询已有数据的时间范围
        cursor = conn.cursor()
        cursor.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {table_name}")
        result = cursor.fetchone()
        existing_min = result[0] if result[0] else 0
        existing_max = result[1] if result[1] else 0
        
        # 收集需要插入的数据（去重）
        existing_timestamps = set()
        if existing_max > 0:
            cursor.execute(f"SELECT timestamp FROM {table_name}")
            existing_timestamps = {row[0] for row in cursor.fetchall()}
        
        new_data = []
        for k in klines:
            ts = int(k[0])
            # 只添加不存在的数据
            if ts not in existing_timestamps:
                new_data.append((
                    ts,
                    float(k[1]),
                    float(k[2]),
                    float(k[3]),
                    float(k[4]),
                    float(k[5])
                ))
                existing_timestamps.add(ts)
        
        if new_data:
            cursor.executemany(f"""
                INSERT INTO {table_name} (timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            """, new_data)
            conn.commit()
        
        conn.close()

    def get_klines(self, interval: str, limit: int = 100) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        table_name = f"kline_{interval}"
        
        df = pd.read_sql(f"""
            SELECT timestamp, open, high, low, close, volume
            FROM {table_name}
            ORDER BY timestamp DESC
            LIMIT {limit}
        """, conn)
        
        conn.close()
        
        if not df.empty:
            df = df.iloc[::-1]
        
        return df

    def save_trade(self, action: str, price: float, amount: float, leverage: int, 
                   pnl: Optional[float] = None, status: str = "open", reason: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO trades (timestamp, action, price, amount, leverage, pnl, status, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(datetime.now().timestamp()), action, price, amount, leverage, pnl, status, reason))
        
        conn.commit()
        conn.close()

    def update_trade_pnl(self, trade_id: int, pnl: float, status: str = "closed"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trades SET pnl = ?, status = ? WHERE id = ?
        """, (pnl, status, trade_id))
        
        conn.commit()
        conn.close()

    def get_open_trades(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, timestamp, action, price, amount, leverage, reason
            FROM trades WHERE status = 'open'
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {"id": r[0], "timestamp": r[1], "action": r[2], "price": r[3], 
             "amount": r[4], "leverage": r[5], "reason": r[6]}
            for r in rows
        ]

    def save_balance(self, balance: float, action: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO balance_history (timestamp, balance, action)
            VALUES (?, ?, ?)
        """, (int(datetime.now().timestamp()), balance, action))
        
        conn.commit()
        conn.close()

    def get_balance_history(self) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql("""
            SELECT timestamp, balance, action FROM balance_history ORDER BY timestamp
        """, conn)
        conn.close()
        return df

    def get_trades_history(self) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql("""
            SELECT * FROM trades ORDER BY timestamp DESC
        """, conn)
        conn.close()
        return df
    
    def get_trade_stats(self, days: int = 7) -> dict:
        """获取交易统计"""
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总交易统计
        cursor.execute("""
            SELECT COUNT(*), SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   SUM(pnl), MAX(pnl), MIN(pnl)
            FROM trades WHERE status = 'closed'
        """)
        row = cursor.fetchone()
        
        total_trades = row[0] or 0
        win_trades = row[1] or 0
        total_pnl = row[2] or 0
        max_win = row[3] or 0
        max_loss = row[4] or 0
        
        win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 今日交易
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_ts = int(today_start.timestamp() * 1000)
        
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(pnl), 0)
            FROM trades WHERE timestamp >= ?
        """, (today_ts,))
        today_row = cursor.fetchone()
        today_trades = today_row[0] or 0
        today_pnl = today_row[1] or 0
        
        # 本周交易
        week_start = (datetime.now() - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_ts = int(week_start.timestamp() * 1000)
        
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(pnl), 0)
            FROM trades WHERE timestamp >= ?
        """, (week_ts,))
        week_row = cursor.fetchone()
        week_trades = week_row[0] or 0
        week_pnl = week_row[1] or 0
        
        conn.close()
        
        return {
            'total_trades': total_trades,
            'win_trades': win_trades,
            'loss_trades': total_trades - win_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'best_trade': max_win,
            'worst_trade': max_loss,
            'today_trades': today_trades,
            'today_pnl': today_pnl,
            'week_trades': week_trades,
            'week_pnl': week_pnl,
            'total_withdrawn': 0  # 可后续添加
        }
