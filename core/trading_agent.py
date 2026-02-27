import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict
from config import Config


class TradingAgent:
    """简单指标策略 - 用于Equilibrium实盘"""
    
    def __init__(self, config: type = Config):
        self.config = config
    
    def analyze(self, ticker: str, date: str, market_data: Dict) -> Dict:
        price = market_data.get("price", 0)
        indicators = market_data.get("indicators", {})
        
        signal = self._get_signal(indicators)
        
        if signal == "buy":
            stop_loss, take_profit = self._calc_sl_tp(price, indicators, "buy")
            return {
                "action": "buy",
                "confidence": 0.8,
                "position_size": 10,
                "leverage": 15,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": "RSI超卖+MACD金叉",
                "approved": True
            }
        elif signal == "sell":
            stop_loss, take_profit = self._calc_sl_tp(price, indicators, "sell")
            return {
                "action": "sell",
                "confidence": 0.8,
                "position_size": 10,
                "leverage": 15,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": "RSI超买+MACD死叉",
                "approved": True
            }
        
        return {"action": "hold", "confidence": 0, "approved": True}
    
    def _get_signal(self, indicators: Dict) -> str:
        rsi = indicators.get("rsi", 50)
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)
        macd_hist = indicators.get("macd_hist", 0)
        adx = indicators.get("adx", 0)
        close = indicators.get("close", 0)
        ma20 = indicators.get("ma20", 0)
        
        if rsi < 30 and macd > macd_signal:
            return "buy"
        if rsi < 35 and macd_hist > 0:
            return "buy"
        if rsi < 25 and adx > 30:
            return "buy"
        
        if rsi > 70 and macd < macd_signal:
            return "sell"
        if rsi > 65 and close < ma20:
            return "sell"
        if macd < macd_signal and macd_hist < 0 and adx > 25:
            return "sell"
        
        return "hold"
    
    def _calc_sl_tp(self, price: float, indicators: Dict, action: str):
        bb_lower = indicators.get("bb_lower", price * 0.98)
        bb_upper = indicators.get("bb_upper", price * 1.02)
        atr = indicators.get("atr", price * 0.02)
        
        if action == "buy":
            stop_loss = bb_lower - atr * 1.5
            take_profit = price + (price - stop_loss) * 2.5
        else:
            stop_loss = bb_upper + atr * 1.5
            take_profit = price - (stop_loss - price) * 2.5
        
        return stop_loss, take_profit
