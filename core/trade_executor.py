from typing import Optional, Dict, Any
from datetime import datetime
from config import Config
from core.data_manager import DataManager
from core.notification import NotificationManager
from core.okx_client import OKXClient


class TradeExecutor:
    def __init__(self, config: type = Config, 
                 data_manager: DataManager = None,
                 notification: NotificationManager = None,
                 okx_client: OKXClient = None):
        self.config = config
        self.data_manager = data_manager or DataManager()
        self.notification = notification or NotificationManager(config)
        self.okx_client = okx_client or OKXClient(config)
        self.balance = config.INITIAL_BALANCE
        self.base_balance = config.BASE_BALANCE
        self.withdraw_profit = config.WITHDRAW_PROFIT
        self.total_withdrawn = 0
        self.last_withdraw_month = None
        self.position = None
        self.max_hours = 12  # 持仓超时时间
        self.enable_add_position = True  # 加仓开关
        self.add_count = 0  # 加仓次数
    
    def open_position(self, action: str, price: float, amount: float, 
                     leverage: int, reason: str = "",
                     stop_loss: float = None, take_profit_tp1: float = None, 
                     take_profit_tp2: float = None, atr: float = None) -> bool:
        # 实盘下单
        if not self.config.DRY_RUN:
            order = {
                'instId': 'BTC-USDT-SWAP',
                'tdMode': 'isolated',
                'side': action,
                'ordType': 'market',
                'sz': str(int(amount))
            }
            result = self.okx_client._request('POST', '/api/v5/trade/order', order)
            if result.get('code') != '0':
                print(f"开仓失败: {result}")
                return False
            print(f"实盘开仓成功: {action} {amount} USDT")
        else:
            sl_info = f", 止损: ${stop_loss:.2f}" if stop_loss else ""
            tp1_info = f", 止盈1: ${take_profit_tp1:.2f}" if take_profit_tp1 else ""
            tp2_info = f", 止盈2: ${take_profit_tp2:.2f}" if take_profit_tp2 else ""
            print(f"[DRY RUN] {'买入' if action == 'buy' else '卖出'} {amount} USDT @ ${price}, 杠杆: {leverage}x{sl_info}{tp1_info}{tp2_info}")
        
        self.position = {
            "action": action,
            "entry_price": price,
            "amount": amount,
            "leverage": leverage,
            "reason": reason,
            "stop_loss": stop_loss,
            "trailing_stop": stop_loss,  # 移动止损
            "take_profit_tp1": take_profit_tp1,
            "take_profit_tp2": take_profit_tp2,
            "tp1_hit": False,
            "atr": atr,
            "entry_time": datetime.now(),
            "add_count": 0,
            "add_prices": []
        }
        self.add_count = 0
        
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
    
    def add_position(self, price: float, amount: float) -> bool:
        """加仓"""
        if not self.position or not self.enable_add_position:
            return False
        
        # 不限制加仓次数（与回测一致）
        
        old_amount = self.position["amount"]
        old_price = self.position["entry_price"]
        new_amount = old_amount + amount
        new_price = (old_amount * old_price + amount * price) / new_amount
        
        self.position["amount"] = new_amount
        self.position["entry_price"] = new_price
        self.position["add_count"] = self.position.get("add_count", 0) + 1
        self.position["add_prices"].append(price)
        self.add_count = self.position["add_count"]
        
        if self.config.DRY_RUN:
            print(f"[DRY RUN] ➕ 加仓 @ ${price:.2f}, 仓位: ${new_amount:.2f}")
        
        return True
    
    def close_position(self, close_price: float, reason: str = "") -> Optional[float]:
        if not self.position:
            return None
        
        action = self.position["action"]
        entry_price = self.position["entry_price"]
        amount = self.position["amount"]
        leverage = self.position["leverage"]
        
        # 实盘平仓
        if not self.config.DRY_RUN:
            close_side = 'sell' if action == 'buy' else 'buy'
            order = {
                'instId': 'BTC-USDT-SWAP',
                'tdMode': 'isolated',
                'side': close_side,
                'ordType': 'market',
                'sz': str(int(amount)),
                'posSide': 'net'
            }
            result = self.okx_client._request('POST', '/api/v5/trade/order', order)
            if result.get('code') != '0':
                print(f"平仓失败: {result}")
                return None
            print(f"实盘平仓成功: {close_side} {amount} USDT")
        
        if action == "buy":
            pnl = (close_price - entry_price) / entry_price * amount * leverage
        else:
            pnl = (entry_price - close_price) / entry_price * amount * leverage
        
        self.balance += pnl
        
        if self.config.DRY_RUN:
            print(f"[DRY RUN] 平仓 @ ${close_price}, 盈亏: ${pnl:.2f}, 原因: {reason}")
        
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
        self.notification.send_trade_result(action, close_price, pnl, reason)
        
        self.position = None
        self.add_count = 0
        
        return pnl
    
    def check_stop_loss(self, current_price: float) -> bool:
        """检查止损（含移动止损）"""
        if not self.position:
            return False
        
        action = self.position["action"]
        trailing_stop = self.position.get("trailing_stop")
        
        # 检查移动止损
        if trailing_stop:
            if action == "buy" and current_price <= trailing_stop:
                self.close_position(current_price, "止损")
                return True
            elif action == "sell" and current_price >= trailing_stop:
                self.close_position(current_price, "止损")
                return True
        
        return False
    
    def check_take_profit(self, current_price: float) -> bool:
        """检查分批止盈"""
        if not self.position:
            return False
        
        action = self.position["action"]
        entry_price = self.position["entry_price"]
        tp1 = self.position.get("take_profit_tp1")
        tp2 = self.position.get("take_profit_tp2")
        tp1_hit = self.position.get("tp1_hit", False)
        
        # 第一档止盈
        if not tp1_hit and tp1:
            if action == "buy" and current_price >= tp1:
                self.position["tp1_hit"] = True
                self.position["trailing_stop"] = entry_price  # 移动止损到保本
                if self.config.DRY_RUN:
                    print(f"[DRY RUN] ✅ 第一档止盈触发, 止损移至保本")
                return True
            elif action == "sell" and current_price <= tp1:
                self.position["tp1_hit"] = True
                self.position["trailing_stop"] = entry_price
                if self.config.DRY_RUN:
                    print(f"[DRY RUN] ✅ 第一档止盈触发, 止损移至保本")
                return True
        
        # 第二档止盈
        if tp1_hit and tp2:
            if action == "buy" and current_price >= tp2:
                self.close_position(current_price, "第二档止盈")
                return True
            elif action == "sell" and current_price <= tp2:
                self.close_position(current_price, "第二档止盈")
                return True
        
        return False
    
    def check_timeout(self, current_price: float) -> bool:
        """检查持仓超时"""
        if not self.position:
            return False
        
        entry_time = self.position.get("entry_time")
        if not entry_time:
            return False
        
        hours_held = (datetime.now() - entry_time).total_seconds() / 3600
        
        if hours_held >= self.max_hours:
            self.close_position(current_price, f"超时({int(hours_held)}h)")
            return True
        
        return False
    
    def get_balance(self) -> float:
        return self.balance
    
    def get_position(self) -> Optional[Dict]:
        return self.position
    
    def check_and_withdraw_profit(self) -> Optional[float]:
        """每月检查并提取收益，保持基础余额"""
        if not self.withdraw_profit:
            return None
        
        if self.position:
            return None
        
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        
        if self.last_withdraw_month == current_month:
            return None
        
        if self.balance > self.base_balance:
            withdrawn = self.balance - self.base_balance
            self.total_withdrawn += withdrawn
            self.balance = self.base_balance
            self.last_withdraw_month = current_month
            
            msg = f"💰 每月收益提取\n提取金额: ${withdrawn:.2f}\n当前余额: ${self.balance:.2f}\n累计提取: ${self.total_withdrawn:.2f}"
            print(msg)
            self.notification.send_message(msg)
            
            self.data_manager.save_balance(self.balance, f"withdraw_{current_month}")
            
            return withdrawn
        
        return None
    
    def get_add_count(self) -> int:
        """获取加仓次数"""
        if self.position:
            return self.position.get("add_count", 0)
        return 0
