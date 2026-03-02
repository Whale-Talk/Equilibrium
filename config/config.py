import os

class Config:
    # 交易设置
    DRY_RUN = False  # 实盘模式
    TRADING_INSTRUMENT = "BTC-USDT-SWAP"
    LEVERAGE = 10
    POSITION_SIZE = 10.0
    INITIAL_BALANCE = 100.0
    
    # 资金管理
    WITHDRAW_PROFIT = True
    BASE_BALANCE = 100.0
    
    # 风险控制
    STOP_LOSS_RATIO = 0.15
    TAKE_PROFIT_RATIO = 0.30
    DAILY_LOSS_LIMIT = 0.30
    MAX_LEVERAGE = 20
    MIN_TRADE_AMOUNT = 5
    
    # AI对话
    DEBATE_ROUNDS = 2
    
    # ===== API密钥 - 请在 .env 文件中设置 =====
    # OKX API (现货/合约)
    OKX_API_KEY = os.getenv("OKX_API_KEY", "")
    OKX_SECRET_KEY = os.getenv("OKX_SECRET_KEY", "")
    OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")
    
    # DeepSeek API
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    # Telegram 通知
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Alpha Vantage
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    
    # K线数据
    KLINE_INTERVALS = ["1h", "4h", "1d"]
    KLINE_LIMIT = 2000
