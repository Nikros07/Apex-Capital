import asyncio
from functools import partial
from typing import Optional

import pandas as pd
import yfinance as yf


def _fetch_ohlcv_sync(ticker: str, period: str) -> pd.DataFrame:
    t = yf.Ticker(ticker)
    return t.history(period=period)


def _fetch_info_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    return t.info or {}


def _fetch_price_sync(ticker: str) -> float:
    t = yf.Ticker(ticker)
    info = t.info or {}
    price = (
        info.get("regularMarketPrice")
        or info.get("currentPrice")
        or info.get("previousClose")
        or 0.0
    )
    return float(price)


async def fetch_ohlcv(ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_fetch_ohlcv_sync, ticker, period))
    except Exception:
        return None


async def fetch_info(ticker: str) -> dict:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_fetch_info_sync, ticker))
    except Exception:
        return {}


async def fetch_current_price(ticker: str) -> float:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_fetch_price_sync, ticker))
    except Exception:
        return 0.0


def compute_indicators(df: pd.DataFrame) -> dict:
    if df is None or df.empty or len(df) < 20:
        return {}

    try:
        import ta
    except ImportError:
        return {"current_price": float(df["Close"].iloc[-1])}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    current_price = float(close.iloc[-1])

    rsi_val = float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1])
    ema20_series = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema20 = float(ema20_series.iloc[-1])

    ema50 = None
    ema_crossover = "NONE"
    if len(df) >= 50:
        ema50_series = ta.trend.EMAIndicator(close, window=50).ema_indicator()
        ema50 = float(ema50_series.iloc[-1])
        ema20_prev = float(ema20_series.iloc[-2])
        ema50_prev = float(ema50_series.iloc[-2])
        if ema20 > ema50 and ema20_prev <= ema50_prev:
            ema_crossover = "GOLDEN_CROSS"
        elif ema20 < ema50 and ema20_prev >= ema50_prev:
            ema_crossover = "DEATH_CROSS"

    macd_ind = ta.trend.MACD(close)
    macd_val = float(macd_ind.macd().iloc[-1])
    macd_signal = float(macd_ind.macd_signal().iloc[-1])
    macd_diff = float(macd_ind.macd_diff().iloc[-1])

    _atr_series = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    atr_raw = _atr_series.iloc[-1]
    atr_val = float(atr_raw) if not (atr_raw != atr_raw) else current_price * 0.02  # NaN fallback

    bb = ta.volatility.BollingerBands(close, window=20)
    bb_upper = float(bb.bollinger_hband().iloc[-1])
    bb_lower = float(bb.bollinger_lband().iloc[-1])
    bb_mid = float(bb.bollinger_mavg().iloc[-1])

    vol_avg_20 = float(volume.rolling(20).mean().iloc[-1])
    vol_current = float(volume.iloc[-1])
    vol_ratio = vol_current / vol_avg_20 if vol_avg_20 > 0 else 1.0

    resistance = float(high.rolling(20).max().iloc[-1])
    support = float(low.rolling(20).min().iloc[-1])

    if ema50:
        trend = "UPTREND" if ema20 > ema50 else "DOWNTREND"
    else:
        trend = "UPTREND" if current_price > ema20 else "DOWNTREND"

    return {
        "current_price": round(current_price, 4),
        "rsi": round(rsi_val, 2),
        "ema20": round(ema20, 4),
        "ema50": round(ema50, 4) if ema50 else None,
        "macd": round(macd_val, 6),
        "macd_signal": round(macd_signal, 6),
        "macd_diff": round(macd_diff, 6),
        "atr": round(atr_val, 4),
        "bb_upper": round(bb_upper, 4),
        "bb_lower": round(bb_lower, 4),
        "bb_mid": round(bb_mid, 4),
        "volume_ratio": round(vol_ratio, 2),
        "support": round(support, 4),
        "resistance": round(resistance, 4),
        "trend": trend,
        "ema_crossover": ema_crossover,
    }


async def fetch_indicators(ticker: str) -> dict:
    df = await fetch_ohlcv(ticker)
    if df is None or df.empty:
        return {}
    return compute_indicators(df)
