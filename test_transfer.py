#!/usr/bin/env python3
"""资金划转测试脚本"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.okx_client import OKXClient


def test_transfer():
    client = OKXClient()
    
    print("=== 测试1: 获取账户余额 ===")
    balance = client.get_balance()
    if balance:
        print(f"USDT 余额: {balance['balance']}")
        print(f"可用余额: {balance['available']}")
    else:
        print("获取余额失败")
        return
    
    print("\n=== 测试2: 资金划转 ===")
    print("请选择操作:")
    print("1. 从资金钱包划转到合约钱包")
    print("2. 从合约钱包划转到资金钱包")
    
    choice = input("请输入选项 (1/2): ").strip()
    
    if choice == "1":
        # 划转到合约
        amount = input("请输入划转金额 (USDT): ").strip()
        try:
            amount = float(amount)
        except:
            print("金额格式错误")
            return
        
        result = client.transfer("USDT", amount, "ccy_to_futures")
        print(f"划转结果: {result}")
        
    elif choice == "2":
        # 从合约划出
        amount = input("请输入划转金额 (USDT): ").strip()
        try:
            amount = float(amount)
        except:
            print("金额格式错误")
            return
        
        result = client.transfer("USDT", amount, "futures_to_ccy")
        print(f"划转结果: {result}")
    
    else:
        print("无效选项")
        return
    
    print("\n=== 测试3: 划转后余额 ===")
    balance = client.get_balance()
    if balance:
        print(f"USDT 余额: {balance['balance']}")
        print(f"可用余额: {balance['available']}")


if __name__ == "__main__":
    test_transfer()
