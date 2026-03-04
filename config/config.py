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
    TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "5750184219,6830843772").split(",")
    
    # Alpha Vantage
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    
    # K线数据
    KLINE_INTERVALS = ["1h", "4h", "1d"]
    KLINE_LIMIT = 2000

    # ===== 日志配置 =====
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT = os.getenv("LOG_FORMAT", "text")  # text, json
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    LOG_FILE_MAX_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_FILE_BACKUP_COUNT = 30

    # ===== API重试配置 =====
    API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
    API_BACKOFF_FACTOR = float(os.getenv("API_BACKOFF_FACTOR", "2.0"))
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "15"))
    API_MAX_TIMEOUT = int(os.getenv("API_MAX_TIMEOUT", "30"))

    # ===== 健康检查配置 =====
    HEALTH_CHECK_ENABLED = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"
    HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))  # 秒
    HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))
    HEALTH_CHECK_ALERT = os.getenv("HEALTH_CHECK_ALERT", "true").lower() == "true"

    # ===== 熔断器配置 =====
    CIRCUIT_BREAKER_ENABLED = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
    CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"))  # 秒
