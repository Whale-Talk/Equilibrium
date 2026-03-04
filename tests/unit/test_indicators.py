"""技术指标单元测试"""
import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.indicators import calculate_all_indicators


def create_test_dataframe():
    """创建测试用K线数据"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='h')
    np.random.seed(42)

    # 生成模拟价格数据（有趋势）
    base_price = 50000
    trend = np.linspace(0, 1000, 100)
    noise = np.random.normal(0, 200, 100)
    closes = base_price + trend + noise

    highs = closes * 1.01
    lows = closes * 0.99
    opens = closes * (1 + np.random.uniform(-0.005, 0.005, 100))
    volumes = np.random.uniform(100, 1000, 100)

    df = pd.DataFrame({
        'timestamp': dates.astype(np.int64) // 10**9,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })
    return df


def test_calculate_ma():
    """测试移动平均线计算"""
    df = create_test_dataframe()
    result = calculate_all_indicators(df)

    assert 'ma5' in result.columns
    assert 'ma10' in result.columns
    assert 'ma20' in result.columns
    assert 'ma60' in result.columns

    # MA应该平滑价格
    assert result['ma20'].iloc[-1] > result['ma20'].iloc[-20]


def test_calculate_rsi():
    """测试RSI计算"""
    df = create_test_dataframe()
    result = calculate_all_indicators(df)

    assert 'rsi' in result.columns

    # RSI应该在0-100之间
    rsi_values = result['rsi'].dropna()
    assert rsi_values.min() >= 0
    assert rsi_values.max() <= 100


def test_calculate_macd():
    """测试MACD计算"""
    df = create_test_dataframe()
    result = calculate_all_indicators(df)

    assert 'macd' in result.columns
    assert 'macd_signal' in result.columns
    assert 'macd_hist' in result.columns


def test_calculate_bollinger():
    """测试布林带计算"""
    df = create_test_dataframe()
    result = calculate_all_indicators(df)

    assert 'bb_upper' in result.columns
    assert 'bb_middle' in result.columns
    assert 'bb_lower' in result.columns

    # 上轨应该 > 中轨 > 下轨
    latest = result.iloc[-1]
    assert latest['bb_upper'] > latest['bb_middle']
    assert latest['bb_middle'] > latest['bb_lower']


def test_calculate_atr():
    """测试ATR计算"""
    df = create_test_dataframe()
    result = calculate_all_indicators(df)

    assert 'atr' in result.columns

    # ATR应该是正数
    atr_values = result['atr'].dropna()
    assert (atr_values > 0).all()


def test_calculate_adx():
    """测试ADX计算"""
    df = create_test_dataframe()
    result = calculate_all_indicators(df)

    assert 'adx' in result.columns

    # ADX应该在0-100之间
    adx_values = result['adx'].dropna()
    assert adx_values.min() >= 0
    assert adx_values.max() <= 100


def test_indicators_with_insufficient_data():
    """测试数据不足时的处理"""
    # 只提供10条数据
    df = create_test_dataframe().head(10)
    result = calculate_all_indicators(df)

    # 数据不足时某些指标可能为NaN
    # 但不应该抛出异常
    assert len(result) > 0


def test_indicators_empty_dataframe():
    """测试空DataFrame的处理"""
    df = pd.DataFrame()
    result = calculate_all_indicators(df)

    # 空数据应该返回空DataFrame或处理得当
    # 不应该崩溃
    assert result is not None
