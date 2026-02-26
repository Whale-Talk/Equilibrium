import sys
sys.path.insert(0, '/home/mjy/AI量化/BTC3.0')

import sqlite3
import pandas as pd
from datetime import datetime
from core.data_manager import DataManager
from utils.indicators import calculate_all_indicators

# 读取K文件夹的数据
print("读取K文件夹数据...")
conn = sqlite3.connect('/home/mjy/AI量化/K/data/btc_klines.db')
cursor = conn.cursor()
cursor.execute("SELECT timestamp, open, high, low, close, volume FROM kline_1h ORDER BY timestamp")
rows = cursor.fetchall()
klines = pd.DataFrame({
    'timestamp': [r[0] for r in rows],
    'open': [r[1] for r in rows],
    'high': [r[2] for r in rows],
    'low': [r[3] for r in rows],
    'close': [r[4] for r in rows],
    'volume': [r[5] for r in rows]
})
conn.close()
print(f"原始数据: {len(klines)} 条")

klines = klines.sort_values('timestamp').reset_index(drop=True)
print(f"从 {datetime.fromtimestamp(klines['timestamp'].iloc[0]/1000)} 到 {datetime.fromtimestamp(klines['timestamp'].iloc[-1]/1000)}")

# 计算指标
print("计算指标...")
df = calculate_all_indicators(klines)
print(f"指标计算后: {len(df)} 条")

# 按年度测试
print("\n" + "="*60)
print("按年度回测结果")
print("="*60)

df['_year'] = df['timestamp'].apply(lambda x: datetime.fromtimestamp(x/1000).year)

# 简化回测函数
def simple_backtest(df_test, version='original', max_hours=12):
    INITIAL_BALANCE = 100.0
    ATR_SL = 2.0
    RISK_PERCENT = 0.02
    TRAILING_ATR = 1.0
    BASE_BALANCE = 100.0
    leverage = 10
    
    balance = INITIAL_BALANCE
    base_balance = BASE_BALANCE
    position = None
    win, loss = 0, 0
    total_withdrawn = 0
    
    for i in range(20, len(df_test)):
        latest = df_test.iloc[i]
        price = latest['close']
        rsi = latest.get('rsi', 50)
        bb_lower = latest.get('bb_lower', price * 0.98)
        bb_upper = latest.get('bb_upper', price * 1.02)
        atr = latest.get('atr', price * 0.02)
        ma20 = latest.get('ma20', price)
        adx = latest.get('adx', 50)
        
        is_ranging = adx < 25
        
        if version == 'moderate':
            position_size_ratio = 0.5 if is_ranging else 1.0
            allow_add = False if is_ranging else True
            dynamic_max_hours = max_hours
        elif version == 'dynamic':
            is_strong_trend = False
            if i >= 24:
                ma20_prev = df_test.iloc[i-24].get('ma20', price)
                ma20_now = ma20
                ma20_slope = ma20_now / ma20_prev if ma20_prev > 0 else 1.0
                is_strong_trend = (ma20_slope > 1.01 or ma20_slope < 0.99) and adx > 30
            
            if is_strong_trend:
                position_size_ratio = 1.0
                allow_add = True
                dynamic_max_hours = max_hours
            else:
                position_size_ratio = 0.5
                allow_add = False
                dynamic_max_hours = 4
        else:
            position_size_ratio = 1.0
            allow_add = True
            dynamic_max_hours = max_hours
        
        position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
        position_size = position_size * position_size_ratio
        position_size = max(5, min(position_size, balance * 0.5))
        
        if i >= 24:
            ma20_prev = df_test.iloc[i-24].get('ma20', price)
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
                if allow_add:
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
                
                should_close = hit_tp2 or hit_sl or (i - position["entry_idx"]) >= dynamic_max_hours
                
                if hit_tp1 and not hit_sl and (i - position["entry_idx"]) < dynamic_max_hours:
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
        
        # 每月提取
        if i + 1 < len(df_test):
            current_month = datetime.fromtimestamp(df_test.iloc[i]['timestamp']/1000).strftime('%Y-%m')
            next_month = datetime.fromtimestamp(df_test.iloc[i+1]['timestamp']/1000).strftime('%Y-%m')
            if current_month != next_month and position is None and balance > base_balance:
                total_withdrawn += balance - base_balance
                balance = base_balance
    
    if balance > base_balance:
        total_withdrawn += balance - base_balance
        balance = base_balance
    
    total_return = total_withdrawn + (balance - INITIAL_BALANCE)
    trades = win + loss
    wr = win / trades * 100 if trades > 0 else 0
    return total_withdrawn, balance, total_return, trades, wr

# 测试2025年
print("\n=== 2025年测试 ===")
df_2025 = df[df['_year'] == 2025].reset_index(drop=True)
print(f"2025数据: {len(df_2025)} 条")

for version in ['original', 'moderate', 'dynamic']:
    w, b, r, t, wr = simple_backtest(df_2025, version=version)
    print(f"[{version:8}] 提取${w:.0f} + 余额${b:.0f} = 总${r:.0f} ({r:+.0f}%), 交易{t}次, 胜率{wr:.0f}%")

# 测试2024年
print("\n=== 2024年测试 ===")
df_2024 = df[df['_year'] == 2024].reset_index(drop=True)
print(f"2024数据: {len(df_2024)} 条")

for version in ['original', 'moderate', 'dynamic']:
    w, b, r, t, wr = simple_backtest(df_2024, version=version)
    print(f"[{version:8}] 提取${w:.0f} + 余额${b:.0f} = 总${r:.0f} ({r:+.0f}%), 交易{t}次, 胜率{wr:.0f}%")
