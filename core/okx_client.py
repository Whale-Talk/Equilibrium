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


class OKXClient:
    def __init__(self, config: type = Config):
        self.config = config
        self.base_url = "https://www.okx.com"
        self.api_key = config.OKX_API_KEY
        self.secret_key = config.OKX_SECRET_KEY
        self.passphrase = config.OKX_PASSPHRASE
    
    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = timestamp + method + path + body
        mac = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()
    
    def _request(self, method: str, path: str, params: Dict = None) -> Dict:
        if not self.api_key or not self.secret_key:
            return {"code": "-1", "msg": "API key not configured"}
        
        url = self.base_url + path
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
        query = ""
        body = ""
        if params:
            query = "?" + "&".join([f"{k}={v}" for k, v in params.items()])
            url += query
        
        sign = self._sign(timestamp, method, path + query, body)
        
        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase
        }
        
        proxies = {
            "http": "http://127.0.0.1:7897",
            "https": "http://127.0.0.1:7897"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=15, proxies=proxies)
            else:
                response = requests.post(url, headers=headers, json=params, timeout=15, proxies=proxies)
            if response.status_code != 200:
                return {"code": "-1", "msg": f"HTTP {response.status_code}: {response.text}"}
            return response.json()
        except Exception as e:
            import traceback
            return {"code": "-1", "msg": str(e), "trace": traceback.format_exc()}
    
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
        inst_id = "BTC-USDT-SWAP"
        
        interval_map = {
            "1h": "1H",
            "4h": "4H", 
            "1d": "1D"
        }
        
        bar = interval_map.get(interval, "1h")
        
        url = f"{self.base_url}/market/history-candles"
        params = {
            "instId": inst_id,
            "bar": bar,
            "limit": limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("code") == "0":
                return data.get("data", [])
            else:
                print(f"Error getting klines: {data}")
                return []
        except Exception as e:
            print(f"Exception getting klines: {e}")
            return []

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
            print(f"Exception getting current price: {e}")
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
