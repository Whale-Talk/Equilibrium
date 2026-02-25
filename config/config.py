import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DRY_RUN = True

    TRADING_INSTRUMENT = "BTC-USDT-SWAP"
    LEVERAGE = 10
    POSITION_SIZE = 10.0
    INITIAL_BALANCE = 100.0
    
    WITHDRAW_PROFIT = True  # 每月提取收益，保持初始本金
    BASE_BALANCE = 100.0   # 提取后的基础余额

    STOP_LOSS_RATIO = 0.15
    TAKE_PROFIT_RATIO = 0.30
    DAILY_LOSS_LIMIT = 0.30
    MAX_LEVERAGE = 20
    MIN_TRADE_AMOUNT = 5

    DEBATE_ROUNDS = 2

    OKX_API_KEY = os.getenv("OKX_API_KEY", "")
    OKX_SECRET_KEY = os.getenv("OKX_SECRET_KEY", "")
    OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

    KLINE_INTERVALS = ["1h", "4h", "1d"]
    KLINE_LIMIT = 2000
