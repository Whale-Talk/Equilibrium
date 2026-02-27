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

load_dotenv = lambda: None


class OKXClient:
    def __init__(self, config: type = Config):
        self.config = config
        self.base_url = "https://www.okx.com"
        self.api_key = os.getenv("OKX_API_KEY", "") or config.OKX_API_KEY
        self.secret_key = os.getenv("OKX_SECRET_KEY", "") or config.OKX_SECRET_KEY
        self.passphrase = os.getenv("OKX_PASSPHRASE", "") or config.OKX_PASSPHRASE
    
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
        
        proxies = {
            "http": "http://127.0.0.1:7897",
            "https": "http://127.0.0.1:7897"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=15, proxies=proxies)
            else:
                response = requests.post(url, headers=headers, data=body, timeout=15, proxies=proxies)
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
        
        print(f"划转参数: {params}")
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
