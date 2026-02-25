from typing import Optional, Dict, Any
from datetime import datetime
from config import Config
from core.data_manager import DataManager
from core.notification import NotificationManager


class TradeExecutor:
    def __init__(self, config: type = Config, 
                 data_manager: DataManager = None,
                 notification: NotificationManager = None):
        self.config = config
        self.data_manager = data_manager or DataManager()
        self.notification = notification or NotificationManager(config)
        self.balance = config.INITIAL_BALANCE
        self.position = None
    
    def open_position(self, action: str, price: float, amount: float, 
                     leverage: int, reason: str = "",
                     stop_loss: float = None, take_profit: float = None) -> bool:
        if self.config.DRY_RUN:
            sl_info = f", 止损: ${stop_loss:.2f}" if stop_loss else ""
            tp_info = f", 止盈: ${take_profit:.2f}" if take_profit else ""
            print(f"[DRY RUN] {'买入' if action == 'buy' else '卖出'} {amount} USDT @ ${price}, 杠杆: {leverage}x{sl_info}{tp_info}")
        
        self.position = {
            "action": action,
            "entry_price": price,
            "amount": amount,
            "leverage": leverage,
            "reason": reason,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "timestamp": datetime.now().timestamp()
        }
        
        self.data_manager.save_trade(
            action=action,
            price=price,
            amount=amount,
            leverage=leverage,
            status="open",
            reason=reason
        )
        
        self.notification.send_trade_signal(action, price, amount, leverage, reason)
        
        return True
    
    def close_position(self, close_price: float, reason: str = "") -> Optional[float]:
        if not self.position:
            return None
        
        action = self.position["action"]
        entry_price = self.position["entry_price"]
        amount = self.position["amount"]
        leverage = self.position["leverage"]
        
        if action == "buy":
            pnl = (close_price - entry_price) / entry_price * amount * leverage
        else:
            pnl = (entry_price - close_price) / entry_price * amount * leverage
        
        self.balance += pnl
        
        if self.config.DRY_RUN:
            print(f"[DRY RUN] 平仓 @ ${close_price}, 盈亏: ${pnl:.2f}")
        
        self.data_manager.save_trade(
            action=f"close_{action}",
            price=close_price,
            amount=amount,
            leverage=leverage,
            pnl=pnl,
            status="closed",
            reason=reason
        )
        
        self.data_manager.save_balance(self.balance, f"close_{action}")
        self.notification.send_trade_result(action, close_price, pnl, "closed")
        
        self.position = None
        
        return pnl
    
    def check_stop_loss(self, current_price: float) -> bool:
        if not self.position:
            return False
        
        entry_price = self.position["entry_price"]
        action = self.position["action"]
        ai_stop_loss = self.position.get("stop_loss")
        
        # 优先使用AI给出的止损价格
        if ai_stop_loss:
            if action == "buy" and current_price <= ai_stop_loss:
                self.close_position(current_price, f"止损 @ ${ai_stop_loss:.2f}")
                return True
            elif action == "sell" and current_price >= ai_stop_loss:
                self.close_position(current_price, f"止损 @ ${ai_stop_loss:.2f}")
                return True
        else:
            # 使用配置文件中的默认值
            if action == "buy":
                loss_ratio = (entry_price - current_price) / entry_price
            else:
                loss_ratio = (current_price - entry_price) / entry_price
            
            if loss_ratio >= self.config.STOP_LOSS_RATIO:
                self.close_position(current_price, "止损")
                return True
        
        return False
    
    def check_take_profit(self, current_price: float) -> bool:
        if not self.position:
            return False
        
        entry_price = self.position["entry_price"]
        action = self.position["action"]
        ai_take_profit = self.position.get("take_profit")
        
        # 优先使用AI给出的止盈价格
        if ai_take_profit:
            if action == "buy" and current_price >= ai_take_profit:
                self.close_position(current_price, f"止盈 @ ${ai_take_profit:.2f}")
                return True
            elif action == "sell" and current_price <= ai_take_profit:
                self.close_position(current_price, f"止盈 @ ${ai_take_profit:.2f}")
                return True
        else:
            # 使用配置文件中的默认值
            if action == "buy":
                profit_ratio = (current_price - entry_price) / entry_price
            else:
                profit_ratio = (entry_price - current_price) / entry_price
            
            if profit_ratio >= self.config.TAKE_PROFIT_RATIO:
                self.close_position(current_price, "止盈")
                return True
        
        return False
    
    def get_balance(self) -> float:
        return self.balance
    
    def get_position(self) -> Optional[Dict]:
        return self.position
