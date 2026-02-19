"""Tests for the technical indicator wrapper module."""

import pandas as pd
import pytest

from src.indicators.technical import (
    compute_atr,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_volume_ma,
    enrich_dataframe,
)


def _make_ohlcv(n: int = 50) -> pd.DataFrame:
    """Generate a synthetic uptrend OHLCV DataFrame for testing."""
    import numpy as np

    np.random.seed(42)
    base = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame(
        {
            "open": base - 0.2,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base,
            "volume": np.random.uniform(1000, 5000, n),
        }
    )


class TestIndividualIndicators:
    def test_ema_returns_series(self):
        df = _make_ohlcv()
        result = compute_ema(df["close"], 20)
        assert isinstance(result, pd.Series)
        assert len(result) == len(df)

    def test_ema_last_value_finite(self):
        df = _make_ohlcv()
        ema = compute_ema(df["close"], 10)
        assert pd.notna(ema.iloc[-1])

    def test_macd_returns_three_columns(self):
        df = _make_ohlcv()
        macd_line, macd_hist, macd_signal = compute_macd(df["close"])
        assert isinstance(macd_line, pd.Series)
        assert isinstance(macd_hist, pd.Series)
        assert isinstance(macd_signal, pd.Series)
        assert len(macd_line) == len(df)

    def test_rsi_range(self):
        df = _make_ohlcv()
        rsi = compute_rsi(df["close"])
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_atr_positive(self):
        df = _make_ohlcv()
        atr = compute_atr(df["high"], df["low"], df["close"])
        valid = atr.dropna()
        assert (valid >= 0).all()

    def test_volume_ma_length(self):
        df = _make_ohlcv()
        vma = compute_volume_ma(df["volume"], 20)
        assert len(vma) == len(df)


class TestEnrichDataframe:
    def test_adds_expected_columns(self):
        df = _make_ohlcv()
        enriched = enrich_dataframe(df)
        expected = {
            "ema_fast",
            "ema_slow",
            "macd",
            "macd_hist",
            "macd_signal",
            "rsi",
            "atr",
            "volume_ma",
        }
        assert expected.issubset(set(enriched.columns))

    def test_original_columns_preserved(self):
        df = _make_ohlcv()
        enriched = enrich_dataframe(df)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in enriched.columns

    def test_does_not_mutate_input(self):
        df = _make_ohlcv()
        original_cols = set(df.columns)
        _ = enrich_dataframe(df)
        assert set(df.columns) == original_cols
