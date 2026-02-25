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
        if not klines:
            return
            
        conn = sqlite3.connect(self.db_path)
        table_name = f"kline_{interval}"
        
        data = []
        for k in klines:
            data.append((
                int(k[0]),
                float(k[1]),
                float(k[2]),
                float(k[3]),
                float(k[4]),
                float(k[5])
            ))
        
        cursor = conn.cursor()
        cursor.executemany(f"""
            INSERT OR REPLACE INTO {table_name} (timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?)
        """, data)
        
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
