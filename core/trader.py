from typing import Optional, Dict, Any, List
import pandas as pd
from utils.indicators import calculate_all_indicators


class Trader:
    """核心交易逻辑 - V3"""
    
    def __init__(self, config, executor):
        self.config = config
        self.executor = executor
        
        # 策略参数
        self.atr_sl = 2.0
        self.risk_percent = 0.02
        self.trailing_atr = 1.0
        self.max_hours = 12
        self.enable_add_position = True
        self.max_add_count = 3
        
        # 持仓状态
        self.position = None
    
    def analyze(self, df: pd.DataFrame, current_price: float, version: str = 'moderate') -> Optional[Dict]:
        """分析市场，返回信号
        version: 'original', 'moderate'
        """
        if df.empty or len(df) < 50:
            return None
        
        latest = df.iloc[-1]
        
        # 趋势判断
        trend = self._get_trend(df)
        
        # 判断震荡市
        is_ranging = self._is_ranging(df)
        
        # 获取交易信号
        signal = self._get_signal(latest, trend)
        
        if signal == "hold":
            return None
        
        # 计算止损止盈
        stop_loss, tp1, tp2, atr = self._calculate_stoploss_takeprofit(
            latest, current_price, signal
        )
        
        # 计算仓位
        position_size = self.calculate_position_size(current_price, atr)
        
        # moderate策略：震荡市仓位减半
        if version == 'moderate' and is_ranging:
            position_size = position_size * 0.5
        
        return {
            "action": signal,
            "confidence": 0.8,
            "stop_loss": stop_loss,
            "take_profit_tp1": tp1,
            "take_profit_tp2": tp2,
            "atr": atr,
            "trend": trend,
            "rsi": latest.get('rsi', 50),
            "is_ranging": is_ranging,
            "position_size": position_size,
            "approved": True
        }
    
    def get_max_hours(self, df: pd.DataFrame) -> int:
        """获取持仓超时时间"""
        is_ranging = self._is_ranging(df)
        return 4 if is_ranging else 12
    
    def can_add_position(self, df: pd.DataFrame) -> bool:
        """是否可以加仓"""
        is_ranging = self._is_ranging(df)
        return not is_ranging  # 震荡市禁止加仓
    
    def check_position(self, df: pd.DataFrame, current_price: float) -> Optional[Dict]:
        """检查持仓状态，返回操作指令"""
        position = self.executor.get_position()
        
        if not position:
            return None
        
        action = position.get("action")
        entry_price = position.get("entry_price")
        stop_loss = position.get("stop_loss")
        trailing_stop = position.get("trailing_stop")
        tp1 = position.get("take_profit_tp1")
        tp2 = position.get("take_profit_tp2")
        tp1_hit = position.get("tp1_hit", False)
        entry_time = position.get("entry_time")
        add_count = position.get("add_count", 0)
        
        # 检查第二档止盈
        if tp1_hit and tp2:
            if (action == "buy" and current_price >= tp2) or \
               (action == "sell" and current_price <= tp2):
                return {"action": "close", "reason": "第二档止盈"}
        
        # 检查止损（含移动止损）
        if trailing_stop:
            if (action == "buy" and current_price <= trailing_stop) or \
               (action == "sell" and current_price >= trailing_stop):
                return {"action": "close", "reason": "止损"}
        
        # 检查第一档止盈
        if not tp1_hit and tp1:
            if (action == "buy" and current_price >= tp1) or \
               (action == "sell" and current_price <= tp1):
                return {"action": "take_profit_1", "new_trailing_stop": entry_price}
        
        # 检查超时
        if entry_time:
            hours_held = (pd.Timestamp.now() - entry_time).total_seconds() / 3600
            if hours_held >= self.max_hours:
                return {"action": "close", "reason": f"超时({int(hours_held)}h)"}
        
        # 检查反向信号
        if len(df) >= 2:
            latest = df.iloc[-1]
            trend = self._get_trend(df)
            signal = self._get_signal(latest, trend)
            
            if signal != "hold" and signal != action:
                return {"action": "close", "reason": "反向信号"}
            
            # 检查加仓（同向信号）
            if signal == action and self.enable_add_position and add_count < self.max_add_count:
                return {"action": "add", "add_count": add_count + 1}
        
        return None
    
    def on_new_signal(self, signal: Dict, current_price: float) -> Optional[Dict]:
        """收到新信号时的处理"""
        position = self.executor.get_position()
        
        if not position:
            # 无持仓：开仓
            return {
                "action": "open",
                "signal": signal,
                "price": current_price
            }
        
        # 有持仓：检查是否加仓或平仓
        action = position.get("action")
        
        if signal["action"] == action and self.enable_add_position:
            add_count = position.get("add_count", 0)
            if add_count < self.max_add_count:
                return {
                    "action": "add",
                    "price": current_price,
                    "amount": self.config.POSITION_SIZE * 0.3
                }
        elif signal["action"] != action:
            return {
                "action": "close",
                "reason": "反向信号",
                "price": current_price
            }
        
        return None
    
    def _get_trend(self, df: pd.DataFrame) -> str:
        """判断趋势"""
        if len(df) < 24:
            return "neutral"
        
        ma20_now = df.iloc[-1].get('ma20')
        ma20_prev = df.iloc[-24].get('ma20')
        
        if not ma20_now or not ma20_prev:
            return "neutral"
        
        if ma20_now > ma20_prev * 1.01:
            return "up"
        elif ma20_now < ma20_prev * 0.99:
            return "down"
        else:
            return "neutral"
    
    def _is_ranging(self, df: pd.DataFrame) -> bool:
        """判断是否震荡市"""
        if len(df) < 25:
            return False
        
        latest = df.iloc[-1]
        adx = latest.get('adx', 0)
        
        return adx < 25
    
    def _get_signal(self, latest: pd.Series, trend: str) -> str:
        """获取交易信号 - V2原始策略"""
        rsi = latest.get('rsi', 50)
        
        rsi_buy = rsi < 40
        rsi_sell = rsi > 60
        
        if trend == 'up' and rsi_buy:
            return 'buy'
        elif trend == 'down' and rsi_sell:
            return 'sell'
        
        return 'hold'
    
    def _calculate_stoploss_takeprofit(self, latest: pd.Series, 
                                         current_price: float, 
                                         signal: str) -> tuple:
        """计算止损止盈"""
        bb_lower = latest.get('bb_lower', current_price * 0.98)
        bb_upper = latest.get('bb_upper', current_price * 1.02)
        atr = latest.get('atr', current_price * 0.02)
        
        if signal == "buy":
            stop_loss = bb_lower - atr * self.atr_sl
            tp1 = current_price + (current_price - stop_loss) * 1.5
            tp2 = current_price + (current_price - stop_loss) * 3.0
        else:
            stop_loss = bb_upper + atr * self.atr_sl
            tp1 = current_price - (stop_loss - current_price) * 1.5
            tp2 = current_price - (stop_loss - current_price) * 3.0
        
        return stop_loss, tp1, tp2, atr
    
    def calculate_position_size(self, current_price: float, atr: float) -> float:
        """计算仓位大小 - V2原始逻辑"""
        if atr == 0:
            return self.config.POSITION_SIZE
        
        stop_pct = self.atr_sl * atr / current_price
        if stop_pct == 0:
            return self.config.POSITION_SIZE
        
        position = current_price * self.risk_percent / stop_pct
        # V2原始逻辑：最大仓位是余额的50%
        return max(5, min(position, self.executor.get_balance() * 0.5))
    
    def calculate_add_size(self, current_price: float, atr: float) -> float:
        """计算加仓大小 - V2原始逻辑"""
        if atr == 0:
            return self.config.POSITION_SIZE * 0.3
        
        stop_pct = self.atr_sl * atr / current_price
        if stop_pct == 0:
            return self.config.POSITION_SIZE * 0.3
        
        # V2原始逻辑：加仓是余额的30%
        add_size = self.executor.get_balance() * 0.3
        return max(5, add_size)
