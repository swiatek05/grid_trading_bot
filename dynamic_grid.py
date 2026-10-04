import asyncio
import os
import pandas as pd
import pandas_ta as ta
import numpy as np
import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'regime_kmeans.joblib')
FEE = 0.0004


async def fetch_candles(exchange, symbol, timeframe='15m', limit=100):
    try:
        data = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return None


def add_features(df):
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['rsi'] = ta.rsi(df['close'], length=14)

    bb = ta.bbands(df['close'], length=20, std=2)
    df['bb_lower'] = bb.iloc[:, 0]
    df['bb_middle'] = bb.iloc[:, 1]
    df['bb_upper'] = bb.iloc[:, 2]
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

    df['ema_9'] = ta.ema(df['close'], length=9)
    df['ema_50'] = ta.ema(df['close'], length=50)
    df['ema_trend'] = (df['ema_9'] - df['ema_50']) / df['ema_50']

    df.dropna(inplace=True)
    return df


async def get_grid_params(exchange, symbol):
    df = await fetch_candles(exchange, symbol)

    if df is None or len(df) < 60:
        print("Not enough data")
        return None

    df = add_features(df)
    if df.empty:
        print("Feature calc failed")
        return None

    last = df.iloc[-1]
    close = last['close']
    atr = last['atr']
    rsi = last['rsi']
    bb_w = last['bb_width']
    ema_trend = last['ema_trend']

    try:
        regime_data = joblib.load(MODEL_PATH)
    except Exception as e:
        print(f"Model load error: {e}")
        return None

    model = regime_data['model']
    scaler = regime_data['scaler']
    mapping = regime_data['mapping']

    atr_pct = (atr / close) * 100
    log_atr = np.log1p(atr_pct)

    features = pd.DataFrame([[log_atr, bb_w]], columns=['log_atr_percent', 'bb_width'])
    scaled = scaler.transform(features)
    cluster = model.predict(scaled)[0]
    regime = mapping[cluster]

    print(f"[{symbol}] Price: {close} | RSI: {rsi:.2f} | EMA: {ema_trend:.4f} | Regime: {regime}")

    atr_dec = atr / close

    multiplier = {0: 8.0, 1: 15.0, 2: 25.0}.get(regime, 15.0)
    grid_range = max(atr_dec * multiplier, 0.035)

    opt_step = max(atr_dec * 1.2, 5.5 * FEE)
    levels = max(10, min(int((2 * grid_range) / opt_step), 40))

    upper = close * (1 + grid_range)
    lower = close * (1 - grid_range)

    print(f"Grid: {lower:.2f} - {upper:.2f} ({levels} levels)")

    return {
        'symbol': symbol,
        'current_price': close,
        'lower_price': lower,
        'upper_price': upper,
        'count_of_levels': levels,
        'rsi': rsi,
        'ema_trend': ema_trend,
        'regime': regime
    }