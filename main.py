import os
import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

os.environ['http_proxy'] = 'http://127.0.0.1:7897'
os.environ['https_proxy'] = 'http://127.0.0.1:7897'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from core.okx_client import OKXClient
from core.data_manager import DataManager
from core.notification import NotificationManager
from core.trade_executor import TradeExecutor
from core.btc_trading_agents import TradingAgent
from utils.indicators import calculate_all_indicators, get_indicator_summary


class BTCTader:
    def __init__(self, config: type = Config):
        self.config = config
        self.okx_client = OKXClient(config)
        self.data_manager = DataManager()
        self.notification = NotificationManager(config)
        self.trade_executor = TradeExecutor(config, self.data_manager, self.notification)
        
        self.last_analysis_time = {}
        self.analysis_interval_hours = 4
    
    def fetch_and_store_data(self):
        print(f"[{datetime.now()}] 获取K线数据...")
        
        for interval in self.config.KLINE_INTERVALS:
            klines = self.okx_client.get_klines(interval, self.config.KLINE_LIMIT)
            if klines:
                self.data_manager.save_klines(interval, klines)
                print(f"  {interval}: {len(klines)} 条")
    
    def run_analysis(self, force: bool = False):
        now = datetime.now()
        current_hour = now.hour
        
        should_run = False
        if force:
            should_run = True
        elif current_hour % self.analysis_interval_hours == 0:
            last_time = self.last_analysis_time.get("periodic")
            if not last_time or (now - last_time).total_seconds() > 3600 * self.analysis_interval_hours:
                should_run = True
        
        if not should_run:
            return None
        
        self.last_analysis_time["periodic"] = now
        
        print(f"\n[{now}] 开始指标信号分析...")
        
        klines_1h = self.data_manager.get_klines("1h", 100)
        if klines_1h.empty:
            print("没有K线数据")
            return None
        
        df_with_indicators = calculate_all_indicators(klines_1h)
        
        current_price = self.okx_client.get_current_price()
        if not current_price:
            current_price = float(klines_1h.iloc[-1]['close'])
        
        if df_with_indicators.empty:
            return None
        
        latest = df_with_indicators.iloc[-1]
        
        # 判断趋势
        if len(df_with_indicators) >= 24:
            ma20_prev = df_with_indicators.iloc[-24].get('ma20', current_price)
            ma20_now = latest.get('ma20', current_price)
            if ma20_now > ma20_prev * 1.01:
                trend = "up"
            elif ma20_now < ma20_prev * 0.99:
                trend = "down"
            else:
                trend = "neutral"
        else:
            trend = "neutral"
        
        print(f"趋势判断: {trend}")
        
        signal = self._simple_signal(latest, trend)
        
        if signal == "hold":
            print(f"信号: hold - 无交易信号")
            return None
        
        rsi = latest.get('rsi', 50)
        bb_lower = latest.get('bb_lower', current_price * 0.98)
        bb_upper = latest.get('bb_upper', current_price * 1.02)
        atr = latest.get('atr', current_price * 0.02)
        atr_sl = 1.5  # 止损ATR倍数
        
        if signal == "buy":
            stop_loss = bb_lower - atr * atr_sl
            take_profit = current_price + (current_price - stop_loss) * 2.5
        else:
            stop_loss = bb_upper + atr * atr_sl
            take_profit = current_price - (stop_loss - current_price) * 2.5
        
        print(f"信号: {signal} | 价格: ${current_price:.2f} | RSI: {rsi:.2f}")
        print(f"止损: ${stop_loss:.2f} | 止盈: ${take_profit:.2f}")
        
        return {
            "action": signal,
            "confidence": 0.8,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": f"指标信号: RSI={rsi:.2f}",
            "approved": True
        }
    
    def check_positions(self):
        current_price = self.okx_client.get_current_price()
        if not current_price:
            return
        
        if self.trade_executor.get_position():
            self.trade_executor.check_stop_loss(current_price)
            self.trade_executor.check_take_profit(current_price)
        else:
            self.trade_executor.check_and_withdraw_profit()
    
    def execute_signal(self, signal):
        if not signal or signal.get("action") == "hold":
            print("无交易信号")
            return
        
        if not signal.get("approved", True):
            print(f"风控拒绝交易: {signal.get('reason', '')[:100]}")
            return
        
        action = signal.get("action")
        confidence = signal.get("confidence", 0)
        
        if confidence < 0.6:
            print(f"置信度太低: {confidence}")
            return
        
        if self.trade_executor.get_position():
            print("已有持仓")
            return
        
        current_price = self.okx_client.get_current_price()
        if not current_price:
            print("无法获取价格")
            return
        
        amount = self.config.POSITION_SIZE
        leverage = min(signal.get("leverage", 10), self.config.MAX_LEVERAGE)
        reason = signal.get("reason", "")
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("take_profit")
        
        self.trade_executor.open_position(
            action=action,
            price=current_price,
            amount=amount,
            leverage=leverage,
            reason=reason[:500],
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    def run_backtest(self, days: int = 30, max_hours: int = 12, leverage: int = 10, 
                   enable_add_position: bool = True, withdraw_profit: bool = True,
                   strategy_version: str = 'original', quarter: str = None):
        """回测：优化版指标信号 + 移动止损 + 分批止盈 + 动态仓位 + 加仓 + 每月提取收益
        strategy_version: 'original', 'improve1', 'improve2', 'improve_both'
        quarter: 'Q1','Q2','Q3','Q4' """
        import sys
        import numpy as np
        from datetime import datetime
        
        # 优化后的参数
        ATR_SL = 2.0  # 止损ATR倍数 (优化后)
        RISK_PERCENT = 0.02  # 单笔风险2%
        TRAILING_ATR = 1.0  # 移动止损触发阈值
        BASE_BALANCE = 100.0  # 每月提取后的基础余额
        
        print(f"开始回测 (最近 {days} 天)")
        print(f"参数: 持仓{max_hours}h 杠杆{leverage}x | ATR_SL={ATR_SL}")
        print(f"加仓: {'启用' if enable_add_position else '禁用'} | 每月提取: {'启用' if withdraw_profit else '禁用'}")
        sys.stdout.flush()
        
        # 根据天数计算需要多少根K线（每天24根 + 预留指标计算需要20根）
        hours_needed = days * 24 + 20
        
        self.fetch_and_store_data()
        
        klines = self.data_manager.get_klines("1h", hours_needed)
        if klines.empty:
            print("没有K线数据")
            return None
        
        # 按时间排序，确保数据顺序正确
        klines = klines.sort_values('timestamp').reset_index(drop=True)
        
        # 如果数据超过需要的天数，从最早开始截取
        if len(klines) > hours_needed:
            klines = klines.iloc[-hours_needed:].reset_index(drop=True)
        
        print(f"[回测] K线数据: {len(klines)} 条 ({days} 天)", flush=True)
        
        df = calculate_all_indicators(klines)
        
        if quarter:
            df['_month'] = df['timestamp'].apply(lambda x: datetime.fromtimestamp(x/1000).month)
            if quarter == 'Q1':
                df = df[df['_month'].isin([1,2,3])].reset_index(drop=True)
            elif quarter == 'Q2':
                df = df[df['_month'].isin([4,5,6])].reset_index(drop=True)
            elif quarter == 'Q3':
                df = df[df['_month'].isin([7,8,9])].reset_index(drop=True)
            elif quarter == 'Q4':
                df = df[df['_month'].isin([10,11,12])].reset_index(drop=True)
            print(f"[回测] 季度{quarter}筛选后: {len(df)} 条", flush=True)
        
        balance = self.config.INITIAL_BALANCE
        base_balance = BASE_BALANCE if withdraw_profit else balance
        max_balance = balance
        trades = []
        position = None
        
        win_count = 0
        loss_count = 0
        daily_returns = []
        total_withdrawn = 0
        last_withdraw_month = None
        
        rsi_buy_count = 0
        rsi_sell_count = 0
        macd_pos_count = 0
        macd_neg_count = 0
        
        for i in range(20, len(df)):
            latest = df.iloc[i]
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
            is_strong_trend = False
            if i >= 24:
                ma20_prev = df.iloc[i-24].get('ma20', price)
                ma20_now = ma20
                ma20_slope = ma20_now / ma20_prev if ma20_prev > 0 else 1.0
                is_strong_trend = (ma20_slope > 1.01 or ma20_slope < 0.99) and adx > 30
            
            # 动态参数调整
            if strategy_version == 'dynamic':
                if is_strong_trend:
                    dynamic_max_hours = max_hours
                    position_size_ratio = 1.0
                    allow_add = True
                else:
                    dynamic_max_hours = 4
                    position_size_ratio = 0.5
                    allow_add = False
            elif strategy_version == 'moderate':
                if is_ranging:
                    dynamic_max_hours = max_hours
                    position_size_ratio = 0.5
                    allow_add = False
                else:
                    dynamic_max_hours = max_hours
                    position_size_ratio = 1.0
                    allow_add = True
            elif strategy_version in ['improve2', 'improve_both']:
                dynamic_max_hours = 4 if is_ranging else max_hours
                position_size_ratio = 0.5 if is_ranging else 1.0
                allow_add = not is_ranging
            else:
                dynamic_max_hours = max_hours
                position_size_ratio = 1.0
                allow_add = True
            
            if i >= 20:
                vol_ma = df.iloc[i-20:i]['volume'].mean()
            else:
                vol_ma = volume
            
            position_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
            position_size = position_size * position_size_ratio
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
            
            if i % 50 == 0:
                print(f"[回测] 进度: {i}/{len(df)} | 价格: ${price:.2f} | RSI: {rsi:.2f} | 趋势: {trend}", flush=True)
            
            if strategy_version in ['improve1', 'improve_both']:
                if rsi < 40:
                    rsi_buy_count += 1
                else:
                    rsi_buy_count = 0
                
                if rsi > 60:
                    rsi_sell_count += 1
                else:
                    rsi_sell_count = 0
                
                if macd > macd_signal:
                    macd_pos_count += 1
                    macd_neg_count = 0
                elif macd < macd_signal:
                    macd_neg_count += 1
                    macd_pos_count = 0
                
                vol_ok = volume > vol_ma
                
                signal = 'hold'
                if trend == 'up' and rsi_buy_count >= 0 and macd_pos_count >= 0 and vol_ok:
                    signal = 'buy'
                elif trend == 'down' and rsi_sell_count >= 0 and macd_neg_count >= 0 and vol_ok:
                    signal = 'sell'
            else:
                signal = self._simple_signal(latest, trend)
            
            # ========== 处理持仓 ==========
            if position is not None:
                # 同向信号 → 加仓
                if enable_add_position and signal == position["action"]:
                    if not allow_add:
                        pass
                    else:
                        add_size = balance * RISK_PERCENT / (atr * ATR_SL / price)
                        add_size = max(5, min(add_size, balance * 0.3))
                        position["position_size"] = position.get("position_size", 0) + add_size
                        position["add_count"] = position.get("add_count", 0) + 1
                        print(f"[回测] ➕ 加仓 @ ${price:.2f} | 仓位: ${position['position_size']:.2f}", flush=True)
                
                # 反向信号 → 平仓
                elif signal != "hold" and signal != position["action"]:
                    # 计算平仓盈亏
                    if position["action"] == "buy":
                        pnl_pct = (price - position["price"]) / position["price"] * position["leverage"]
                    else:
                        pnl_pct = (position["price"] - price) / position["price"] * position["leverage"]
                    
                    pnl = position["position_size"] * pnl_pct
                    balance += pnl
                    
                    if pnl > 0:
                        win_count += 1
                    else:
                        loss_count += 1
                    
                    trades.append({"action": position["action"], "price": price, "pnl": pnl, "type": "close", "reason": "反向信号"})
                    print(f"[回测] ⚠️ 反向信号平仓 @ ${price:.2f} | 盈亏: ${pnl:.2f} | 余额: ${balance:.2f}", flush=True)
                    
                    position = None
            
            if signal == "buy" and position is None:
                stop_loss = bb_lower - atr * ATR_SL
                take_profit_tp1 = price + (price - stop_loss) * 1.5  # 第一档止盈1.5倍
                take_profit_tp2 = price + (price - stop_loss) * 3.0  # 第二档止盈3倍
                
                position = {
                    "action": "buy", 
                    "price": price, 
                    "leverage": leverage, 
                    "entry_idx": i,
                    "stop_loss": stop_loss,
                    "take_profit_tp1": take_profit_tp1,
                    "take_profit_tp2": take_profit_tp2,
                    "atr": atr,
                    "trailing_stop": stop_loss,  # 移动止损
                    "tp1_hit": False,
                    "position_size": position_size
                }
                trades.append({"action": "buy", "price": price, "type": "open", "rsi": rsi, "sl": stop_loss, "tp1": take_profit_tp1, "tp2": take_profit_tp2, "size": position_size})
                print(f"[回测] 开多 @ ${price:.2f} | RSI: {rsi:.2f} | 仓位: ${position_size:.2f} | 止损: ${stop_loss:.2f} | 止盈1: ${take_profit_tp1:.2f} | 止盈2: ${take_profit_tp2:.2f}", flush=True)
            
            elif signal == "sell" and position is None:
                stop_loss = bb_upper + atr * ATR_SL
                take_profit_tp1 = price - (stop_loss - price) * 1.5
                take_profit_tp2 = price - (stop_loss - price) * 3.0
                
                position = {
                    "action": "sell", 
                    "price": price, 
                    "leverage": leverage, 
                    "entry_idx": i,
                    "stop_loss": stop_loss,
                    "take_profit_tp1": take_profit_tp1,
                    "take_profit_tp2": take_profit_tp2,
                    "atr": atr,
                    "trailing_stop": stop_loss,
                    "tp1_hit": False,
                    "position_size": position_size
                }
                trades.append({"action": "sell", "price": price, "type": "open", "rsi": rsi, "sl": stop_loss, "tp1": take_profit_tp1, "tp2": take_profit_tp2, "size": position_size})
                print(f"[回测] 开空 @ ${price:.2f} | RSI: {rsi:.2f} | 仓位: ${position_size:.2f} | 止损: ${stop_loss:.2f} | 止盈1: ${take_profit_tp1:.2f} | 止盈2: ${take_profit_tp2:.2f}", flush=True)
            
            elif position is not None:
                if position["action"] == "buy":
                    pnl_pct = (price - position["price"]) / position["price"] * position["leverage"]
                    hit_sl = price <= position["trailing_stop"]
                    hit_tp1 = price >= position["take_profit_tp1"] and not position["tp1_hit"]
                    hit_tp2 = position["tp1_hit"] and price >= position["take_profit_tp2"]
                    
                    # 移动止损：当价格向有利方向移动2xATR时，移到保本
                    if not position["tp1_hit"] and price >= position["price"] + position["atr"] * TRAILING_ATR:
                        position["trailing_stop"] = position["price"]  # 移动到保本
                        position["tp1_hit"] = True
                        print(f"[回测] 移动止损触发 @ ${price:.2f} | 止损移至: ${position['price']:.2f}", flush=True)
                else:
                    pnl_pct = (position["price"] - price) / position["price"] * position["leverage"]
                    hit_sl = price >= position["trailing_stop"]
                    hit_tp1 = price <= position["take_profit_tp1"] and not position["tp1_hit"]
                    hit_tp2 = position["tp1_hit"] and price <= position["take_profit_tp2"]
                    
                    if not position["tp1_hit"] and price <= position["price"] - position["atr"] * TRAILING_ATR:
                        position["trailing_stop"] = position["price"]
                        position["tp1_hit"] = True
                        print(f"[回测] 移动止损触发 @ ${price:.2f} | 止损移至: ${position['price']:.2f}", flush=True)
                
                should_close = hit_tp2 or hit_sl or (i - position["entry_idx"]) >= dynamic_max_hours
                
                # 第一档止盈后继续持有但止损移到保本
                if hit_tp1 and not hit_sl and (i - position["entry_idx"]) < dynamic_max_hours:
                    position["tp1_hit"] = True
                    position["stop_loss"] = position["price"]  # 移动止损到保本
                    print(f"[回测] ✅ 第一档止盈 @ ${price:.2f} | 继续持有 | 止损移至保本", flush=True)
                    continue
                
                if should_close:
                    pnl = position["position_size"] * pnl_pct
                    balance += pnl
                    daily_returns.append(pnl / balance if balance > 0 else 0)
                    
                    if balance > max_balance:
                        max_balance = balance
                    
                    if pnl > 0:
                        win_count += 1
                    else:
                        loss_count += 1
                    
                    trades.append({"action": position["action"], "price": price, "pnl": pnl, "type": "close"})
                    
                    emoji = "✅" if pnl >= 0 else "❌"
                    if hit_tp2:
                        reason = "第二档止盈"
                    elif hit_tp1:
                        reason = "第一档止盈"
                    elif hit_sl:
                        reason = "止损"
                    else:
                        reason = "超时"
                    print(f"[回测] {emoji} 平仓 @ ${price:.2f} | 盈亏: ${pnl:.2f} | 原因: {reason} | 余额: ${balance:.2f}", flush=True)
                    
                    position = None
                    
                    # 每月提取收益
                    if withdraw_profit and balance > base_balance:
                        withdrawn = balance - base_balance
                        total_withdrawn += withdrawn
                        balance = base_balance
                        print(f"[回测] 💰 每月提取收益: ${withdrawn:.2f} | 累计提取: ${total_withdrawn:.2f}", flush=True)
        
        # 月末检查提取收益
        if withdraw_profit and i + 1 < len(df):
            current_month = datetime.fromtimestamp(df.iloc[i]['timestamp']/1000).strftime('%Y-%m')
            next_month = datetime.fromtimestamp(df.iloc[i+1]['timestamp']/1000).strftime('%Y-%m')
            if current_month != next_month and position is None and balance > base_balance:
                withdrawn = balance - base_balance
                total_withdrawn += withdrawn
                balance = base_balance
                print(f"[回测] 💰 月末提取收益: ${withdrawn:.2f} | 累计提取: ${total_withdrawn:.2f}", flush=True)
        max_drawdown = 0
        equity_curve = [self.config.INITIAL_BALANCE]
        for t in trades:
            if t.get("type") == "close":
                equity_curve.append(equity_curve[-1] + t.get("pnl", 0))
        
        for eq in equity_curve:
            drawdown = (max_balance - eq) / max_balance if max_balance > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 计算夏普比率（简化版）
        if daily_returns:
            avg_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            sharpe = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            sharpe = 0
        
        print(f"\n=== 回测结果 (优化版) ===", flush=True)
        print(f"持仓{max_hours}h | 杠杆{leverage}x | 风险比例{RISK_PERCENT*100}%", flush=True)
        print(f"初始资金: ${self.config.INITIAL_BALANCE:.2f}", flush=True)
        if withdraw_profit:
            print(f"累计提取收益: ${total_withdrawn:.2f}", flush=True)
        print(f"最终余额: ${balance:.2f}", flush=True)
        total_return = total_withdrawn + (balance - self.config.INITIAL_BALANCE)
        print(f"总收益: ${total_return:.2f} ({total_return/self.config.INITIAL_BALANCE*100:.2f}%)", flush=True)
        print(f"最大回撤: {max_drawdown * 100:.2f}%", flush=True)
        print(f"夏普比率: {sharpe:.2f}", flush=True)
        print(f"交易次数: {len([t for t in trades if t.get('type') == 'open'])}", flush=True)
        
        total = win_count + loss_count
        if total > 0:
            print(f"胜率: {win_count / total * 100:.2f}%", flush=True)
        
        return {
            "initial_balance": self.config.INITIAL_BALANCE,
            "final_balance": balance,
            "return_pct": (balance - self.config.INITIAL_BALANCE) / self.config.INITIAL_BALANCE * 100,
            "max_drawdown": max_drawdown * 100,
            "sharpe_ratio": sharpe,
            "trades": len([t for t in trades if t.get('type') == 'open']),
            "win_rate": win_count / total * 100 if total > 0 else 0,
            "params": {"max_hours": max_hours, "leverage": leverage, "risk_percent": RISK_PERCENT}
        }
    
    def _simple_signal(self, row, trend="neutral") -> str:
        """优化的技术信号 - 只在趋势明显的市场中交易"""
        rsi = row.get('rsi', 50)
        macd = row.get('macd', 0)
        macd_signal = row.get('macd_signal', 0)
        macd_hist = row.get('macd_hist', 0)
        adx = row.get('adx', 0)
        close = row.get('close', 0)
        ma20 = row.get('ma20', 0)
        bb_lower = row.get('bb_lower', close * 0.98)
        bb_middle = row.get('bb_middle', close)
        
        # ========== 买入信号 (只在上涨趋势中做多) ==========
        if trend == "up":
            if rsi < 40 and macd > macd_signal:
                return "buy"
            if rsi < 35 and adx > 20:
                return "buy"
            if rsi < 30 and close < bb_middle:
                return "buy"
        
        # ========== 卖出信号 (只在下跌趋势中做空) ==========
        if trend == "down":
            if rsi > 60 and macd < macd_signal:
                return "sell"
            if rsi > 55 and close < ma20:
                return "sell"
            if macd < macd_signal and macd_hist < 0 and adx > 20:
                return "sell"
        
        return "hold"
    
    def start(self):
        print("=" * 50)
        print("BTC TradingAgents 交易系统启动")
        print(f"模式: {'模拟盘' if self.config.DRY_RUN else '实盘'}")
        print(f"交易对: {self.config.TRADING_INSTRUMENT}")
        print("=" * 50)
        
        self.fetch_and_store_data()
        
        initial_signal = self.run_analysis(force=True)
        if initial_signal:
            self.execute_signal(initial_signal)
        
        scheduler = BlockingScheduler()
        
        scheduler.add_job(self.fetch_and_store_data, 'interval', hours=1, id="fetch_data")
        
        scheduler.add_job(
            self.run_analysis, 'cron', hour='0,4,8,12,16,20', id="analysis",
            minute=0
        )
        
        scheduler.add_job(self.check_positions, 'interval', minutes=5, id="check_positions")
        
        print("调度器已启动，按Ctrl+C退出")
        
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("\n系统退出")


def main():
    parser = argparse.ArgumentParser(description="BTC TradingAgents Trader")
    parser.add_argument("--backtest", action="store_true", help="运行回测")
    parser.add_argument("--days", type=int, default=30, help="回测天数")
    parser.add_argument("--version", type=str, default='original', choices=['original', 'improve1', 'improve2', 'improve_both', 'dynamic', 'moderate'], help="策略版本")
    parser.add_argument("--quarter", type=str, choices=['Q1','Q2','Q3','Q4'], help="按季度测试")
    parser.add_argument("--once", action="store_true", help="运行一次分析并执行")
    
    args = parser.parse_args()
    
    trader = BTCTader()
    
    if args.backtest:
        result = trader.run_backtest(args.days, strategy_version=args.version, quarter=args.quarter)
        
        if result:
            message = f"""
📊 *回测结果*

初始资金: ${result['initial_balance']:.2f}
最终余额: ${result['final_balance']:.2f}
收益率: {result['return_pct']:.2f}%
交易次数: {result['trades']}
胜率: {result['win_rate']:.2f}%
"""
            trader.notification.send_message(message)
    elif args.once:
        trader.fetch_and_store_data()
        signal = trader.run_analysis(force=True)
        if signal:
            print(f"信号: {signal}")
            trader.execute_signal(signal)
    else:
        trader.start()


if __name__ == "__main__":
    main()
