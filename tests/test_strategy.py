import sys
sys.path.insert(0, '/home/mjy/AI量化/BTC3.0')
from core.data_manager import DataManager
from utils.indicators import calculate_all_indicators

dm = DataManager()
klines = dm.get_klines('1h', 8000)
klines = klines.sort_values('timestamp').reset_index(drop=True)
df = calculate_all_indicators(klines)

# 测试1: RSI过滤区
balance = 100
leverage = 10
max_hours = 12
RISK_PERCENT = 0.02
ATR_SL = 2.0

position = None
win, loss = 0, 0
total_withdrawn = 0
base_balance = 100
rsi_buy_count = 0
rsi_sell_count = 0

for i in range(24, len(df)):
    latest = df.iloc[i]
    price = latest['close']
    rsi = latest.get('rsi', 50)
    bb_lower = latest.get('bb_lower', price * 0.98)
    bb_upper = latest.get('bb_upper', price * 1.02)
    atr = latest.get('atr', price * 0.02)
    ma20 = latest.get('ma20', price)
    macd = latest.get('macd', 0)
    macd_signal = latest.get('macd_signal', 0)
    
    if rsi < 40:
        rsi_buy_count += 1
    else:
        rsi_buy_count = 0
    
    if rsi > 60:
        rsi_sell_count += 1
    else:
        rsi_sell_count = 0
    
    ma20_prev = df.iloc[i-24].get('ma20', price)
    trend = 'up' if ma20 > ma20_prev * 1.01 else ('down' if ma20 < ma20_prev * 0.99 else 'neutral')
    
    signal = 'hold'
    if trend == 'up' and rsi_buy_count >= 2 and macd > macd_signal:
        signal = 'buy'
    if trend == 'down' and rsi_sell_count >= 2 and macd < macd_signal:
        signal = 'sell'
    
    if position:
        if signal == position['action']:
            add_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
            add_size = max(5, min(add_size, balance * 0.3))
            position['size'] = position.get('size', 0) + add_size
        elif signal != 'hold' and signal != position['action']:
            if position['action'] == 'buy':
                pnl = position['size'] * (price - position['price']) / position['price'] * leverage
            else:
                pnl = position['size'] * (position['price'] - price) / position['price'] * leverage
            balance += pnl
            if pnl > 0: win += 1
            else: loss += 1
            position = None
            if balance > base_balance:
                total_withdrawn += balance - base_balance
                balance = base_balance
            continue
        
        if position:
            if position['action'] == 'buy':
                pnl_pct = (price - position['price']) / position['price'] * leverage
                hit_sl = price <= position['trailing']
                if not position.get('tp1_hit') and price >= position['price'] + position['atr']:
                    position['trailing'] = position['price']
                    position['tp1_hit'] = True
            else:
                pnl_pct = (position['price'] - price) / position['price'] * leverage
                hit_sl = price >= position['trailing']
                if not position.get('tp1_hit') and price <= position['price'] - position['atr']:
                    position['trailing'] = position['price']
                    position['tp1_hit'] = True
            
            hit_tp2 = position.get('tp1_hit') and (position['action'] == 'buy' and price >= position.get('tp2', 999999) or position['action'] == 'sell' and price <= position.get('tp2', 0))
            if hit_tp2 or hit_sl or (i - position['entry_idx']) >= max_hours:
                pnl = position['size'] * pnl_pct
                balance += pnl
                if pnl > 0: win += 1
                else: loss += 1
                position = None
                if balance > base_balance:
                    total_withdrawn += balance - base_balance
                    balance = base_balance
    
    elif signal != 'hold':
        position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
        position_size = max(5, min(position_size, balance * 0.5))
        
        if signal == 'buy':
            sl = bb_lower - atr * ATR_SL
            position = {'action': 'buy', 'price': price, 'size': position_size, 'entry_idx': i, 'sl': sl, 'tp1_hit': False, 'tp2': price + (price - sl) * 3, 'trailing': sl, 'atr': atr}
        else:
            sl = bb_upper + atr * ATR_SL
            position = {'action': 'sell', 'price': price, 'size': position_size, 'entry_idx': i, 'sl': sl, 'tp1_hit': False, 'tp2': price - (sl - price) * 3, 'trailing': sl, 'atr': atr}

if balance > base_balance:
    total_withdrawn += balance - base_balance
    balance = base_balance

total_return = total_withdrawn + (balance - 100)
trades = win + loss
wr = win / trades * 100 if trades > 0 else 0
print(f'1.RSI过滤区(2根): 提取{total_withdrawn:.0f}U + 余额{balance:.0f}U = 总{total_return:.0f}U ({total_return/100*100:+.0f}%), 交易{trades}次, 胜率{wr:.0f}%')
