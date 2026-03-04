import threading
import time
from datetime import datetime
from typing import Optional, Callable, Dict
from core.logger import get_logger


class HealthChecker:
    """健康检查器 - 定期检查系统各组件的健康状态

    检查项：
    1. API 连通性（OKX, Telegram）
    2. 数据库连接
    3. 可自定义检查项

    发现问题时触发告警通知。
    """

    def __init__(self, config=None, notification=None, okx_client=None, data_manager=None):
        self.config = config
        self.notification = notification
        self.okx_client = okx_client
        self.data_manager = data_manager

        self.logger = get_logger(config=config)

        # 从配置获取设置
        if config:
            self.check_interval = getattr(config, 'HEALTH_CHECK_INTERVAL', 60)
            self.check_timeout = getattr(config, 'HEALTH_CHECK_TIMEOUT', 10)
            self.enable_alert = getattr(config, 'HEALTH_CHECK_ALERT', True)
        else:
            self.check_interval = 60
            self.check_timeout = 10
            self.enable_alert = True

        # 运行状态
        self.running = False
        self.thread = None

        # 自定义检查项
        self.custom_checks = []

        # 健康状态
        self.status = {
            'last_check': None,
            'okx': {'status': 'unknown', 'last_error': None, 'consecutive_failures': 0},
            'telegram': {'status': 'unknown', 'last_error': None, 'consecutive_failures': 0},
            'database': {'status': 'unknown', 'last_error': None, 'consecutive_failures': 0}
        }

        # 告警阈值（连续失败次数）
        self.alert_threshold = {
            'okx': 3,
            'telegram': 5,
            'database': 3
        }

        # 告警冷却时间（秒）
        self.alert_cooldown = {}
        self.alert_cooldown_time = 300  # 5分钟

    def start(self):
        """启动健康检查线程"""
        if self.running:
            self.logger.warning("健康检查器已在运行")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.logger.info("健康检查器已启动", interval=self.check_interval)

    def stop(self):
        """停止健康检查线程"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("健康检查器已停止")

    def _run_loop(self):
        """健康检查主循环"""
        while self.running:
            try:
                self.check_all()
            except Exception as e:
                self.logger.log_error_with_context(e, context={'task': 'health_check_loop'})

            time.sleep(self.check_interval)

    def check_all(self) -> Dict:
        """执行所有健康检查

        Returns:
            完整的健康状态字典
        """
        self.status['last_check'] = datetime.now().isoformat()

        # 执行各项检查
        self._check_okx()
        self._check_telegram()
        self._check_database()

        # 执行自定义检查
        for check_func in self.custom_checks:
            try:
                check_func()
            except Exception as e:
                self.logger.log_error_with_context(e, context={'custom_check': check_func.__name__})

        return self.status

    def _check_okx(self):
        """检查 OKX API 连通性"""
        if not self.okx_client:
            self.status['okx']['status'] = 'skipped'
            return

        try:
            # 尝试获取当前价格
            price = self.okx_client.get_current_price()

            if price is not None and price > 0:
                self._update_status('okx', 'healthy', None)
                self.logger.debug("OKX API 健康检查通过", price=price)
            else:
                raise Exception("Invalid price response")

        except Exception as e:
            self._update_status('okx', 'unhealthy', str(e))

    def _check_telegram(self):
        """检查 Telegram Bot 连通性"""
        if not self.notification:
            self.status['telegram']['status'] = 'skipped'
            return

        try:
            # 尝试发送测试消息（只在首次或失败时发送）
            if self.status['telegram']['status'] != 'healthy':
                self.notification.send_message("🔍 健康检查测试")
            self._update_status('telegram', 'healthy', None)
            self.logger.debug("Telegram API 健康检查通过")

        except Exception as e:
            self._update_status('telegram', 'unhealthy', str(e))

    def _check_database(self):
        """检查数据库连接"""
        if not self.data_manager:
            self.status['database']['status'] = 'skipped'
            return

        try:
            # 尝试执行简单查询
            self.data_manager.get_balance_history()
            self._update_status('database', 'healthy', None)
            self.logger.debug("数据库连接检查通过")

        except Exception as e:
            self._update_status('database', 'unhealthy', str(e))

    def _update_status(self, component: str, status: str, error: Optional[str]):
        """更新组件状态并处理告警

        Args:
            component: 组件名称 (okx, telegram, database)
            status: 状态 (healthy, unhealthy, skipped, unknown)
            error: 错误信息（如果有）
        """
        prev_status = self.status[component]['status']
        self.status[component]['status'] = status

        if status == 'healthy':
            # 恢复健康
            if prev_status == 'unhealthy':
                self.logger.info(
                    f"{component.upper()} 已恢复健康",
                    component=component,
                    previous_status=prev_status
                )
                self._send_alert(f"✅ {component.upper()} 恢复正常")
            self.status[component]['consecutive_failures'] = 0
            self.status[component]['last_error'] = None

        elif status == 'unhealthy':
            # 健康检查失败
            self.status[component]['last_error'] = error
            self.status[component]['consecutive_failures'] += 1

            failures = self.status[component]['consecutive_failures']
            threshold = self.alert_threshold.get(component, 3)

            self.logger.warning(
                f"{component.upper()} 健康检查失败",
                component=component,
                error=error,
                consecutive_failures=failures,
                threshold=threshold
            )

            # 达到阈值时发送告警
            if failures >= threshold:
                self._send_alert_if_cooldown(
                    component,
                    f"⚠️ {component.upper()} 连续失败 {failures} 次\n错误: {error}"
                )

    def _send_alert_if_cooldown(self, component: str, message: str):
        """在冷却期后发送告警

        Args:
            component: 组件名称
            message: 告警消息
        """
        now = time.time()
        last_alert = self.alert_cooldown.get(component, 0)

        if now - last_alert >= self.alert_cooldown_time:
            self._send_alert(message)
            self.alert_cooldown[component] = now
        else:
            self.logger.debug(
                f"{component} 告警冷却中",
                component=component,
                seconds_until_next=int(self.alert_cooldown_time - (now - last_alert))
            )

    def _send_alert(self, message: str):
        """发送告警通知

        Args:
            message: 告警消息
        """
        if not self.enable_alert or not self.notification:
            return

        try:
            alert_msg = f"""
🚨 *系统健康告警* - {datetime.now().strftime('%H:%M:%S')}

{message}
"""
            self.notification.send_alert("健康检查", message)
            self.logger.warning("健康检查告警已发送", message=message[:100])

        except Exception as e:
            self.logger.log_error_with_context(e, context={'alert_message': message})

    def add_custom_check(self, check_func: Callable):
        """添加自定义健康检查函数

        Args:
            check_func: 检查函数，应抛出异常表示失败
        """
        self.custom_checks.append(check_func)
        self.logger.info("添加自定义健康检查", function=check_func.__name__)

    def get_status(self) -> Dict:
        """获取当前健康状态

        Returns:
            健康状态字典
        """
        return self.status.copy()

    def is_healthy(self) -> bool:
        """检查所有组件是否都健康

        Returns:
            True 如果所有组件都健康或跳过
        """
        for component, data in self.status.items():
            if component == 'last_check':
                continue
            status = data.get('status')
            if status == 'unhealthy':
                return False
        return True

    def force_check(self, component: str = None):
        """强制执行健康检查

        Args:
            component: 指定组件，None表示检查所有
        """
        if component:
            check_func = getattr(self, f'_check_{component}', None)
            if check_func:
                check_func()
        else:
            self.check_all()


class HealthCheckError(Exception):
    """健康检查异常"""
    pass
