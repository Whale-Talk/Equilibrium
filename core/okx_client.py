import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import pandas as pd
import time
import hashlib
import hmac
import base64
from datetime import datetime, timezone
from typing import List, Optional, Dict
from config import Config
from dotenv import load_dotenv
from core.retry import retry_on_network_error, with_circuit_breaker
from core.logger import get_logger

load_dotenv()


class OKXClient:
    def __init__(self, config: type = Config):
        self.config = config
        self.base_url = "https://www.okx.com"
        self.api_key = os.getenv("OKX_API_KEY", "") or config.OKX_API_KEY
        self.secret_key = os.getenv("OKX_SECRET_KEY", "") or config.OKX_SECRET_KEY
        self.passphrase = os.getenv("OKX_PASSPHRASE", "") or config.OKX_PASSPHRASE
        self.logger = get_logger(config=config)

        # 代理设置
        self.proxies = {
            "http": "http://127.0.0.1:7897",
            "https": "http://127.0.0.1:7897"
        }

        # 连接状态
        self.last_successful_request = None
        self.consecutive_failures = 0

        # 熔断器（如果启用）
        self._circuit_breaker_enabled = getattr(config, 'CIRCUIT_BREAKER_ENABLED', True)
    
    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = timestamp + method + path + body
        mac = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()
    
    @retry_on_network_error(
        max_retries=lambda self: self.config.API_MAX_RETRIES,
        backoff_factor=lambda self: self.config.API_BACKOFF_FACTOR,
        backoff_max=lambda self: self.config.API_MAX_TIMEOUT,
        logger=lambda self: self.logger
    )
    def _request(self, method: str, path: str, params: Dict = None) -> Dict:
        if not self.api_key or not self.secret_key:
            error_msg = "API key not configured"
            self.logger.error(error_msg)
            return {"code": "-1", "msg": error_msg}

        url = self.base_url + path
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        query = ""
        body = ""
        if params:
            if method == "GET":
                query = "?" + "&".join([f"{k}={v}" for k, v in params.items()])
                url += query
            else:
                import json
                body = json.dumps(params)

        sign = self._sign(timestamp, method, path + query, body)

        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase
        }

        # 记录API调用
        self.logger.log_api_call("OKX", path, params, result=None)

        try:
            timeout = getattr(self.config, 'API_TIMEOUT', 15)
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=timeout, proxies=self.proxies)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=timeout, proxies=self.proxies)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self.logger.log_api_call("OKX", path, params, error=error_msg)
                return {"code": "-1", "msg": error_msg}

            result = response.json()
            self.logger.log_api_call("OKX", path, params, result={"code": result.get("code")})

            # 更新连接状态
            self._on_request_success()
            return result

        except Exception as e:
            self._on_request_failure()
            self.logger.log_error_with_context(
                e,
                context={'method': method, 'path': path, 'params': params}
            )
            import traceback
            return {"code": "-1", "msg": str(e), "trace": traceback.format_exc()}

    def _on_request_success(self):
        """请求成功时的处理"""
        self.last_successful_request = datetime.now()
        self.consecutive_failures = 0

    def _on_request_failure(self):
        """请求失败时的处理"""
        self.consecutive_failures += 1

    def get_connection_status(self) -> Dict:
        """获取连接状态"""
        return {
            'last_success': self.last_successful_request.isoformat() if self.last_successful_request else None,
            'consecutive_failures': self.consecutive_failures,
            'is_connected': self.consecutive_failures < 3
        }
    
    def get_balance(self) -> Optional[Dict]:
        """获取账户余额"""
        data = self._request("GET", "/api/v5/account/balance")
        if data.get("code") == "0":
            for bal in data.get("data", [{}])[0].get("details", []):
                if bal.get("ccy") == "USDT":
                    return {
                        "available": float(bal.get("availBal", 0)),
                        "balance": float(bal.get("cashBal", 0))
                    }
        return None
    
    def transfer(self, currency: str, amount: float, side: str) -> Dict:
        """资金划转 (统一账户模式)
        side: 
            - ccy_to_futures: 资金账户 -> 交易账户
            - futures_to_ccy: 交易账户 -> 资金账户
        """
        type_map = {
            "ccy_to_futures": "0",  # 资金账户 -> 交易账户
            "futures_to_ccy": "0"    # 交易账户 -> 资金账户
        }
        
        trans_type = type_map.get(side, "0")
        
        # 统一账户模式: from=18(交易账户), to=6(资金账户)
        # 旧版API: from=18(币币), to=19(合约)
        if side == "ccy_to_futures":
            # 资金账户 -> 交易账户
            params = {
                "ccy": currency,
                "amt": str(amount),
                "type": trans_type,
                "from": "6",  # 资金账户
                "to": "18"    # 交易账户(统一账户)
            }
        else:
            # 交易账户 -> 资金账户
            params = {
                "ccy": currency,
                "amt": str(amount),
                "type": trans_type,
                "from": "18",  # 交易账户(统一账户)
                "to": "6"      # 资金账户
            }
        
        self.logger.info(f"资金划转", side=side, currency=currency, amount=amount, params=params)
        data = self._request("POST", "/api/v5/asset/transfer", params)
        return data
    
    def get_position(self) -> Optional[Dict]:
        """获取当前持仓"""
        params = {"instId": "BTC-USDT-SWAP", "mgnMode": "isolated"}
        data = self._request("GET", "/api/v5/account/positions", params)
        if data.get("code") == "0" and data.get("data"):
            pos = data["data"][0]
            return {
                "side": pos.get("posSide", ""),
                "size": float(pos.get("pos", 0)),
                "avgPrice": float(pos.get("avgPx", 0)),
                "unrealizedPnl": float(pos.get("upl", 0))
            }
        return None
    
    def get_klines(self, interval: str, limit: int = 100) -> List[List]:
        """获取K线数据，自动分页获取完整历史数据
        
        Args:
            interval: K线周期 (1h, 4h, 1d)
            limit: 需要获取的总数量
            
        Returns:
            K线数据列表
        """
        all_klines = []
        after = None
        fetch_count = 0
        max_fetches = 100  # 最多请求次数，防止无限循环
        
        while len(all_klines) < limit and fetch_count < max_fetches:
            fetch_count += 1
            klines = self._get_klines_impl(interval, 300, after)
            
            if not klines:
                break
            
            all_klines.extend(klines)
            self.logger.info(f"获取K线数据", fetch_count=fetch_count, count=len(klines), total=len(all_klines))
            
            # OKX返回倒序，最新在前，最后一条是最早的
            # 用最后一条的时间戳作为after，获取更早的数据
            if len(klines) >= 300:
                after = klines[-1][0]
            else:
                break
            
            time.sleep(0.3)  # 避免请求过快
        
        return all_klines[:limit]
    
    def get_klines_since(self, interval: str, since_timestamp: int) -> List[List]:
        """获取指定时间戳之后的K线数据（增量获取）"""
        all_klines = []
        after = None
        fetch_count = 0
        max_fetches = 10
        
        while fetch_count < max_fetches:
            fetch_count += 1
            klines = self._get_klines_impl(interval, 300, after)
            
            if not klines:
                break
            
            # 过滤掉比本地更早的数据
            new_klines = [k for k in klines if int(k[0]) > since_timestamp]
            
            if new_klines:
                all_klines.extend(new_klines)
            
            # OKX返回倒序，最新在前，最后一条是最早的
            if len(klines) >= 300:
                after = klines[-1][0]
            else:
                break
            
            # 如果没有新数据了，就停止
            if not new_klines or int(klines[-1][0]) <= since_timestamp:
                break
            
            time.sleep(0.3)
        
        return all_klines
    
    def _get_klines_impl(self, interval: str, limit: int = 100, after: str = None) -> List[List]:
        inst_id = "BTC-USDT-SWAP"
        
        interval_map = {
            "1h": "1H",
            "4h": "4H", 
            "1d": "1D"
        }
        
        bar = interval_map.get(interval, "1h")
        
        url = f"{self.base_url}/api/v5/market/history-candles"
        params = {
            "instId": inst_id,
            "bar": bar,
            "limit": limit
        }
        
        if after:
            params["after"] = after
        
        proxies = {
            "http": "http://127.0.0.1:7897",
            "https": "http://127.0.0.1:7897"
        }
        
        try:
            response = requests.get(url, params=params, timeout=15, proxies=proxies)
            data = response.json()
            
            if data.get("code") == "0":
                return data.get("data", [])
            else:
                self.logger.log_api_call("OKX", "/api/v5/market/history-candles", params, error=data)
                return []
        except Exception as e:
            self.logger.log_error_with_context(e, context={'task': 'get_klines_impl'})
            return []
            return []
    
    def get_klines_full(self, interval: str, limit: int = 2000) -> List[List]:
        """使用ccxt循环获取完整历史K线数据"""
        try:
            import ccxt
        except ImportError:
            self.logger.error("ccxt未安装，请运行: pip install ccxt")
            return self.get_klines(interval, limit)
        
        exchange = ccxt.okx({
            'enableRateLimit': True,
        })
        
        exchange.session.proxies = {
            'http': 'http://127.0.0.1:7897',
            'https': 'http://127.0.0.1:7897'
        }
        
        interval_map = {
            "1h": "1h",
            "4h": "4h", 
            "1d": "1d"
        }
        timeframe = interval_map.get(interval, "1h")
        
        klines = []
        fetch_since = None
        request_count = 0
        
        while request_count < 10:  # 最多10次
            request_count += 1
            fetched = exchange.fetch_ohlcv(
                symbol='BTC/USDT',
                timeframe=timeframe,
                since=fetch_since,
                limit=300
            )
            
            if not fetched:
                break
            
            klines.extend(fetched)
            self.logger.info(f"获取K线(ccxt)", request_count=request_count, count=len(fetched), total=len(klines))
            
            if len(klines) >= limit:
                break
            
            fetch_since = fetched[-1][0] + 1
            time.sleep(0.5)
        
        return klines[:limit]

    def get_current_price(self) -> Optional[float]:
        inst_id = "BTC-USDT-SWAP"
        
        url = f"{self.base_url}/api/v5/market/ticker"
        params = {"instId": inst_id}
        
        proxies = {
            "http": "http://127.0.0.1:7897",
            "https": "http://127.0.0.1:7897"
        }
        
        try:
            response = requests.get(url, params=params, timeout=15, proxies=proxies)
            data = response.json()
            
            if data.get("code") == "0":
                tickers = data.get("data", [])
                if tickers:
                    return float(tickers[0].get("last", 0))
            return None
        except Exception as e:
            self.logger.log_error_with_context(e, context={'task': 'get_current_price'})
            return None
            return None

    def format_klines(self, klines: List[List]) -> pd.DataFrame:
        if not klines:
            return pd.DataFrame()
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'
        ])
        
        df['timestamp'] = df['timestamp'].astype(int)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]


if __name__ == "__main__":
    client = OKXClient()
    klines = client.get_klines("1h", 10)
    print(client.format_klines(klines))
