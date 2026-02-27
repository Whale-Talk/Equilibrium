import sys
sys.path.insert(0, '/home/mjy/AI量化/Equilibrium')
from core.data_manager import DataManager
from utils.indicators import calculate_all_indicators
from datetime import datetime

dm = DataManager()
klines = dm.get_klines('1h', 9000)
klines = klines.sort_values('timestamp').reset_index(drop=True)
df = calculate_all_indicators(klines)

ATR_SL = 2.0
RISK_PERCENT = 0.02
TRAILING_ATR = 1.0
BASE_BALANCE = 100.0
leverage = 10
max_hours = 12

def run_backtest_v2(days=365):
    hours_needed = days * 24 + 20
    df_test = df.iloc[-hours_needed:].reset_index(drop=True).copy()
    
    balance = 100.0
    base_balance = BASE_BALANCE
    max_balance = balance
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
        
        position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
        position_size = max(5, min(position_size, balance * 0.5))
        
        if i >= 24:
            ma20_prev = df_test.iloc[i-24].get('ma20', price)
            if ma20 > ma20_prev * 1.01:
                trend = "up"
            elif ma20 < ma20_prev * 0.99:
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
                position["add_count"] = position.get("add_count", 0) + 1
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
    
    if balance > base_balance:
        total_withdrawn += balance - base_balance
        balance = base_balance
    
    total_return = total_withdrawn + (balance - 100)
    trades = win + loss
    wr = win / trades * 100 if trades > 0 else 0
    return total_withdrawn, balance, total_return, trades, wr

def run_backtest_v2_improve1(days=365):
    hours_needed = days * 24 + 20
    df_test = df.iloc[-hours_needed:].reset_index(drop=True).copy()
    
    balance = 100.0
    base_balance = BASE_BALANCE
    max_balance = balance
    position = None
    win, loss = 0, 0
    total_withdrawn = 0
    
    rsi_buy_consecutive = 0
    rsi_sell_consecutive = 0
    macd_positive_count = 0
    macd_negative_count = 0
    
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
        
        if i >= 20:
            vol_ma = df_test.iloc[i-20:i]['volume'].mean()
        else:
            vol_ma = volume
        
        position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
        position_size = max(5, min(position_size, balance * 0.5))
        
        if i >= 24:
            ma20_prev = df_test.iloc[i-24].get('ma20', price)
            if ma20 > ma20_prev * 1.01:
                trend = "up"
            elif ma20 < ma20_prev * 0.99:
                trend = "down"
            else:
                trend = "neutral"
        else:
            trend = "neutral"
        
        if rsi < 40:
            rsi_buy_consecutive += 1
        else:
            rsi_buy_consecutive = 0
        
        if rsi > 60:
            rsi_sell_consecutive += 1
        else:
            rsi_sell_consecutive = 0
        
        if macd > macd_signal:
            macd_positive_count += 1
            macd_negative_count = 0
        elif macd < macd_signal:
            macd_negative_count += 1
            macd_positive_count = 0
        else:
            macd_positive_count = 0
            macd_negative_count = 0
        
        volume_ok = volume > vol_ma
        
        signal = 'hold'
        if trend == 'up' and rsi_buy_consecutive >= 1 and macd_positive_count >= 1 and volume_ok:
            signal = 'buy'
        elif trend == 'down' and rsi_sell_consecutive >= 1 and macd_negative_count >= 1 and volume_ok:
            signal = 'sell'
        
        if position:
            if signal == position["action"]:
                add_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
                add_size = max(5, min(add_size, balance * 0.3))
                position["position_size"] = position.get("position_size", 0) + add_size
                position["add_count"] = position.get("add_count", 0) + 1
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
    
    if balance > base_balance:
        total_withdrawn += balance - base_balance
        balance = base_balance
    
    total_return = total_withdrawn + (balance - 100)
    trades = win + loss
    wr = win / trades * 100 if trades > 0 else 0
    return total_withdrawn, balance, total_return, trades, wr

def run_backtest_v2_improve2(days=365):
    hours_needed = days * 24 + 20
    df_test = df.iloc[-hours_needed:].reset_index(drop=True).copy()
    
    balance = 100.0
    base_balance = BASE_BALANCE
    max_balance = balance
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
        
        if i >= 24:
            ma20_prev = df_test.iloc[i-24].get('ma20', price)
            if ma20 > ma20_prev * 1.01:
                trend = "up"
            elif ma20 < ma20_prev * 0.99:
                trend = "down"
            else:
                trend = "neutral"
        else:
            trend = "neutral"
        
        is_ranging = adx < 25
        dynamic_max_hours = 4 if is_ranging else 12
        position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
        if is_ranging:
            position_size = position_size * 0.5
        position_size = max(5, min(position_size, balance * 0.5))
        
        rsi_buy = rsi < 40
        rsi_sell = rsi > 60
        signal = 'hold'
        if trend == 'up' and rsi_buy:
            signal = 'buy'
        elif trend == 'down' and rsi_sell:
            signal = 'sell'
        
        if position:
            if signal == position["action"]:
                if is_ranging:
                    continue
                add_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
                add_size = max(5, min(add_size, balance * 0.3))
                position["position_size"] = position.get("position_size", 0) + add_size
                position["add_count"] = position.get("add_count", 0) + 1
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
    
    if balance > base_balance:
        total_withdrawn += balance - base_balance
        balance = base_balance
    
    total_return = total_withdrawn + (balance - 100)
    trades = win + loss
    wr = win / trades * 100 if trades > 0 else 0
    return total_withdrawn, balance, total_return, trades, wr

