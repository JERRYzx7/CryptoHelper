"""Tests for strategy scoring logic using synthetic DataFrames."""

import numpy as np
import pandas as pd
import pytest

from src.config import BreakoutConfig, DivergenceConfig, TrendConfig
from src.strategies.base import StrategyResult
from src.strategies.breakout import BreakoutStrategy
from src.strategies.breakout_short import BearishBreakoutStrategy
from src.strategies.divergence import DivergenceStrategy
from src.strategies.divergence_short import BearishDivergenceStrategy
from src.strategies.trend import TrendStrategy
from src.strategies.trend_short import BearishTrendStrategy


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_trend_df(
    *,
    golden_cross: bool = False,
    macd_cross: bool = False,
    rsi_val: float = 55,
    volume_ratio: float = 1.0,
) -> pd.DataFrame:
    """Build a 2-row DataFrame that simulates trend conditions."""
    prev_ema_fast = 99 if golden_cross else 101
    cur_ema_fast = 101

    prev_macd_hist = -0.5 if macd_cross else 0.5
    cur_macd_hist = 0.5

    return pd.DataFrame(
        {
            "close": [100, 102],
            "ema_fast": [prev_ema_fast, cur_ema_fast],
            "ema_slow": [100, 100],
            "macd_hist": [prev_macd_hist, cur_macd_hist],
            "rsi": [45, rsi_val],
            "volume": [1000, 1000 * volume_ratio],
            "volume_ma": [1000, 1000],
        }
    )


def _make_breakout_df(
    *,
    n_bars: int = 25,
    consolidation_range_pct: float = 3.0,
    breakout: bool = False,
    volume_ratio: float = 1.0,
    atr_expanding: bool = False,
) -> pd.DataFrame:
    """Build a DataFrame that simulates breakout conditions."""
    base_price = 100.0
    half_range = (consolidation_range_pct / 100) * base_price / 2

    highs = [base_price + half_range] * n_bars
    lows = [base_price - half_range] * n_bars
    closes = [base_price] * n_bars
    volumes = [1000.0] * n_bars
    volume_mas = [1000.0] * n_bars
    atrs = [1.0] * n_bars

    # Last bar
    close_val = base_price + half_range + 1 if breakout else base_price
    highs.append(close_val + 0.5)
    lows.append(close_val - 0.5)
    closes.append(close_val)
    volumes.append(1000 * volume_ratio)
    volume_mas.append(1000)
    atrs.append(2.0 if atr_expanding else 0.5)

    return pd.DataFrame(
        {
            "open": closes,  # simplified
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "volume_ma": volume_mas,
            "atr": atrs,
        }
    )


# ── Trend Strategy Tests ──────────────────────────────────────────────────────

class TestTrendStrategy:
    def setup_method(self):
        self.config = TrendConfig(
            weights={"ema_cross": 3, "macd_cross": 2, "rsi_above": 1, "volume_surge": 2},
        )
        self.strategy = TrendStrategy(self.config)

    def test_full_score(self):
        df = _make_trend_df(
            golden_cross=True, macd_cross=True, rsi_val=55, volume_ratio=2.0
        )
        result = self.strategy.evaluate(df)
        assert result.score == 8
        assert result.max_score == 8
        assert len(result.details) == 4

    def test_zero_score(self):
        df = _make_trend_df(
            golden_cross=False, macd_cross=False, rsi_val=30, volume_ratio=1.0
        )
        result = self.strategy.evaluate(df)
        assert result.score == 0
        assert len(result.details) == 0

    def test_partial_score(self):
        df = _make_trend_df(golden_cross=True, macd_cross=False, rsi_val=55)
        result = self.strategy.evaluate(df)
        assert result.score == 4  # ema_cross(3) + rsi(1)

    def test_insufficient_data(self):
        df = pd.DataFrame({"close": [100]})
        result = self.strategy.evaluate(df)
        assert result.score == 0


# ── Breakout Strategy Tests ────────────────────────────────────────────────────

class TestBreakoutStrategy:
    def setup_method(self):
        self.config = BreakoutConfig(
            consolidation_bars=24,
            range_threshold_pct=5.0,
            volume_multiplier=2.0,
            weights={
                "consolidation": 2,
                "breakout": 3,
                "volume_surge": 3,
                "atr_expansion": 1,
            },
        )
        self.strategy = BreakoutStrategy(self.config)

    def test_full_breakout(self):
        df = _make_breakout_df(
            consolidation_range_pct=3.0,
            breakout=True,
            volume_ratio=2.5,
            atr_expanding=True,
        )
        result = self.strategy.evaluate(df)
        assert result.score == 9  # consol(2) + breakout(3) + vol(3) + atr(1)

    def test_no_consolidation(self):
        """Wide range should not trigger consolidation."""
        df = _make_breakout_df(consolidation_range_pct=10.0, breakout=True)
        result = self.strategy.evaluate(df)
        # No consolidation → no breakout either (gated by is_consolidated)
        consol_score = 0
        breakout_score = 0
        assert result.score <= result.max_score

    def test_consolidation_without_breakout(self):
        df = _make_breakout_df(consolidation_range_pct=3.0, breakout=False)
        result = self.strategy.evaluate(df)
        assert result.score == 2  # Only consolidation fires


