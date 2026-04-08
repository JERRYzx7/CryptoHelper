"""Tests for the technical indicator wrapper module."""

import pandas as pd
import pytest

from src.indicators.technical import (
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_obv,
    compute_rsi,
    compute_stoch_rsi,
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

    def test_compute_bollinger_bands(self):
        df = _make_ohlcv()
        upper, middle, lower = compute_bollinger_bands(df["close"], period=20, std=2.0)
        # Returns 3 Series
        assert isinstance(upper, pd.Series)
        assert isinstance(middle, pd.Series)
        assert isinstance(lower, pd.Series)
        assert len(upper) == len(df)
        # Middle band is SMA (validate against rolling mean)
        expected_sma = df["close"].rolling(window=20).mean()
        pd.testing.assert_series_equal(middle, expected_sma, check_names=False)
        # Upper > middle > lower (where valid)
        valid_idx = middle.dropna().index
        assert (upper.loc[valid_idx] >= middle.loc[valid_idx]).all()
        assert (middle.loc[valid_idx] >= lower.loc[valid_idx]).all()

    def test_compute_stoch_rsi(self):
        df = _make_ohlcv()
        k, d = compute_stoch_rsi(df["close"], period=14, smooth_k=3, smooth_d=3)
        # Returns 2 Series
        assert isinstance(k, pd.Series)
        assert isinstance(d, pd.Series)
        assert len(k) == len(df)
        assert len(d) == len(df)
        # Values are in 0-100 range (ta library returns 0-1 scaled to 0-100)
        valid_k = k.dropna()
        valid_d = d.dropna()
        assert (valid_k >= 0).all() and (valid_k <= 100).all()
        assert (valid_d >= 0).all() and (valid_d <= 100).all()

    def test_compute_adx(self):
        df = _make_ohlcv()
        adx = compute_adx(df["high"], df["low"], df["close"], period=14)
        # Returns 1 Series
        assert isinstance(adx, pd.Series)
        assert len(adx) == len(df)
        # ADX values are 0-100
        valid = adx.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_compute_obv(self):
        df = _make_ohlcv()
        obv = compute_obv(df["close"], df["volume"])
        # Returns 1 Series
        assert isinstance(obv, pd.Series)
        assert len(obv) == len(df)
        # OBV follows cumulative volume logic: increases when close > prev close
        # Test that OBV changes direction based on price movement
        for i in range(1, min(10, len(df))):
            price_diff = df["close"].iloc[i] - df["close"].iloc[i - 1]
            obv_diff = obv.iloc[i] - obv.iloc[i - 1]
            if price_diff > 0:
                assert obv_diff > 0, f"OBV should increase when price rises at index {i}"
            elif price_diff < 0:
                assert obv_diff < 0, f"OBV should decrease when price falls at index {i}"


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

    def test_enrich_dataframe_new_indicators(self):
        df = _make_ohlcv()
        enriched = enrich_dataframe(df)
        new_columns = {
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "stoch_rsi_k",
            "stoch_rsi_d",
            "adx",
            "obv",
        }
        assert new_columns.issubset(set(enriched.columns))
        # Verify the values are actually computed (not all NaN)
        for col in new_columns:
            assert enriched[col].notna().any(), f"Column {col} should have valid values"
        # Verify Bollinger Bands relationship
        valid_idx = enriched["bb_middle"].dropna().index
        assert (enriched.loc[valid_idx, "bb_upper"] >= enriched.loc[valid_idx, "bb_middle"]).all()
        assert (enriched.loc[valid_idx, "bb_middle"] >= enriched.loc[valid_idx, "bb_lower"]).all()
        # Verify stoch RSI and ADX ranges
        valid_k = enriched["stoch_rsi_k"].dropna()
        assert (valid_k >= 0).all() and (valid_k <= 100).all()
        valid_adx = enriched["adx"].dropna()
        assert (valid_adx >= 0).all() and (valid_adx <= 100).all()
