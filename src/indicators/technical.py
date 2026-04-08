"""Unified technical indicator computation via the `ta` library.

All indicators are computed and appended as new columns to the OHLCV DataFrame.
This module wraps the `ta` library (bukosabino/ta) to keep indicator logic
centralised and testable.
"""

from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return EMAIndicator(close=series, window=period).ema_indicator()


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD — returns (macd_line, histogram, signal_line)."""
    m = MACD(close=series, window_fast=fast, window_slow=slow, window_sign=signal)
    return m.macd(), m.macd_diff(), m.macd_signal()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    return RSIIndicator(close=series, window=period).rsi()


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range."""
    return AverageTrueRange(high=high, low=low, close=close, window=period).average_true_range()


def compute_volume_ma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Simple Moving Average of volume."""
    return volume.rolling(window=period).mean()


def compute_bollinger_bands(
    series: pd.Series,
    period: int = 20,
    std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands — returns (upper, middle, lower)."""
    bb = BollingerBands(close=series, window=period, window_dev=std)
    return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()


def compute_stoch_rsi(
    series: pd.Series,
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """Stochastic RSI — returns (stoch_rsi_k, stoch_rsi_d)."""
    stoch = StochRSIIndicator(close=series, window=period, smooth1=smooth_k, smooth2=smooth_d)
    return stoch.stochrsi_k(), stoch.stochrsi_d()


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average Directional Index."""
    return ADXIndicator(high=high, low=low, close=close, window=period).adx()


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    return OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()


def enrich_dataframe(
    df: pd.DataFrame,
    *,
    ema_fast: int = 20,
    ema_slow: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
    volume_ma_period: int = 20,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bb_period: int = 20,
    bb_std: float = 2.0,
    stoch_rsi_period: int = 14,
    adx_period: int = 14,
) -> pd.DataFrame:
    """Compute all standard indicators and append them as columns.

    Added columns:
      - ema_fast, ema_slow
      - macd, macd_hist, macd_signal
      - rsi
      - atr
      - volume_ma
      - bb_upper, bb_middle, bb_lower
      - stoch_rsi_k, stoch_rsi_d
      - adx
      - obv
    """
    out = df.copy()

    out["ema_fast"] = compute_ema(out["close"], ema_fast)
    out["ema_slow"] = compute_ema(out["close"], ema_slow)

    macd_line, macd_hist, macd_sig = compute_macd(
        out["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal,
    )
    out["macd"] = macd_line
    out["macd_hist"] = macd_hist
    out["macd_signal"] = macd_sig

    out["rsi"] = compute_rsi(out["close"], rsi_period)
    out["atr"] = compute_atr(out["high"], out["low"], out["close"], atr_period)
    out["volume_ma"] = compute_volume_ma(out["volume"], volume_ma_period)

    bb_upper, bb_middle, bb_lower = compute_bollinger_bands(
        out["close"], period=bb_period, std=bb_std,
    )
    out["bb_upper"] = bb_upper
    out["bb_middle"] = bb_middle
    out["bb_lower"] = bb_lower

    stoch_k, stoch_d = compute_stoch_rsi(out["close"], period=stoch_rsi_period)
    out["stoch_rsi_k"] = stoch_k
    out["stoch_rsi_d"] = stoch_d

    out["adx"] = compute_adx(out["high"], out["low"], out["close"], adx_period)
    out["obv"] = compute_obv(out["close"], out["volume"])

    return out