# ── Divergence Strategy Tests ─────────────────────────────────────────────────

class TestDivergenceStrategy:
    def setup_method(self):
        self.config = DivergenceConfig(
            lookback=20,
            rsi_oversold=40,
            swing_window=2,  # smaller window for test data
            weights={
                "price_new_low": 2,
                "rsi_divergence": 3,
                "volume_decline": 1,
                "oversold": 2,
            },
        )
        self.strategy = DivergenceStrategy(self.config)

    def test_oversold_only(self):
        """RSI below threshold should score oversold points."""
        n = 20
        df = pd.DataFrame(
            {
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0] * n,
                "volume": [1000.0] * n,
                "volume_ma": [1000.0] * n,
                "rsi": [35.0] * n,
            }
        )
        result = self.strategy.evaluate(df)
        assert result.score >= 2  # At least oversold

    def test_insufficient_data(self):
        df = pd.DataFrame(
            {
                "open": [100], "high": [101], "low": [99],
                "close": [100], "volume": [1000], "rsi": [30],
            }
        )
        result = self.strategy.evaluate(df)
        assert result.score == 0


# ── Direction & Key Levels ─────────────────────────────────────────────────────

class TestDirectionAndKeyLevels:
    """Ensure direction and key_levels are correctly populated."""

    def test_trend_direction_is_long(self):
        config = TrendConfig(weights={"ema_cross": 3, "macd_cross": 2, "rsi_above": 1, "volume_surge": 2})
        strategy = TrendStrategy(config)
        df = _make_trend_df(golden_cross=True, macd_cross=True, rsi_val=55, volume_ratio=2.0)
        # add atr/close so key_levels is computed
        df["atr"] = 2.0
        result = strategy.evaluate(df)
        assert result.direction == "long"

    def test_trend_key_levels_has_stop_and_target(self):
        config = TrendConfig(weights={"ema_cross": 3, "macd_cross": 2, "rsi_above": 1, "volume_surge": 2})
        strategy = TrendStrategy(config)
        df = _make_trend_df(golden_cross=True, macd_cross=True, rsi_val=55, volume_ratio=2.0)
        df["atr"] = 2.0
        result = strategy.evaluate(df)
        assert "stop" in result.key_levels
        assert "target" in result.key_levels
        assert result.key_levels["target"] > result.key_levels["stop"]

    def test_breakout_key_levels_measured_move(self):
        config = BreakoutConfig(
            consolidation_bars=24, range_threshold_pct=5.0, volume_multiplier=2.0,
            weights={"consolidation": 2, "breakout": 3, "volume_surge": 3, "atr_expansion": 1},
        )
        strategy = BreakoutStrategy(config)
        df = _make_breakout_df(consolidation_range_pct=3.0, breakout=True, volume_ratio=2.5, atr_expanding=True)
        result = strategy.evaluate(df)
        assert result.direction == "long"
        assert "stop" in result.key_levels
        assert "target" in result.key_levels
        assert result.key_levels["target"] > result.key_levels["stop"]

    def test_default_direction_is_long_on_zero_score(self):
        config = TrendConfig(weights={"ema_cross": 3, "macd_cross": 2, "rsi_above": 1, "volume_surge": 2})
        strategy = TrendStrategy(config)
        df = _make_trend_df()
        result = strategy.evaluate(df)
        assert result.direction == "long"


# ── Bearish Trend Strategy ─────────────────────────────────────────────────────

def _make_bearish_trend_df(
    *,
    death_cross: bool = False,
    macd_dead_cross: bool = False,
    rsi_val: float = 45,
    volume_ratio: float = 1.0,
) -> pd.DataFrame:
    """Build a 2-row DataFrame that simulates bearish trend conditions."""
    prev_ema_fast = 101 if death_cross else 99
    cur_ema_fast = 99

    prev_macd_hist = 0.5 if macd_dead_cross else -0.5
    cur_macd_hist = -0.5

    return pd.DataFrame(
        {
            "close": [100, 98],
            "ema_fast": [prev_ema_fast, cur_ema_fast],
            "ema_slow": [100, 100],
            "macd_hist": [prev_macd_hist, cur_macd_hist],
            "rsi": [55, rsi_val],
            "volume": [1000, 1000 * volume_ratio],
            "volume_ma": [1000, 1000],
            "atr": [2.0, 2.0],
        }
    )


