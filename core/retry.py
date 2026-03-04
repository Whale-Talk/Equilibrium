import time
import functools
from typing import Callable, Type, Tuple, Optional, Any
from core.logger import get_logger


def retry_on_exception(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    backoff_max: float = 60.0,
    logger=None
) -> Callable:
    """重试装饰器 - 使用指数退避策略

    当函数抛出指定异常时，自动重试，每次重试间隔时间递增。

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子，每次重试间隔 = backoff_factor * (2 ^ retry_count)
        exceptions: 需要重试的异常类型
        backoff_max: 最大退避时间（秒）
        logger: Logger实例，如果为None则获取默认logger

    Returns:
        装饰器函数

    Example:
        @retry_on_exception(max_retries=3, backoff_factor=2.0)
        def api_call():
            # 可能失败的API调用
            pass
    """
    def decorator(func: Callable) -> Callable:
        _logger = logger or get_logger()

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    # 记录重试尝试
                    if attempt > 0:
                        _logger.warning(
                            f"重试 {func.__name__} (第{attempt}次)",
                            function=func.__name__,
                            attempt=attempt,
                            max_retries=max_retries
                        )
                    else:
                        _logger.debug(f"调用函数: {func.__name__}", function=func.__name__)

                    # 执行函数
                    result = func(*args, **kwargs)

                    # 成功后返回结果
                    if attempt > 0:
                        _logger.info(
                            f"重试成功: {func.__name__}",
                            function=func.__name__,
                            total_attempts=attempt + 1
                        )

                    return result

                except exceptions as e:
                    last_exception = e

                    # 如果是最后一次尝试，抛出异常
                    if attempt >= max_retries:
                        _logger.error(
                            f"重试失败: {func.__name__} 已达到最大重试次数",
                            function=func.__name__,
                            max_retries=max_retries,
                            total_attempts=max_retries + 1,
                            error=str(e)
                        )
                        _logger.log_error_with_context(
                            e,
                            context={
                                'function': func.__name__,
                                'total_attempts': max_retries + 1
                            }
                        )
                        raise

                    # 计算退避时间（指数退避）
                    sleep_time = min(
                        backoff_factor * (2 ** attempt),
                        backoff_max
                    )

                    _logger.warning(
                        f"函数执行失败，{sleep_time:.2f}秒后重试: {func.__name__}",
                        function=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                        attempt=attempt + 1,
                        next_retry_in_sec=round(sleep_time, 2)
                    )

                    # 等待后重试
                    time.sleep(sleep_time)

        return wrapper

    return decorator


def retry_on_network_error(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    backoff_max: float = 30.0,
    logger=None
) -> Callable:
    """专门针对网络错误的重试装饰器

    重试常见的网络相关异常，如连接超时、连接拒绝等。

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子
        backoff_max: 最大退避时间（秒）
        logger: Logger实例

    Returns:
        装饰器函数
    """
    import requests
    from requests.exceptions import (
        ConnectionError,
        Timeout,
        RequestException
    )
    import socket

    network_exceptions = (
        ConnectionError,
        Timeout,
        RequestException,
        socket.timeout,
        socket.gaierror,
        socket.error
    )

    return retry_on_exception(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        exceptions=network_exceptions,
        backoff_max=backoff_max,
        logger=logger
    )


class CircuitBreaker:
    """熔断器 - 防止频繁调用失败的服务

    当服务连续失败超过阈值时，熔断器打开，直接拒绝请求，
    避免雪崩效应。一段时间后尝试恢复。

    Args:
        failure_threshold: 失败阈值，连续失败多少次后打开熔断器
        timeout: 熔断器打开后的超时时间（秒）
        expected_exception: 预期的异常类型
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
        self.logger = get_logger()

    def call(self, func: Callable, *args, **kwargs):
        """通过熔断器调用函数

        Args:
            func: 要调用的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器打开时抛出
        """
        if self.state == 'open':
            if self._should_attempt_reset():
                self.state = 'half-open'
                self.logger.info(
                    "熔断器尝试恢复",
                    state='half-open'
                )
            else:
                self.logger.warning(
                    "熔断器已打开，拒绝请求",
                    failure_count=self.failure_count,
                    time_since_failure=time.time() - self.last_failure_time
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open. Failures: {self.failure_count}"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """成功时重置状态"""
        self.failure_count = 0
        if self.state == 'half-open':
            self.state = 'closed'
            self.logger.info("熔断器已恢复", state='closed')

    def _on_failure(self):
        """失败时增加计数并可能打开熔断器"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            self.logger.error(
                "熔断器已打开",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )

    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试恢复"""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.timeout


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass


def with_circuit_breaker(
    failure_threshold: int = 5,
    timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception,
    logger=None
) -> Callable:
    """熔断器装饰器

    Args:
        failure_threshold: 失败阈值
        timeout: 超时时间（秒）
        expected_exception: 预期的异常类型
        logger: Logger实例

    Returns:
        装饰器函数
    """
    circuit_breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        timeout=timeout,
        expected_exception=expected_exception
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return circuit_breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
