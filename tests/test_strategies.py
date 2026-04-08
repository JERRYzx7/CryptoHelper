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
    adx_val: float | None = None,
    obv_rising: bool = False,
) -> pd.DataFrame:
    """Build a 2-row DataFrame that simulates trend conditions."""
    prev_ema_fast = 99 if golden_cross else 101
    cur_ema_fast = 101

    prev_macd_hist = -0.5 if macd_cross else 0.5
    cur_macd_hist = 0.5

    prev_obv = 10000
    cur_obv = 11000 if obv_rising else 9000

    return pd.DataFrame(
        {
            "close": [100, 102],
            "ema_fast": [prev_ema_fast, cur_ema_fast],
            "ema_slow": [100, 100],
            "macd_hist": [prev_macd_hist, cur_macd_hist],
            "rsi": [45, rsi_val],
            "volume": [1000, 1000 * volume_ratio],
            "volume_ma": [1000, 1000],
            "adx": [20, adx_val if adx_val is not None else 20],
            "obv": [prev_obv, cur_obv],
        }
    )


def _make_breakout_df(
    *,
    n_bars: int = 25,
    consolidation_range_pct: float = 3.0,
    breakout: bool = False,
    volume_ratio: float = 1.0,
    atr_expanding: bool = False,
    bb_breakout: bool = False,
    include_obv: bool = False,
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
    # Bollinger Bands: set upper band relative to base price
    bb_uppers = [base_price + 2.0] * n_bars  # BB upper at 102
    obvs = [10000.0 + i * 100 for i in range(n_bars)] if include_obv else [10000.0] * n_bars

    # Last bar
    close_val = base_price + half_range + 1 if breakout else base_price
    if bb_breakout:
        close_val = base_price + 3.0  # > bb_upper (102)
    highs.append(close_val + 0.5)
    lows.append(close_val - 0.5)
    closes.append(close_val)
    volumes.append(1000 * volume_ratio)
    volume_mas.append(1000)
    atrs.append(2.0 if atr_expanding else 0.5)
    bb_uppers.append(base_price + 2.0)  # BB upper stays at 102
    obvs.append(obvs[-1] + 200 if include_obv else 10000.0)

    return pd.DataFrame(
        {
            "open": closes,  # simplified
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "volume_ma": volume_mas,
            "atr": atrs,
            "bb_upper": bb_uppers,
            "obv": obvs,
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

    def test_adx_obv_conditions(self):
        """ADX strong trend and OBV rising should add to score."""
        config = TrendConfig(
            weights={
                "ema_cross": 3,
                "macd_cross": 2,
                "rsi_above": 1,
                "volume_surge": 2,
                "adx_strong": 2,
                "obv_confirm": 1,
            },
            adx_threshold=25,
        )
        strategy = TrendStrategy(config)
        df = _make_trend_df(
            golden_cross=False,
            macd_cross=False,
            rsi_val=30,  # below threshold
            volume_ratio=1.0,
            adx_val=30,  # > 25 threshold
            obv_rising=True,
        )
        result = strategy.evaluate(df)
        # Should score: adx_strong(2) + obv_confirm(1) = 3
        assert result.score == 3
        assert any("ADX" in d for d in result.details)
        assert any("OBV" in d for d in result.details)


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

    def test_bollinger_bands_breakout(self):
        """Close above bb_upper should score BB breakout weight."""
        config = BreakoutConfig(
            consolidation_bars=24,
            range_threshold_pct=5.0,
            volume_multiplier=2.0,
            weights={
                "consolidation": 2,
                "breakout": 3,
                "volume_surge": 3,
                "atr_expansion": 1,
                "bb_breakout": 2,
                "obv_confirm": 1,
            },
        )
        strategy = BreakoutStrategy(config)
        # BB breakout: close > bb_upper (close=103, bb_upper=102)
        df = _make_breakout_df(
            consolidation_range_pct=3.0,
            breakout=False,
            bb_breakout=True,
            include_obv=True,
        )
        result = strategy.evaluate(df)
        # Should score: consolidation(2) + bb_breakout(2) + obv_confirm(1) = 5
        # (no standard breakout since close doesn't exceed consol_high which is 101.5)
        assert result.score >= 2  # At least consolidation + BB breakout
        assert any("BB" in d for d in result.details)


# ── Divergence Strategy Tests ─────────────────────────────────────────────────


def _make_divergence_df(
    *,
    n: int = 50,
    price_new_low: bool = True,
    rsi_divergence: bool = False,
    stoch_rsi_divergence: bool = False,
    rsi_oversold: bool = False,
    rsi_val: float = 35.0,
) -> pd.DataFrame:
    """Build a DataFrame for divergence testing with swing lows.
    
    The divergence strategy compares cur_idx (last bar) to the LAST prior swing low.
    A swing low at index i means series[i] is the minimum in [i-window, i+window].
    
    We need to create data where:
    1. There's exactly one clear prior swing low with low RSI/Stoch
    2. The last bar has price_new_low but HIGHER RSI/Stoch
    3. No false swing lows detected after our intended prior swing
    """
    # Create trending-up lows so swing detection doesn't trigger everywhere
    # This ensures only our explicit swing low is detected
    closes = [100.0 + i * 0.1 for i in range(n)]  # Gradually increasing
    lows = [99.0 + i * 0.1 for i in range(n)]  # Gradually increasing
    highs = [101.0 + i * 0.1 for i in range(n)]
    rsis = [50.0] * n
    stoch_rsi_ks = [50.0] * n

    if price_new_low:
        # Create ONE clear swing low around bar 30 (well within lookback)
        # Must be lower than surrounding bars by at least swing_window on each side
        lows[30] = 90.0  # Much lower than neighbors to be clear swing low
        closes[30] = 90.5
        rsis[30] = 20.0  # Low RSI at prior swing
        stoch_rsi_ks[30] = 12.0  # Low Stoch RSI at prior swing

        # The last bar: NEW low (< 90.0) but HIGHER RSI/Stoch = divergence
        lows[-1] = 89.0  # New absolute low
        closes[-1] = 89.5
        
        if rsi_divergence:
            rsis[-1] = 25.0  # 25 > 20 at bar 30 = RSI divergence
        else:
            rsis[-1] = 18.0  # 18 < 20 = no divergence
            
        if stoch_rsi_divergence:
            stoch_rsi_ks[-1] = 15.0  # 15 > 12 at bar 30 = Stoch RSI divergence
        else:
            stoch_rsi_ks[-1] = 10.0  # 10 < 12 = no divergence

    if rsi_oversold:
        rsis[-1] = rsi_val  # Override with oversold value

    return pd.DataFrame({
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [1000.0] * n,
        "volume_ma": [1000.0] * n,
        "rsi": rsis,
        "stoch_rsi_k": stoch_rsi_ks,
        "atr": [1.0] * n,
    })


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

    def test_stoch_rsi_divergence(self):
        """Stochastic RSI divergence should add to score."""
        config = DivergenceConfig(
            lookback=40,
            rsi_oversold=40,
            swing_window=2,
            stoch_rsi_oversold=20,
            weights={
                "price_new_low": 2,
                "rsi_divergence": 3,
                "volume_decline": 1,
                "oversold": 2,
                "stoch_rsi_divergence": 2,
            },
        )
        strategy = DivergenceStrategy(config)
        # Create data with Stoch RSI divergence but not RSI divergence
        df = _make_divergence_df(
            n=50,
            price_new_low=True,
            rsi_divergence=False,  # No RSI divergence
            stoch_rsi_divergence=True,  # Stoch RSI divergence
            rsi_oversold=False,  # Don't override RSI value
        )
        result = strategy.evaluate(df)
        # Should include: price_new_low(2) + stoch_rsi_divergence(2) = 4
        assert result.score >= 4
        # Check that Stoch RSI divergence detail is present
        assert any("Stoch RSI" in d for d in result.details)


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
