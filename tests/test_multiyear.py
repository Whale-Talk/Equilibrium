import sys
import os
import sqlite3
import numpy as np
from datetime import datetime

sys.path.insert(0, '/home/mjy/AI量化/Equilibrium')
from utils.indicators import calculate_all_indicators

# 读取K文件夹的数据
def get_klines_from_K(interval='1h'):
    conn = sqlite3.connect('/home/mjy/AI量化/K/data/btc_klines.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT timestamp, open, high, low, close, volume FROM kline_{interval} ORDER BY timestamp")
    rows = cursor.fetchall()
    data = {
        'timestamp': [r[0] for r in rows],
        'open': [r[1] for r in rows],
        'high': [r[2] for r in rows],
        'low': [r[3] for r in rows],
        'close': [r[4] for r in rows],
        'volume': [r[5] for r in rows]
    }
    import pandas as pd
    df = pd.DataFrame(data)
    print(f"{interval}: {len(df)} 条, 从 {datetime.fromtimestamp(df['timestamp'].iloc[0]/1000)} 到 {datetime.fromtimestamp(df['timestamp'].iloc[-1]/1000)}")
    conn.close()
    return df

print("读取K文件夹数据...")
klines = get_klines_from_K('1h')
klines = klines.sort_values('timestamp').reset_index(drop=True)
print(f"总数据: {len(klines)} 条")

df = calculate_all_indicators(klines)

INITIAL_BALANCE = 100.0
ATR_SL = 2.0
RISK_PERCENT = 0.02
TRAILING_ATR = 1.0
BASE_BALANCE = 100.0
leverage = 10

def run_backtest(df_test, version='original', max_hours=12):
    balance = INITIAL_BALANCE
    base_balance = BASE_BALANCE
    max_balance = balance
    position = None
    win, loss = 0, 0
    total_withdrawn = 0
    
    rsi_buy_count = 0
    rsi_sell_count = 0
    macd_pos_count = 0
    macd_neg_count = 0
    
    for i in range(20, len(df_test)):
        latest = df_test.iloc[i]
        price = latest['close']
        rsi = latest.get('rsi', 50)
        bb_lower = latest.get('bb_lower', price * 0.98)
        bb_upper = latest.get('bb_upper', price * 1.02)
        atr = latest.get('atr', price * 0.02)
        ma20 = latest.get('ma20', price)
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)
        volume = latest.get('volume', 0)
        adx = latest.get('adx', 50)
        
        # 判断市场状态
        is_ranging = adx < 25
        
        ma20_now = ma20
        if version == 'moderate':
            position_size_ratio = 0.5 if is_ranging else 1.0
            allow_add = False if is_ranging else True
            dynamic_max_hours = max_hours
        elif version == 'dynamic':
            is_strong_trend = False
            if i >= 24:
                ma20_prev = df_test.iloc[i-24].get('ma20', price)
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
        else:  # original
            position_size_ratio = 1.0
            allow_add = True
            dynamic_max_hours = max_hours
        
        if i >= 20:
            vol_ma = df_test.iloc[i-20:i]['volume'].mean()
        else:
            vol_ma = volume
        
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

# 按年度分析
print("\n" + "="*60)
print("按年度回测结果 (original)")
print("="*60)

df['_year'] = df['timestamp'].apply(lambda x: datetime.fromtimestamp(x/1000).year)

for year in sorted(df['_year'].unique()):
    df_year = df[df['_year'] == year].reset_index(drop=True)
    w, b, r, t, wr = run_backtest(df_year, version='original')
    print(f"[{year}] 提取${w:.0f} + 余额${b:.0f} = 总${r:.0f} ({r:+.0f}%), 交易{t}次, 胜率{wr:.0f}%")

# 运行全年回测
print("\n" + "="*60)
print("多年回测结果 (2019-01 至 2026-02)")
print("="*60)

for version in ['original', 'moderate', 'dynamic']:
    w, b, r, t, wr = run_backtest(df, version=version)
    print(f"[{version:8}] 提取${w:.0f} + 余额${b:.0f} = 总${r:.0f} ({r:+.0f}%), 交易{t}次, 胜率{wr:.0f}%")
