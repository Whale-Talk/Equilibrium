"""Logger模块单元测试"""
import pytest
import json
import os
import tempfile
import shutil
from core.logger import Logger, get_logger


def test_logger_singleton():
    """测试Logger单例模式"""
    logger1 = Logger("test")
    logger2 = Logger("test")
    assert logger1 is logger2, "Logger应该是单例"


def test_logger_initialization():
    """测试Logger初始化"""
    # 使用临时目录
    temp_dir = tempfile.mkdtemp()
    try:
        logger = Logger("test", log_dir=temp_dir)
        assert logger.name == "test"
        assert logger.log_dir == temp_dir
        assert os.path.exists(temp_dir)
    finally:
        shutil.rmtree(temp_dir)


def test_logger_log_levels():
    """测试不同日志级别"""
    logger = Logger("test_log_levels", log_dir=tempfile.mkdtemp())

    # 清除已有handlers避免重复日志
    logger.logger.handlers.clear()

    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")


def test_logger_log_trade():
    """测试交易日志方法"""
    logger = Logger("test_trade", log_dir=tempfile.mkdtemp())
    logger.logger.handlers.clear()

    logger.log_trade("open", {
        "action": "buy",
        "price": 50000,
        "amount": 100,
        "leverage": 10
    })


def test_logger_log_api_call():
    """测试API调用日志方法"""
    logger = Logger("test_api", log_dir=tempfile.mkdtemp())
    logger.logger.handlers.clear()

    logger.log_api_call("OKX", "/api/v5/account/balance", None, result={"code": "0"})
    logger.log_api_call("OKX", "/api/v5/market/ticker", {}, error="timeout")


def test_logger_error_with_context():
    """测试带上下文的错误日志"""
    logger = Logger("test_error", log_dir=tempfile.mkdtemp())
    logger.logger.handlers.clear()

    try:
        raise ValueError("test error")
    except Exception as e:
        logger.log_error_with_context(e, context={"user": "test", "action": "buy"})


def test_logger_json_format():
    """测试JSON格式日志"""
    logger = Logger("test_json", log_dir=tempfile.mkdtemp(), log_format="json")
    logger.logger.handlers.clear()

    logger.info("test message", key="value")


def test_get_logger():
    """测试get_logger工厂函数"""
    logger = get_logger("test_factory")
    assert logger.name == "test_factory"
