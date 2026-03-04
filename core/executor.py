from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd


class Executor(ABC):
    """执行器抽象基类"""
    
    @abstractmethod
    def get_position(self) -> Optional[Dict]:
        """获取当前持仓"""
        pass
    
    @abstractmethod
    def open_position(self, action: str, price: float, amount: float,
                      leverage: int, stop_loss: float, tp1: float, tp2: float,
                      atr: float, reason: str) -> bool:
        """开仓"""
        pass
    
    @abstractmethod
    def add_position(self, price: float, amount: float) -> bool:
        """加仓"""
        pass
    
    @abstractmethod
    def close_position(self, price: float, reason: str) -> Optional[float]:
        """平仓"""
        pass
    
    @abstractmethod
    def update_position(self, updates: Dict) -> None:
        """更新持仓信息"""
        pass
    
    @abstractmethod
    def get_balance(self) -> float:
        """获取余额"""
        pass
    
    @abstractmethod
    def withdraw_profit(self) -> Optional[float]:
        """提取收益"""
        pass


class BacktestExecutor(Executor):
    """回测执行器"""
    
    # OKX U本位合约手续费率
    MAKER_FEE = 0.0002  # 0.02%
    TAKER_FEE = 0.0005  # 0.05%
    
    def __init__(self, initial_balance: float = 100.0, use_maker_fee: bool = False):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.position = None
        self.total_withdrawn = 0
        self.base_balance = 100.0
        self.trades = []
        self.daily_returns = []
        self.max_balance = initial_balance
        self.total_fees = 0
        self.use_maker_fee = use_maker_fee
        self.fee_rate = self.MAKER_FEE if use_maker_fee else self.TAKER_FEE
    
    def get_position(self) -> Optional[Dict]:
        return self.position
    
    def open_position(self, action: str, price: float, amount: float,
                    leverage: int, stop_loss: float, tp1: float, tp2: float,
                    atr: float, reason: str) -> bool:
        # 开仓扣手续费（按合约价值计算：保证金 × 杠杆 × 费率）
        contract_value = amount * leverage
        open_fee = contract_value * self.fee_rate
        self.balance -= open_fee
        self.total_fees += open_fee
        
        self.position = {
            "action": action,
            "entry_price": price,
            "amount": amount,
            "leverage": leverage,
            "stop_loss": stop_loss,
            "trailing_stop": stop_loss,
            "take_profit_tp1": tp1,
            "take_profit_tp2": tp2,
            "tp1_hit": False,
            "atr": atr,
            "entry_time": pd.Timestamp.now(),
            "add_count": 0,
            "add_prices": []
        }
        
        self.trades.append({
            "action": action,
            "price": price,
            "type": "open",
            "amount": amount,
            "reason": reason
        })
        
        return True
    
    def add_position(self, price: float, amount: float) -> bool:
        if not self.position:
            return False
        
        # 加仓扣手续费（按合约价值计算：保证金 × 杠杆 × 费率）
        leverage = self.position.get("leverage", 10)
        contract_value = amount * leverage
        add_fee = contract_value * self.fee_rate
        self.balance -= add_fee
        self.total_fees += add_fee
        
        old_amount = self.position["amount"]
        old_price = self.position["entry_price"]
        new_amount = old_amount + amount
        new_price = (old_amount * old_price + amount * price) / new_amount
        
        self.position["amount"] = new_amount
        self.position["entry_price"] = new_price
        self.position["add_count"] = self.position.get("add_count", 0) + 1
        self.position["add_prices"].append(price)
        
        return True
    
    def close_position(self, price: float, reason: str) -> Optional[float]:
        if not self.position:
            return None
        
        action = self.position["action"]
        entry_price = self.position["entry_price"]
        amount = self.position["amount"]
        leverage = self.position["leverage"]
        
        if action == "buy":
            pnl_pct = (price - entry_price) / entry_price * leverage
        else:
            pnl_pct = (entry_price - price) / entry_price * leverage
        
        pnl = amount * pnl_pct
        
        # 平仓扣手续费（按合约价值计算：保证金 × 杠杆 × 费率）
        contract_value = amount * leverage
        close_fee = contract_value * self.fee_rate
        self.balance += pnl - close_fee
        self.total_fees += close_fee
        
        # 补充本金：如果余额<100，从已提取中补充
        if self.balance < self.base_balance and self.total_withdrawn > 0:
            needed = self.base_balance - self.balance
            if self.total_withdrawn >= needed:
                self.total_withdrawn -= needed
                self.balance = self.base_balance
            else:
                self.balance += self.total_withdrawn
                self.total_withdrawn = 0
        
        if self.balance > self.max_balance:
            self.max_balance = self.balance
        
        self.trades.append({
            "action": action,
            "price": price,
            "pnl": pnl,
            "type": "close",
            "reason": reason
        })
        
        self.position = None
        
        return pnl
    
    def update_position(self, updates: Dict) -> None:
        if self.position:
            self.position.update(updates)
    
    def get_balance(self) -> float:
        return self.balance
    
    def withdraw_profit(self) -> Optional[float]:
        if self.balance > self.base_balance:
            withdrawn = self.balance - self.base_balance
            self.total_withdrawn += withdrawn
            self.balance = self.base_balance
            return withdrawn
        return None
    
    def get_results(self) -> Dict:
        """获取回测结果"""
        wins = [t for t in self.trades if t.get("type") == "close" and t.get("pnl", 0) > 0]
        losses = [t for t in self.trades if t.get("type") == "close" and t.get("pnl", 0) <= 0]
        
        total_trades = len(wins) + len(losses)
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        
        total_return = self.balance + self.total_withdrawn - self.initial_balance
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.balance,
            "total_withdrawn": self.total_withdrawn,
            "total_return": total_return,
            "return_pct": total_return / self.initial_balance * 100,
            "trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_fees": self.total_fees,
            "fee_rate": self.fee_rate,
            "net_return": total_return - self.total_fees,
            "net_return_pct": (total_return - self.total_fees) / self.initial_balance * 100,
            "trades_detail": self.trades
        }


