import requests
import threading
import time
from typing import Optional
from config import Config


class TelegramBot:
    def __init__(self, config: type = Config):
        self.config = config
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_ids = config.TELEGRAM_CHAT_IDS if hasattr(config, 'TELEGRAM_CHAT_IDS') else [config.TELEGRAM_CHAT_ID]
        self.offset = 0
        self.running = False
        self.trader = None
        
    def send_message(self, message: str, chat_id: str = None) -> bool:
        if not self.token or not self.chat_ids:
            return False
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        
        success = True
        targets = [chat_id] if chat_id else self.chat_ids
        
        for cid in targets:
            data = {
                "chat_id": cid.strip(),
                "text": message,
                "parse_mode": "Markdown"
            }
            
            try:
                response = requests.post(url, json=data, timeout=10)
                if response.status_code != 200:
                    success = False
            except Exception:
                success = False
        
        return success
    
    def start_polling(self, trader=None):
        if not self.token:
            print("Telegram bot token not configured")
            return
        
        self.trader = trader
        self.running = True
        
        thread = threading.Thread(target=self._poll_loop, daemon=True)
        thread.start()
        print("Telegram 命令处理器已启动")
    
    def stop_polling(self):
        self.running = False
    
    def _poll_loop(self):
        while self.running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._handle_update(update)
                    self.offset = update['update_id'] + 1
            except Exception as e:
                print(f"Telegram polling error: {e}")
            
            time.sleep(2)
    
    def _get_updates(self):
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {"offset": self.offset, "timeout": 30}
        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return data.get("result", [])
        except:
            pass
        return []
    
    def _handle_update(self, update):
        if 'message' not in update:
            return
        
        message = update['message']
        chat_id = str(message['chat']['id'])
        
        if chat_id not in [str(cid) for cid in self.chat_ids]:
            return
        
        text = message.get('text', '')
        if not text.startswith('/') and not text.startswith('状态') and not text.startswith('仓位') and not text.startswith('价格') and not text.startswith('余额') and not text.startswith('帮助') and not text.startswith('信号') and not text.startswith('交易') and not text.startswith('统计'):
            return
        
        text = text.strip()
        response = self._process_command(text)
        if response:
            self.send_message(response, chat_id)
    
    def _process_command(self, text: str) -> str:
        cmd = text.lower()
        
        if cmd.startswith('/start') or cmd == '开始' or cmd == '启动':
            return self._cmd_start()
        elif cmd.startswith('/help') or cmd == '帮助' or cmd == '?':
            return self._cmd_help()
        elif cmd.startswith('/status') or cmd == '状态':
            return self._cmd_status()
        elif cmd.startswith('/balance') or cmd == '余额':
            return self._cmd_balance()
        elif cmd.startswith('/price') or cmd == '价格':
            return self._cmd_price()
        elif cmd.startswith('/position') or cmd == '仓位':
            return self._cmd_position()
        elif cmd.startswith('/signal') or cmd == '信号':
            return self._cmd_signal()
        elif cmd.startswith('/trades') or cmd.startswith('/交易'):
            return self._cmd_trades(text)
        elif cmd.startswith('/stats') or cmd == '统计':
            return self._cmd_stats()
        else:
            return f"未知命令: {text}\n\n发送 /帮助 或 帮助 查看所有命令"
    
    def _cmd_start(self) -> str:
        return """
🚀 *Equilibrium 交易系统*

系统运行中...
发送 /帮助 查看所有命令
"""
    
    def _cmd_help(self) -> str:
        return """
📋 *可用命令*

/帮助 - 显示帮助（简写: 帮助）
/状态 - 系统状态（简写: 状态）
/价格 - 当前价格（简写: 价格）
/余额 - 账户余额（简写: 余额）
/仓位 - 当前持仓（简写: 仓位）
/信号 - 手动分析信号（简写: 信号）
/交易 - 最近交易记录（简写: 交易）
/统计 - 交易统计（简写: 统计）

💡 可以直接发送中文命令，无需加 /
"""
    
    def _cmd_status(self) -> str:
        if not self.trader:
            return "系统未连接到交易引擎"
        
        try:
            trader = self.trader
            price = trader.okx_client.get_current_price()
            position = trader.trade_executor.get_position()
            
            status = f"""
📊 *系统状态*

💰 当前价格: ${price:,.2f}
📈 模式: {'实盘' if not trader.config.DRY_RUN else '模拟盘'}

"""
            if position:
                action_emoji = "🟢" if position['action'] == 'buy' else "🔴"
                status += f"{action_emoji} 有持仓\n"
                status += f"""
方向: {position['action'].upper()}
💵 仓位: ${position['amount']}
📊 均价: ${position['entry_price']:,.2f}
"""
            else:
                status += "🔴 无持仓"
            
            return status
        except Exception as e:
            return f"获取状态失败: {e}"
    
    def _cmd_balance(self) -> str:
        if not self.trader:
            return "系统未连接到交易引擎"
        
        try:
            balance = self.trader.okx_client.get_balance()
            
            if balance:
                return f"""
💰 *账户余额*

可用: ${balance['available']:.2f}
总余额: ${balance['balance']:.2f}
"""
            return "无法获取余额"
        except Exception as e:
            return f"获取余额失败: {e}"
    
    def _cmd_price(self) -> str:
        if not self.trader:
            return "系统未连接到交易引擎"
        
        try:
            price = self.trader.okx_client.get_current_price()
            return f"💵 当前价格: ${price:,.2f}"
        except Exception as e:
            return f"获取价格失败: {e}"
    
    def _cmd_position(self) -> str:
        if not self.trader:
            return "系统未连接到交易引擎"
        
        try:
            position = self.trader.trade_executor.get_position()
            
            if not position:
                return "🔴 当前无持仓"
            
            action_emoji = "🟢" if position['action'] == 'buy' else "🔴"
            return f"""
{action_emoji} *当前持仓*

方向: {position['action'].upper()}
数量: {position['amount']} USDT
均价: ${position['entry_price']:,.2f}
杠杆: {position['leverage']}x
入场时间: {position['entry_time']}
加仓次数: {position.get('add_count', 0)}

止损: ${position.get('stop_loss', 0):,.2f}
止盈1: ${position.get('take_profit_tp1', 0):,.2f}
止盈2: ${position.get('take_profit_tp2', 0):,.2f}
"""
        except Exception as e:
            return f"获取持仓失败: {e}"
    
    def _cmd_signal(self) -> str:
        if not self.trader:
            return "系统未连接到交易引擎"
        
        try:
            trader = self.trader
            signal = trader.run_analysis(force=True)
            
            if not signal or signal.get('action') == 'hold':
                return "📊 当前无交易信号 (hold)"
            
            action = signal['action']
            emoji = "🟢" if action == "buy" else "🔴"
            
            return f"""
{emoji} *交易信号*

操作: {action.upper()}
价格: ${signal.get('price', 0):,.2f}
止损: ${signal.get('stop_loss', 0):,.2f}
止盈1: ${signal.get('take_profit_tp1', 0):,.2f}
止盈2: ${signal.get('take_profit_tp2', 0):,.2f}
原因: {signal.get('reason', '')}
"""
        except Exception as e:
            return f"分析失败: {e}"
    
    def _cmd_trades(self, text: str) -> str:
        if not self.trader:
            return "系统未连接到交易引擎"
        
        try:
            limit = 5
            if ' ' in text:
                try:
                    limit = int(text.split()[1])
                except:
                    pass
            limit = min(limit, 20)
            
            trades = self.trader.data_manager.get_recent_trades(limit)
            
            if not trades:
                return "暂无交易记录"
            
            result = "📜 *最近交易记录*\n\n"
            for t in trades:
                emoji = "✅" if t['pnl'] >= 0 else "❌"
                result += f"{emoji} {t['action']} | ${t['price']:,.0f} | PnL: ${t['pnl']:.2f} | {t['close_time'][:16]}\n"
            
            return result
        except Exception as e:
            return f"获取交易记录失败: {e}"
    
    def _cmd_stats(self) -> str:
        if not self.trader:
            return "系统未连接到交易引擎"
        
        try:
            stats = self.trader.data_manager.get_trade_stats()
            
            return f"""
📈 *交易统计*

总交易次数: {stats['total_trades']}
盈利次数: {stats['win_trades']}
亏损次数: {stats['loss_trades']}
胜率: {stats['win_rate']:.1f}%

总盈亏: ${stats['total_pnl']:.2f}
最大盈利: ${stats['max_win']:.2f}
最大亏损: ${stats['max_loss']:.2f}
"""
        except Exception as e:
            return f"获取统计失败: {e}"


