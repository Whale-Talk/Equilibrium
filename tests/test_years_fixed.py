import sys
sys.path.insert(0, '/home/mjy/AI量化/BTC3.0')

# 临时修改DataManager的数据库路径
import core.data_manager
core.data_manager.DataManager.__init__ = lambda self, db_path="/home/mjy/AI量化/K/data/btc_klines.db": None

# 直接测试
import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('/home/mjy/AI量化/K/data/btc_klines.db')

for year in [2019, 2020, 2021, 2022, 2023, 2024, 2025]:
    start_ts = int(datetime(year, 1, 1).timestamp() * 1000)
    if year == 2025:
        end_ts = int(datetime(2025, 12, 31, 23, 59, 59).timestamp() * 1000)
    else:
        end_ts = int(datetime(year+1, 1, 1).timestamp() * 1000) - 1
    
    cursor = conn.cursor()
    cursor.execute(f'SELECT timestamp, open, high, low, close, volume FROM kline_1h WHERE timestamp >= {start_ts} AND timestamp <= {end_ts}')
    rows = cursor.fetchall()
    
    if len(rows) < 100:
        continue
    
    klines = pd.DataFrame({
        'timestamp': [r[0] for r in rows],
        'open': [r[1] for r in rows],
        'high': [r[2] for r in rows],
        'low': [r[3] for r in rows],
        'close': [r[4] for r in rows],
        'volume': [r[5] for r in rows]
    })
    
    from utils.indicators import calculate_all_indicators
    df = calculate_all_indicators(klines)
    
    # 回测
    INITIAL_BALANCE = 100.0
    ATR_SL = 2.0
    RISK_PERCENT = 0.02
    TRAILING_ATR = 1.0
    BASE_BALANCE = 100.0
    leverage = 10
    max_hours = 12
    
    balance = INITIAL_BALANCE
    base_balance = BASE_BALANCE
    position = None
    win, loss = 0, 0
    total_withdrawn = 0
    
    for i in range(20, len(df)):
        latest = df.iloc[i]
        price = latest['close']
        rsi = latest.get('rsi', 50)
        bb_lower = latest.get('bb_lower', price * 0.98)
        bb_upper = latest.get('bb_upper', price * 1.02)
        atr = latest.get('atr', price * 0.02)
        ma20 = latest.get('ma20', price)
        
        position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
        position_size = max(5, min(position_size, balance * 0.5))
        
        if i >= 24:
            ma20_prev = df.iloc[i-24].get('ma20', price)
            ma20_now = ma20
            if ma20_now > ma20_prev * 1.01:
                trend = "up"
            elif ma20_now < ma20_prev * 0.99:
                trend = "down"
            else:
                trend = "neutral"
        else:
            trend = "neutral"
        
        rsi_buy = rsi < 40
        rsi_sell = rsi > 60
        signal = 'hold'
        if trend == 'up' and rsi_buy:
            signal = 'buy'
        elif trend == 'down' and rsi_sell:
            signal = 'sell'
        
        if position:
            if signal == position["action"]:
                add_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
                add_size = max(5, min(add_size, balance * 0.3))
                position["position_size"] = position.get("position_size", 0) + add_size
            elif signal != 'hold' and signal != position["action"]:
                if position["action"] == "buy":
                    pnl_pct = (price - position["price"]) / position["price"] * leverage
                else:
                    pnl_pct = (position["price"] - price) / position["price"] * leverage
                pnl = position["position_size"] * pnl_pct
                balance += pnl
                if pnl > 0: win += 1
                else: loss += 1
                position = None
                if balance > base_balance:
                    total_withdrawn += balance - base_balance
                    balance = base_balance
                continue
            
            if position:
                if position["action"] == "buy":
                    pnl_pct = (price - position["price"]) / position["price"] * leverage
                    hit_sl = price <= position["trailing_stop"]
                    hit_tp1 = price >= position["take_profit_tp1"] and not position["tp1_hit"]
                    hit_tp2 = position["tp1_hit"] and price >= position["take_profit_tp2"]
                    if not position["tp1_hit"] and price >= position["price"] + position["atr"] * TRAILING_ATR:
                        position["trailing_stop"] = position["price"]
                        position["tp1_hit"] = True
                else:
                    pnl_pct = (position["price"] - price) / position["price"] * leverage
                    hit_sl = price >= position["trailing_stop"]
                    hit_tp1 = price <= position["take_profit_tp1"] and not position["tp1_hit"]
                    hit_tp2 = position["tp1_hit"] and price <= position["take_profit_tp2"]
                    if not position["tp1_hit"] and price <= position["price"] - position["atr"] * TRAILING_ATR:
                        position["trailing_stop"] = position["price"]
                        position["tp1_hit"] = True
                
                should_close = hit_tp2 or hit_sl or (i - position["entry_idx"]) >= max_hours
                
                if hit_tp1 and not hit_sl and (i - position["entry_idx"]) < max_hours:
                    position["tp1_hit"] = True
                    position["stop_loss"] = position["price"]
                    continue
                
                if should_close:
                    pnl = position["position_size"] * pnl_pct
                    balance += pnl
                    if pnl > 0: win += 1
                    else: loss += 1
                    position = None
                    if balance > base_balance:
                        total_withdrawn += balance - base_balance
                        balance = base_balance
        
        elif signal == 'buy':
            stop_loss = bb_lower - atr * ATR_SL
            take_profit_tp1 = price + (price - stop_loss) * 1.5
            take_profit_tp2 = price + (price - stop_loss) * 3.0
            position = {"action": "buy", "price": price, "leverage": leverage, "entry_idx": i,
                       "stop_loss": stop_loss, "take_profit_tp1": take_profit_tp1, "take_profit_tp2": take_profit_tp2,
                       "atr": atr, "trailing_stop": stop_loss, "tp1_hit": False, "position_size": position_size}
        elif signal == 'sell':
            stop_loss = bb_upper + atr * ATR_SL
            take_profit_tp1 = price - (stop_loss - price) * 1.5
            take_profit_tp2 = price - (stop_loss - price) * 3.0
            position = {"action": "sell", "price": price, "leverage": leverage, "entry_idx": i,
                       "stop_loss": stop_loss, "take_profit_tp1": take_profit_tp1, "take_profit_tp2": take_profit_tp2,
                       "atr": atr, "trailing_stop": stop_loss, "tp1_hit": False, "position_size": position_size}
        
        if i + 1 < len(df):
            current_month = datetime.fromtimestamp(df.iloc[i]['timestamp']/1000).strftime('%Y-%m')
            next_month = datetime.fromtimestamp(df.iloc[i+1]['timestamp']/1000).strftime('%Y-%m')
            if current_month != next_month and position is None and balance > base_balance:
                total_withdrawn += balance - base_balance
                balance = base_balance
    
    if balance > base_balance:
        total_withdrawn += balance - base_balance
        balance = base_balance
    
    total_return = total_withdrawn + (balance - INITIAL_BALANCE)
    trades = win + loss
    wr = win / trades * 100 if trades > 0 else 0
    
    print(f"[{year}] 提取{total_withdrawn:.0f}U + 余额{balance:.0f}U = 总{total_return:.0f}U ({total_return:+.0f}%), 交易{trades}次, 胜率{wr:.0f}%")

conn.close()
