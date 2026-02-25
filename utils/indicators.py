import pandas as pd
import numpy as np


def calculate_ma(df: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
    for period in periods:
        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2) -> pd.DataFrame:
    df['bb_middle'] = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_middle'] + (std * std_dev)
    df['bb_lower'] = df['bb_middle'] - (std * std_dev)
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    df['atr'] = true_range.rolling(window=period).mean()
    return df


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()
    
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
    
    atr = df['atr'] if 'atr' in df.columns else calculate_atr(df, period)['atr']
    
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.rolling(window=period).mean()
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    return df


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 60:
        return df
    
    df = calculate_ma(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)
    df = calculate_atr(df)
    df = calculate_adx(df)
    
    return df


def get_indicator_summary(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 60:
        return "数据不足"
    
    latest = df.iloc[-1]
    
    summary = f"""
当前价格: {latest['close']:.2f}

移动平均线:
- MA5: {latest.get('ma5', 0):.2f}
- MA10: {latest.get('ma10', 0):.2f}
- MA20: {latest.get('ma20', 0):.2f}
- MA60: {latest.get('ma60', 0):.2f}

MACD:
- MACD: {latest.get('macd', 0):.4f}
- Signal: {latest.get('macd_signal', 0):.4f}
- Hist: {latest.get('macd_hist', 0):.4f}

RSI(14): {latest.get('rsi', 0):.2f}

布林带:
- Upper: {latest.get('bb_upper', 0):.2f}
- Middle: {latest.get('bb_middle', 0):.2f}
- Lower: {latest.get('bb_lower', 0):.2f}

ATR: {latest.get('atr', 0):.2f}
ADX: {latest.get('adx', 0):.2f}
"""
    return summary
