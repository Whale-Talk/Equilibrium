"""Trader交易逻辑单元测试"""
import pytest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trader import Trader
from core.executor import BacktestExecutor
from config import Config


def create_test_df_with_indicators():
    """创建带指标的测试数据"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
    np.random.seed(42)

    base_price = 50000
    trend = np.linspace(0, 2000, 100)  # 上涨趋势
    closes = base_price + trend + np.random.normal(0, 300, 100)

    df = pd.DataFrame({
        'timestamp': dates.astype(np.int64) // 10**9,
        'open': closes * (1 + np.random.uniform(-0.005, 0.005, 100)),
        'high': closes * 1.02,
        'low': closes * 0.98,
        'close': closes,
        'volume': np.random.uniform(100, 1000, 100)
    })

    # 添加指标
    from utils.indicators import calculate_all_indicators
    return calculate_all_indicators(df)


def test_trader_initialization():
    """测试Trader初始化"""
    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    assert trader.config is not None
    assert trader.executor is not None
    assert trader.atr_sl == 2.0
    assert trader.risk_percent == 0.02


def test_get_trend_up():
    """测试上涨趋势判断"""
    df = create_test_df_with_indicators()
    # 确保MA20在上涨
    df['ma20'] = np.linspace(50000, 50200, len(df))

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    trend = trader._get_trend(df)
    assert trend == 'up'


def test_get_trend_down():
    """测试下跌趋势判断"""
    df = create_test_df_with_indicators()
    # 确保MA20在下跌
    df['ma20'] = np.linspace(50200, 50000, len(df))

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    trend = trader._get_trend(df)
    assert trend == 'down'


def test_get_trend_neutral():
    """测试震荡趋势判断"""
    df = create_test_df_with_indicators()
    # MA20基本持平
    df['ma20'] = 50100

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    trend = trader._get_trend(df)
    assert trend == 'neutral'


def test_is_ranging():
    """测试震荡市判断"""
    df = create_test_df_with_indicators()
    # ADX低，震荡市
    df['adx'] = 15

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    is_ranging = trader._is_ranging(df)
    assert is_ranging == True


def test_not_ranging():
    """测试趋势市判断"""
    df = create_test_df_with_indicators()
    # ADX高，趋势市
    df['adx'] = 35

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    is_ranging = trader._is_ranging(df)
    assert is_ranging == False


def test_get_signal_buy():
    """测试买入信号"""
    df = create_test_df_with_indicators()
    latest = df.iloc[-1]
    latest['rsi'] = 35  # 超卖

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    # 上涨趋势 + RSI超卖 = 买入信号
    signal = trader._get_signal(latest, 'up')
    assert signal == 'buy'


def test_get_signal_sell():
    """测试卖出信号"""
    df = create_test_df_with_indicators()
    latest = df.iloc[-1]
    latest['rsi'] = 65  # 超买

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    # 下跌趋势 + RSI超买 = 卖出信号
    signal = trader._get_signal(latest, 'down')
    assert signal == 'sell'


def test_get_signal_hold():
    """测试持有信号"""
    df = create_test_df_with_indicators()
    latest = df.iloc[-1]
    latest['rsi'] = 50  # 中性

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    signal = trader._get_signal(latest, 'up')
    assert signal == 'hold'


def test_stop_loss_buy():
    """测试多头止损计算"""
    df = create_test_df_with_indicators()
    latest = df.iloc[-1]
    latest['close'] = 50000
    latest['bb_lower'] = 49000
    latest['atr'] = 500

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    stop_loss, tp1, tp2, atr = trader._calculate_stoploss_takeprofit(
        latest, 50000, 'buy'
    )

    # 多头止损应该低于当前价
    assert stop_loss < 50000
    # 止损 ≈ bb_lower - 2*atr
    assert abs(stop_loss - (49000 - 1000)) < 100


def test_stop_loss_sell():
    """测试空头止损计算"""
    df = create_test_df_with_indicators()
    latest = df.iloc[-1]
    latest['close'] = 50000
    latest['bb_upper'] = 51000
    latest['atr'] = 500

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    stop_loss, tp1, tp2, atr = trader._calculate_stoploss_takeprofit(
        latest, 50000, 'sell'
    )

    # 空头止损应该高于当前价
    assert stop_loss > 50000
    # 止损 ≈ bb_upper + 2*atr
    assert abs(stop_loss - (51000 + 1000)) < 100


def test_take_profit_levels():
    """测试止盈分级"""
    df = create_test_df_with_indicators()
    latest = df.iloc[-1]
    latest['close'] = 50000
    latest['bb_lower'] = 49000
    latest['atr'] = 500

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    stop_loss, tp1, tp2, atr = trader._calculate_stoploss_takeprofit(
        latest, 50000, 'buy'
    )

    risk = 50000 - stop_loss
    # TP1 = 1.5倍风险
    assert abs(tp1 - (50000 + risk * 1.5)) < 10
    # TP2 = 3.0倍风险
    assert abs(tp2 - (50000 + risk * 3.0)) < 10
    # TP1 < TP2
    assert tp1 < tp2


def test_analyze_insufficient_data():
    """测试数据不足时的分析"""
    df = pd.DataFrame({'close': [1, 2, 3]})  # 只有3条

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    result = trader.analyze(df, 50000)
    # 数据不足应该返回None
    assert result is None


def test_analyze_with_ranging_market():
    """测试震荡市场下的分析"""
    df = create_test_df_with_indicators()
    df['adx'] = 15  # 震荡
    df['ma20'] = 50100

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    result = trader.analyze(df, 50000, version='moderate')
    # 应该有结果，但仓位可能减半
    assert result is not None


def test_get_max_hours():
    """测试持仓超时时间"""
    df = create_test_df_with_indicators()
    df['adx'] = 35  # 趋势市

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    max_hours = trader.get_max_hours(df)
    # 趋势市应该12小时
    assert max_hours == 12


def test_get_max_hours_ranging():
    """测试震荡市持仓超时时间"""
    df = create_test_df_with_indicators()
    df['adx'] = 15  # 震荡市

    executor = BacktestExecutor(initial_balance=100.0)
    trader = Trader(Config(), executor)

    max_hours = trader.get_max_hours(df)
    # 震荡市应该4小时
    assert max_hours == 4
