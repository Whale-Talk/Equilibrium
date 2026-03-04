"""Logger模块简化单元测试"""
import pytest
import os
import tempfile
import shutil
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import Logger, get_logger
from config import Config


def test_logger_basic_methods():
    """测试Logger基本方法"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        logger = Logger("test_basic", log_dir=temp_dir)
        logger.logger.handlers.clear()

        # 测试不同级别的日志方法不会抛出异常
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")

    finally:
        shutil.rmtree(temp_dir)


def test_logger_trade_log():
    """测试交易日志方法"""
    temp_dir = tempfile.mkdtemp()
    try:
        logger = Logger("test_trade", log_dir=temp_dir)
        logger.logger.handlers.clear()

        # 测试交易日志不抛出异常
        logger.log_trade("open", {
            "action": "buy",
            "price": 50000,
            "amount": 100
        })
        logger.log_trade("close", {
            "action": "sell",
            "price": 51000,
            "pnl": 100
        })

    finally:
        shutil.rmtree(temp_dir)


def test_logger_api_call_log():
    """测试API调用日志方法"""
    temp_dir = tempfile.mkdtemp()
    try:
        logger = Logger("test_api", log_dir=temp_dir)
        logger.logger.handlers.clear()

        # 测试API调用日志不抛出异常
        logger.log_api_call("OKX", "/test/path", {}, result={"code": "0"})
        logger.log_api_call("Telegram", "/sendMessage", {}, error="timeout")

    finally:
        shutil.rmtree(temp_dir)


def test_logger_error_context():
    """测试带上下文的错误日志"""
    temp_dir = tempfile.mkdtemp()
    try:
        logger = Logger("test_error", log_dir=temp_dir)
        logger.logger.handlers.clear()

        # 测试错误日志不抛出异常
        try:
            raise ValueError("test error")
        except Exception as e:
            logger.log_error_with_context(e, context={"test": "value"})

    finally:
        shutil.rmtree(temp_dir)