class LiveExecutor(Executor):
    """实盘执行器 - 使用OKX API"""
    
    def __init__(self, config, okx_client, data_manager, notification):
        self.config = config
        self.okx_client = okx_client
        self.data_manager = data_manager
        self.notification = notification
        self.balance = config.INITIAL_BALANCE
        self.base_balance = config.BASE_BALANCE
        self.total_withdrawn = 0
        self.last_withdraw_month = None
        self.position = None
    
    def get_position(self) -> Optional[Dict]:
        return self.position
    
    def open_position(self, action: str, price: float, amount: float,
                    leverage: int, stop_loss: float, tp1: float, tp2: float,
                    atr: float, reason: str) -> bool:
        if self.config.DRY_RUN:
            print(f"[DRY RUN] {'买入' if action == 'buy' else '卖出'} {amount} USDT @ ${price}")
        
        self.position = {
            "action": action,
            "entry_price": price,
            "amount": amount,
            "leverage": leverage,
            "stop_loss": stop_loss,
            "trailing_stop": stop_loss,
            "take_profit_tp1": tp1,
            "take_profit_tp2": tp2,
            "tp1_hit": False,
            "atr": atr,
            "entry_time": datetime.now(),
            "add_count": 0
        }
        
        self.notification.send_trade_signal(action, price, amount, leverage, reason)
        return True
    
    def add_position(self, price: float, amount: float) -> bool:
        if not self.position:
            return False
        
        old_amount = self.position["amount"]
        old_price = self.position["entry_price"]
        new_amount = old_amount + amount
        new_price = (old_amount * old_price + amount * price) / new_amount
        
        self.position["amount"] = new_amount
        self.position["entry_price"] = new_price
        self.position["add_count"] = self.position.get("add_count", 0) + 1
        
        if self.config.DRY_RUN:
            print(f"[DRY RUN] ➕ 加仓 @ ${price:.2f}, 仓位: ${new_amount:.2f}")
        
        return True
    
    def close_position(self, price: float, reason: str) -> Optional[float]:
        if not self.position:
            return None
        
        action = self.position["action"]
        entry_price = self.position["entry_price"]
        amount = self.position["amount"]
        leverage = self.position["leverage"]
        
        if action == "buy":
            pnl = (price - entry_price) / entry_price * amount * leverage
        else:
            pnl = (entry_price - price) / entry_price * amount * leverage
        
        self.balance += pnl
        self.position = None
        
        if self.config.DRY_RUN:
            print(f"[DRY RUN] 平仓 @ ${price}, 盈亏: ${pnl:.2f}")
        
        self.notification.send_trade_result(action, price, pnl, reason)
        return pnl
    
    def update_position(self, updates: Dict) -> None:
        if self.position:
            self.position.update(updates)
    
    def get_balance(self) -> float:
        return self.balance
    
    def withdraw_profit(self) -> Optional[float]:
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        
        if self.last_withdraw_month == current_month:
            return None
        
        if self.balance > self.base_balance:
            withdrawn = self.balance - self.base_balance
            self.total_withdrawn += withdrawn
            self.balance = self.base_balance
            self.last_withdraw_month = current_month
            
            msg = f"💰 收益提取: ${withdrawn:.2f}"
            self.notification.send_message(msg)
            
            return withdrawn
        
        return None