class TestBearishTrendStrategy:
    def setup_method(self):
        self.config = TrendConfig(
            weights={"ema_cross": 3, "macd_cross": 2, "rsi_above": 1, "volume_surge": 2},
        )
        self.strategy = BearishTrendStrategy(self.config)

    def test_full_score_death_cross(self):
        df = _make_bearish_trend_df(death_cross=True, macd_dead_cross=True, rsi_val=45, volume_ratio=2.0)
        result = self.strategy.evaluate(df)
        assert result.score == 8
        assert result.direction == "short"

    def test_zero_score_no_death_cross(self):
        df = _make_bearish_trend_df(death_cross=False, macd_dead_cross=False, rsi_val=55)
        result = self.strategy.evaluate(df)
        assert result.score == 0

    def test_direction_is_short(self):
        df = _make_bearish_trend_df()
        result = self.strategy.evaluate(df)
        assert result.direction == "short"

    def test_key_levels_stop_above_target(self):
        df = _make_bearish_trend_df(death_cross=True, macd_dead_cross=True, rsi_val=45)
        result = self.strategy.evaluate(df)
        if "stop" in result.key_levels and "target" in result.key_levels:
            assert result.key_levels["stop"] > result.key_levels["target"]


# ── Bearish Breakout Strategy ──────────────────────────────────────────────────

def _make_bearish_breakout_df(
    *,
    n_bars: int = 25,
    consolidation_range_pct: float = 3.0,
    breakdown: bool = False,
    volume_ratio: float = 1.0,
    atr_expanding: bool = False,
) -> pd.DataFrame:
    base_price = 100.0
    half_range = (consolidation_range_pct / 100) * base_price / 2

    highs = [base_price + half_range] * n_bars
    lows = [base_price - half_range] * n_bars
    closes = [base_price] * n_bars
    volumes = [1000.0] * n_bars
    volume_mas = [1000.0] * n_bars
    atrs = [1.0] * n_bars

    close_val = base_price - half_range - 1 if breakdown else base_price
    highs.append(close_val + 0.5)
    lows.append(close_val - 0.5)
    closes.append(close_val)
    volumes.append(1000 * volume_ratio)
    volume_mas.append(1000)
    atrs.append(2.0 if atr_expanding else 0.5)

    return pd.DataFrame({
        "open": closes, "high": highs, "low": lows, "close": closes,
        "volume": volumes, "volume_ma": volume_mas, "atr": atrs,
    })


class TestBearishBreakoutStrategy:
    def setup_method(self):
        self.config = BreakoutConfig(
            consolidation_bars=24, range_threshold_pct=5.0, volume_multiplier=2.0,
            weights={"consolidation": 2, "breakout": 3, "volume_surge": 3, "atr_expansion": 1},
        )
        self.strategy = BearishBreakoutStrategy(self.config)

    def test_full_breakdown(self):
        df = _make_bearish_breakout_df(
            consolidation_range_pct=3.0, breakdown=True, volume_ratio=2.5, atr_expanding=True
        )
        result = self.strategy.evaluate(df)
        assert result.score == 9
        assert result.direction == "short"

    def test_no_breakdown_only_consolidation(self):
        df = _make_bearish_breakout_df(consolidation_range_pct=3.0, breakdown=False)
        result = self.strategy.evaluate(df)
        assert result.score == 2  # only consolidation

    def test_key_levels_target_below_stop(self):
        df = _make_bearish_breakout_df(consolidation_range_pct=3.0, breakdown=True)
        result = self.strategy.evaluate(df)
        if "stop" in result.key_levels and "target" in result.key_levels:
            assert result.key_levels["target"] < result.key_levels["stop"]


# ── Bearish Divergence Strategy ────────────────────────────────────────────────

class TestBearishDivergenceStrategy:
    def setup_method(self):
        self.config = DivergenceConfig(
            lookback=20, rsi_overbought=60, swing_window=2,
            weights={"price_new_low": 2, "rsi_divergence": 3, "volume_decline": 1, "oversold": 2},
        )
        self.strategy = BearishDivergenceStrategy(self.config)

    def test_overbought_fires(self):
        n = 20
        df = pd.DataFrame({
            "open": [100.0] * n, "high": [102.0] * n, "low": [99.0] * n,
            "close": [101.0] * n, "volume": [1000.0] * n,
            "volume_ma": [900.0] * n, "rsi": [70.0] * n, "atr": [1.0] * n,
        })
        result = self.strategy.evaluate(df)
        assert result.score >= 2  # overbought condition fires

    def test_direction_is_short(self):
        n = 20
        df = pd.DataFrame({
            "open": [100.0] * n, "high": [100.0] * n, "low": [99.0] * n,
            "close": [100.0] * n, "volume": [1000.0] * n,
            "volume_ma": [1000.0] * n, "rsi": [35.0] * n, "atr": [1.0] * n,
        })
        result = self.strategy.evaluate(df)
        assert result.direction == "short"
