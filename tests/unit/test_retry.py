"""重试机制单元测试"""
import pytest
import time
from core.retry import (
    retry_on_exception,
    retry_on_network_error,
    CircuitBreaker,
    CircuitBreakerOpenError
)
from core.logger import get_logger


def test_retry_decorator_success():
    """测试正常情况不重试"""
    call_count = 0

    @retry_on_exception(max_retries=3)
    def test_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = test_func()
    assert result == "success"
    assert call_count == 1, "成功情况不应该重试"


def test_retry_decorator_failure():
    """测试失败时重试"""
    call_count = 0

    @retry_on_exception(max_retries=2)
    def test_func():
        nonlocal call_count
        call_count += 1
        raise ValueError("failed")

    with pytest.raises(ValueError):
        test_func()

    assert call_count == 3, "应该调用1次+2次重试"


def test_retry_backoff():
    """测试指数退避时间"""
    call_times = []

    @retry_on_exception(max_retries=2, backoff_factor=0.1)  # 快速测试
    def test_func():
        call_times.append(time.time())
        raise Exception("test")

    with pytest.raises(Exception):
        test_func()

    # 检查退避时间是否递增
    if len(call_times) >= 2:
        backoff_1 = call_times[1] - call_times[0]
        backoff_2 = call_times[2] - call_times[1]
        assert backoff_2 >= backoff_1, "退避时间应该递增"


def test_retry_specific_exception():
    """测试只重试指定异常"""
    call_count = 0

    @retry_on_exception(max_retries=2, exceptions=(ValueError,))
    def test_func():
        nonlocal call_count
        call_count += 1
        raise TypeError("type error")

    # TypeError不应该重试
    with pytest.raises(TypeError):
        test_func()

    assert call_count == 1


def test_circuit_breaker_open():
    """测试熔断器打开"""
    cb = CircuitBreaker(failure_threshold=3, timeout=1.0)

    call_count = 0

    def failing_func():
        nonlocal call_count
        call_count += 1
        raise Exception("always fail")

    # 连续失败3次
    for _ in range(3):
        try:
            cb.call(failing_func)
        except Exception:
            pass

    assert cb.state == 'open'
    assert cb.failure_count == 3

    # 第4次应该被熔断器拒绝
    with pytest.raises(CircuitBreakerOpenError):
        cb.call(failing_func)

    assert call_count == 3, "熔断器打开后应该拒绝请求"


def test_circuit_breaker_half_open():
    """测试熔断器半开状态"""
    cb = CircuitBreaker(failure_threshold=2, timeout=0.1)

    # 触发熔断器
    for _ in range(2):
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception()))
        except Exception:
            pass

    assert cb.state == 'open'

    # 等待超时（需要足够时间）
    time.sleep(0.2)

    # 尝试恢复 - 第一次调用应该保持open或转为half-open
    cb.call(lambda: None)

    # 成功调用后应该重置状态
    result = cb.call(lambda: "success")
    assert cb.state == 'closed'
    assert result == "success"


def test_circuit_breaker_close_after_success():
    """测试熔断器成功后关闭"""
    cb = CircuitBreaker(failure_threshold=3, timeout=1.0)

    # 触发熔断
    for _ in range(3):
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception()))
        except Exception:
            pass

    assert cb.state == 'open'

    # 等待超时
    time.sleep(1.1)

    # 成功后应该关闭
    result = cb.call(lambda: "success")
    assert cb.state == 'closed'
    assert cb.failure_count == 0