class NotificationManager:
    def __init__(self, config: type = Config):
        self.config = config
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_ids = config.TELEGRAM_CHAT_IDS if hasattr(config, 'TELEGRAM_CHAT_IDS') else [config.TELEGRAM_CHAT_ID]
        self.bot = TelegramBot(config)
    
    def send_message(self, message: str) -> bool:
        return self.bot.send_message(message)
    
    def start_command_handler(self, trader=None):
        self.bot.trader = trader
        self.bot.start_polling(trader)
    
    def stop_command_handler(self):
        self.bot.stop_polling()
    
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
价格: ${price:,.2f}
盈亏: ${pnl:.2f}
状态: {status}
"""
        return self.send_message(message)
    
    def send_daily_report(self, balance: float, trades: int, pnl: float, trades_detail: list = None) -> bool:
        from datetime import datetime
        emoji = "📈" if pnl >= 0 else "📉"
        
        message = f"""
📊 *每日报告* - {datetime.now().strftime('%Y-%m-%d')}

💰 余额: ${balance:,.2f}
{emoji} 今日盈亏: ${pnl:,.2f}
📊 交易次数: {trades}
"""
        if trades_detail:
            wins = sum(1 for t in trades_detail if t.get('pnl', 0) > 0)
            losses = len(trades_detail) - wins
            win_rate = wins / len(trades_detail) * 100 if trades_detail else 0
            message += f"\n胜率: {win_rate:.1f}% ({wins}胜/{losses}负)"
        
        return self.send_message(message)
    
    def send_weekly_report(self, stats: dict) -> bool:
        from datetime import datetime
        pnl = stats.get('total_pnl', 0)
        emoji = "📈" if pnl >= 0 else "📉"
        
        message = f"""
📅 *每周报告* - {datetime.now().strftime('%Y-%m-%d')}

💰 总余额: ${stats.get('balance', 0):,.2f}
{emoji} 本周盈亏: ${pnl:,.2f}
📊 本周交易: {stats.get('trades', 0)}次
🏆 胜率: {stats.get('win_rate', 0):.1f}%
📈 最佳交易: ${stats.get('best_trade', 0):,.2f}
📉 最差交易: ${stats.get('worst_trade', 0):,.2f}

💎 累计提取: ${stats.get('total_withdrawn', 0):,.2f}
"""
        return self.send_message(message)
    
    def send_error(self, error: str) -> bool:
        from datetime import datetime
        message = f"""
⚠️ *系统错误* - {datetime.now().strftime('%H:%M:%S')}

{error}
"""
        return self.send_message(message)
    
    def send_alert(self, title: str, content: str) -> bool:
        from datetime import datetime
        message = f"""
🚨 *{title}* - {datetime.now().strftime('%H:%M:%S')}

{content}
"""
        return self.send_message(message)