def run_backtest_v2_improve_both(days=365):
    hours_needed = days * 24 + 20
    df_test = df.iloc[-hours_needed:].reset_index(drop=True).copy()
    
    balance = 100.0
    base_balance = BASE_BALANCE
    max_balance = balance
    position = None
    win, loss = 0, 0
    total_withdrawn = 0
    
    rsi_buy_consecutive = 0
    rsi_sell_consecutive = 0
    macd_positive_count = 0
    macd_negative_count = 0
    
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
        
        if i >= 20:
            vol_ma = df_test.iloc[i-20:i]['volume'].mean()
        else:
            vol_ma = volume
        
        if i >= 24:
            ma20_prev = df_test.iloc[i-24].get('ma20', price)
            if ma20 > ma20_prev * 1.01:
                trend = "up"
            elif ma20 < ma20_prev * 0.99:
                trend = "down"
            else:
                trend = "neutral"
        else:
            trend = "neutral"
        
        is_ranging = adx < 25
        dynamic_max_hours = 4 if is_ranging else 12
        
        if rsi < 40:
            rsi_buy_consecutive += 1
        else:
            rsi_buy_consecutive = 0
        
        if rsi > 60:
            rsi_sell_consecutive += 1
        else:
            rsi_sell_consecutive = 0
        
        if macd > macd_signal:
            macd_positive_count += 1
            macd_negative_count = 0
        elif macd < macd_signal:
            macd_negative_count += 1
            macd_positive_count = 0
        else:
            macd_positive_count = 0
            macd_negative_count = 0
        
        volume_ok = volume > vol_ma
        
        position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
        if is_ranging:
            position_size = position_size * 0.5
        position_size = max(5, min(position_size, balance * 0.5))
        
        signal = 'hold'
        if trend == 'up' and rsi_buy_consecutive >= 1 and macd_positive_count >= 1 and volume_ok:
            signal = 'buy'
        elif trend == 'down' and rsi_sell_consecutive >= 1 and macd_negative_count >= 1 and volume_ok:
            signal = 'sell'
        
        if position:
            if signal == position["action"]:
                if is_ranging:
                    continue
                add_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
                add_size = max(5, min(add_size, balance * 0.3))
                position["position_size"] = position.get("position_size", 0) + add_size
                position["add_count"] = position.get("add_count", 0) + 1
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
    
    if balance > base_balance:
        total_withdrawn += balance - base_balance
        balance = base_balance
    
    total_return = total_withdrawn + (balance - 100)
    trades = win + loss
    wr = win / trades * 100 if trades > 0 else 0
    return total_withdrawn, balance, total_return, trades, wr

print("开始回测...")
print("="*60)

w1, b1, r1, t1, wr1 = run_backtest_v2(365)
print(f"[原始v2] 提取{w1:.0f}U + 余额{b1:.0f}U = 总{r1:.0f}U ({r1/100*100:+.0f}%), 交易{t1}次, 胜率{wr1:.0f}%")

w2, b2, r2, t2, wr2 = run_backtest_v2_improve1(365)
print(f"[改进1-入场] 提取{w2:.0f}U + 余额{b2:.0f}U = 总{r2:.0f}U ({r2/100*100:+.0f}%), 交易{t2}次, 胜率{wr2:.0f}%")

w3, b3, r3, t3, wr3 = run_backtest_v2_improve2(365)
print(f"[改进2-风控] 提取{w3:.0f}U + 余额{b3:.0f}U = 总{r3:.0f}U ({r3/100*100:+.0f}%), 交易{t3}次, 胜率{wr3:.0f}%")

w4, b4, r4, t4, wr4 = run_backtest_v2_improve_both(365)
print(f"[联合改进] 提取{w4:.0f}U + 余额{b4:.0f}U = 总{r4:.0f}U ({r4/100*100:+.0f}%), 交易{t4}次, 胜率{wr4:.0f}%")

print("="*60)
print(f"改进1 vs 原始: {r2-r1:+.0f}U ({((r2-r1)/r1*100) if r1 > 0 else 0:+.0f}%)")
print(f"改进2 vs 原始: {r3-r1:+.0f}U ({((r3-r1)/r1*100) if r1 > 0 else 0:+.0f}%)")
print(f"联合 vs 原始:  {r4-r1:+.0f}U ({((r4-r1)/r1*100) if r1 > 0 else 0:+.0f}%)")
