import logging
import os
import json
import time
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from functools import wraps
from typing import Optional, Dict, Any


class Logger:
    _instance = None

    def __new__(cls, name="Equilibrium", log_dir="logs", config=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, name="Equilibrium", log_dir="logs", config=None):
        if self._initialized:
            return

        self._initialized = True
        self.name = name
        self.log_dir = log_dir
        self.config = config

        # 从配置获取日志设置
        if config:
            self.log_level = getattr(config, 'LOG_LEVEL', 'INFO')
            self.log_format = getattr(config, 'LOG_FORMAT', 'text')
            self.log_file_max_size = getattr(config, 'LOG_FILE_MAX_SIZE', 10 * 1024 * 1024)
            self.log_file_backup_count = getattr(config, 'LOG_FILE_BACKUP_COUNT', 30)
        else:
            self.log_level = 'INFO'
            self.log_format = 'text'
            self.log_file_max_size = 10 * 1024 * 1024
            self.log_file_backup_count = 30

        os.makedirs(log_dir, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(self._get_log_level())

        if self.logger.handlers:
            return

        # 主日志文件
        log_file = os.path.join(log_dir, f"equilibrium_{datetime.now().strftime('%Y%m%d')}.log")

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.log_file_max_size,
            backupCount=self.log_file_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self._get_log_level())

        # 错误日志单独文件
        error_log_file = os.path.join(log_dir, f"equilibrium_error_{datetime.now().strftime('%Y%m%d')}.log")
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=self.log_file_max_size,
            backupCount=self.log_file_backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)

        # 控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 格式化器
        if self.log_format == 'json':
            file_handler.setFormatter(JsonFormatter())
            error_handler.setFormatter(JsonFormatter())
            console_handler.setFormatter(logging.Formatter('%(message)s'))
        else:
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            error_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(console_handler)

    def _get_log_level(self):
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return level_map.get(self.log_level.upper(), logging.INFO)

    def debug(self, msg, **kwargs):
        self.logger.debug(self._format_msg(msg, **kwargs))

    def info(self, msg, **kwargs):
        self.logger.info(self._format_msg(msg, **kwargs))

    def warning(self, msg, **kwargs):
        self.logger.warning(self._format_msg(msg, **kwargs))

    def error(self, msg, **kwargs):
        self.logger.error(self._format_msg(msg, **kwargs))

    def critical(self, msg, **kwargs):
        self.logger.critical(self._format_msg(msg, **kwargs))

    def _format_msg(self, msg, **kwargs):
        if self.log_format == 'json' or kwargs:
            data = {'message': str(msg)}
            data.update(kwargs)
            return json.dumps(data, ensure_ascii=False)
        elif kwargs:
            return f"{msg} | {', '.join(f'{k}={v}' for k, v in kwargs.items())}"
        return str(msg)

    def log_trade(self, event_type: str, data: Dict) -> None:
        """记录交易相关操作

        Args:
            event_type: 事件类型 (open, close, add, tp1, tp2, stop_loss, timeout)
            data: 交易数据字典
        """
        emoji_map = {
            'open': '🟢' if data.get('action') == 'buy' else '🔴',
            'close': '⭕',
            'add': '➕',
            'tp1': '✅',
            'tp2': '🎯',
            'stop_loss': '🛑',
            'timeout': '⏰'
        }

        self.info(
            f"交易: {event_type}",
            event=event_type,
            emoji=emoji_map.get(event_type, '📊'),
            **data
        )

    def log_api_call(self, api: str, endpoint: str, params: Dict = None, result: Dict = None, error: str = None) -> None:
        """记录API调用

        Args:
            api: API名称 (OKX, Telegram)
            endpoint: 接口路径
            params: 请求参数
            result: 响应结果
            error: 错误信息（如果有）
        """
        log_data = {
            'api': api,
            'endpoint': endpoint
        }
        if params:
            log_data['params'] = self._sanitize_params(params)
        if result:
            log_data['result'] = result
        if error:
            log_data['error'] = error

        if error:
            self.warning(f"API调用失败: {api} {endpoint}", **log_data)
        else:
            self.debug(f"API调用成功: {api} {endpoint}", **log_data)

    def _sanitize_params(self, params: Dict) -> Dict:
        """清理敏感参数（如密钥）"""
        if not params:
            return {}
        sensitive_keys = ['apiKey', 'secretKey', 'passphrase', 'password', 'token']
        return {
            k: '***REDACTED***' if any(sk in k.lower() for sk in sensitive_keys) else v
            for k, v in params.items()
        }

    def log_error_with_context(self, error: Exception, context: Dict = None) -> None:
        """记录带上下文的错误

        Args:
            error: 异常对象
            context: 上下文信息字典
        """
        log_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc()
        }
        if context:
            log_data['context'] = context

        self.error(f"异常: {type(error).__name__}: {str(error)}", **log_data)


def get_logger(name="Equilibrium", config=None):
    return Logger(name, config=config)


class JsonFormatter(logging.Formatter):
    """JSON格式日志格式化器"""

    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage()
        }

        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }

        # 尝试解析JSON格式的消息
        try:
            msg_data = json.loads(record.getMessage())
            log_data.update(msg_data)
        except (json.JSONDecodeError, TypeError):
            pass

        return json.dumps(log_data, ensure_ascii=False)


def log_execution(logger=None, level='INFO'):
    """函数执行日志装饰器

    自动记录函数执行时间、参数、返回值和异常

    Args:
        logger: Logger实例，如果为None则获取默认logger
        level: 日志级别 (DEBUG, INFO)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logger or get_logger()
            func_name = func.__name__

            start_time = time.time()

            # 记录函数调用
            _logger.debug(
                f"调用函数: {func_name}",
                function=func_name,
                args=args,
                kwargs=kwargs
            )

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time

                # 记录函数返回
                _logger.debug(
                    f"函数完成: {func_name}",
                    function=func_name,
                    elapsed_ms=round(elapsed * 1000, 2),
                    result_type=type(result).__name__
                )

                return result

            except Exception as e:
                elapsed = time.time() - start_time

                # 记录异常
                _logger.log_error_with_context(
                    e,
                    context={
                        'function': func_name,
                        'elapsed_ms': round(elapsed * 1000, 2),
                        'args': args,
                        'kwargs': kwargs
                    }
                )
                raise

        return wrapper
    return decorator
