import requests
from typing import Optional
from config import Config


class NotificationManager:
    def __init__(self, config: type = Config):
        self.config = config
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_ids = config.TELEGRAM_CHAT_IDS if hasattr(config, 'TELEGRAM_CHAT_IDS') else [config.TELEGRAM_CHAT_ID]
    
    def send_message(self, message: str) -> bool:
        if not self.token or not self.chat_ids:
            print("Telegram not configured")
            return False
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        
        success = True
        for chat_id in self.chat_ids:
            data = {
                "chat_id": chat_id.strip(),
                "text": message,
                "parse_mode": "Markdown"
            }
            
            try:
                response = requests.post(url, json=data, timeout=10)
                if response.status_code != 200:
                    success = False
            except Exception as e:
                print(f"Failed to send telegram: {e}")
                success = False
        
        return success
    
    def send_trade_signal(self, action: str, price: float, amount: float, 
                          leverage: int, reason: str) -> bool:
        emoji = "🟢" if action == "buy" else "🔴"
        message = f"""
{emoji} *交易信号*

操作: *{action.upper()}*
价格: ${price:,.2f}
数量: {amount} USDT
杠杆: {leverage}x

原因:
{reason}
"""
        return self.send_message(message)
    
    def send_trade_result(self, action: str, price: float, pnl: float, 
                          status: str) -> bool:
        emoji = "✅" if pnl >= 0 else "❌"
        message = f"""
{emoji} *交易结果*

操作: {action}
价格: ${price:,.2x}
盈亏: ${pnl:.2f}
状态: {status}
"""
        return self.send_message(message)
    
    def send_daily_report(self, balance: float, trades: int, pnl: float) -> bool:
        message = f"""
📊 *每日报告*

余额: ${balance:,.2f}
交易次数: {trades}
总盈亏: ${pnl:,.2f}
"""
        return self.send_message(message)
    
    def send_error(self, error: str) -> bool:
        message = f"""
⚠️ *系统错误*

{error}
"""
        return self.send_message(message)
