#!/usr/bin/env python3
"""使用OKX SDK测试资金划转"""

import os
import sys

# 设置环境变量
os.environ["OKX_API_KEY"] = "f72bcbb5-0f9d-4ccf-bda1-ae3cd4fd4dfa"
os.environ["OKX_SECRET_KEY"] = "209E7EE7FA456FB56ABCFEB3A1971C5F"
os.environ["OKX_PASSPHRASE"] = "MJY123marx!"

# 导入SDK
from okx import FundingClient, TradingClient

# 创建API客户端 (添加代理)
funding_api = FundingClient(
    apikey=os.environ["OKX_API_KEY"],
    apisecret=os.environ["OKX_SECRET_KEY"],
    passphrase=os.environ["OKX_PASSPHRASE"],
    simulation=False,
    proxy="http://127.0.0.1:7897"
)

trade_api = TradingClient(
    apikey=os.environ["OKX_API_KEY"],
    apisecret=os.environ["OKX_SECRET_KEY"],
    passphrase=os.environ["OKX_PASSPHRASE"],
    simulation=False,
    proxy="http://127.0.0.1:7897"
)

print("=== 测试1: 获取资金账户余额 ===")
result = funding_api.get_balances(ccy="USDC")
print(result)

print("\n=== 测试2: 获取交易账户余额 ===")
result = funding_api.get_balances(ccy="USDT")
print(result)

print("\n=== 测试3: USDT资金划转 (交易账户 -> 资金账户) ===")
# from_: 18=交易账户(统一账户), to: 6=资金账户
# type: 0=手动
try:
    result = funding_api.funds_transfer(
        ccy="USDT",
        amt="1",
        from_="18",  # 交易账户(统一账户)
        to="6",       # 资金账户
        type="0"      # 0=手动
    )
    print(result)
except Exception as e:
    print(f"错误: {e}")

print("\n=== 测试4: 查看账户配置 ===")
from okx import AccountClient
account_api = AccountClient(
    apikey=os.environ["OKX_API_KEY"],
    apisecret=os.environ["OKX_SECRET_KEY"],
    passphrase=os.environ["OKX_PASSPHRASE"],
    simulation=False,
    proxy="http://127.0.0.1:7897"
)
result = account_api.get_account_config()
print(result)
