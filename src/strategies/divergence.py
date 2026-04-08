"""策略二：背離反轉型（Divergence Reversal Model）

Timeframe: 1H

Conditions:
  1. 價格創最近 lookback 根 K 線的 swing low（新低）
  2. RSI 未創新低（Bullish Divergence）
  3. 成交量逐步縮小
  4. RSI < rsi_oversold（超賣區）

Swing Low 定義：
  前後各 swing_window 根 K 線都高於該點，即局部最低。
"""

from __future__ import annotations

import pandas as pd

from src.config import DivergenceConfig
from src.strategies.base import BaseStrategy, StrategyResult


def _find_swing_lows(series: pd.Series, window: int) -> list[int]:
    """Return indices of swing lows in *series*.

    A swing low at index *i* means ``series[i]`` is the minimum in the
    window ``[i - window, i + window]``.
    """
    lows: list[int] = []
    for i in range(window, len(series) - window):
        segment = series.iloc[i - window: i + window + 1]
        if series.iloc[i] == segment.min():
            lows.append(i)
    return lows


class DivergenceStrategy(BaseStrategy):
    """Detect bullish RSI divergence at potential reversal points."""

    def __init__(self, config: DivergenceConfig) -> None:
        self._cfg = config

    @property
    def name(self) -> str:
        return "背離反轉型"

    @property
    def timeframe(self) -> str:
        return self._cfg.timeframe

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        w = self._cfg.weights
        score = 0
        details: list[str] = []
        max_score = int(w.total())
        lookback = self._cfg.lookback

        if len(df) < lookback:
            return StrategyResult(self.name, 0, max_score)

        recent = df.iloc[-lookback:].copy()
        recent = recent.reset_index(drop=True)
        cur_idx = len(recent) - 1
        cur = recent.iloc[cur_idx]

        # ── 1. Price new low ─────────────────────────────────────────────
        price_low_weight = getattr(w, "price_new_low", 0)
        price_is_new_low = cur["low"] <= recent["low"].min()
        if price_is_new_low:
            score += price_low_weight
            details.append(f"價格創 {lookback} 根 K 線新低")

        # ── 2. RSI bullish divergence ────────────────────────────────────
        rsi_div_weight = getattr(w, "rsi_divergence", 0)
        swing_window = self._cfg.swing_window
        swing_lows = _find_swing_lows(recent["low"], swing_window)
        prior_swings = [i for i in swing_lows if i < cur_idx - swing_window]

        if "rsi" in recent.columns and pd.notna(cur.get("rsi")):
            # We need at least one *prior* swing low to compare against
            if prior_swings and price_is_new_low:
                prev_swing_idx = prior_swings[-1]
                # Bullish divergence: price lower low, RSI higher low
                if (
                    recent["low"].iloc[cur_idx] < recent["low"].iloc[prev_swing_idx]
                    and pd.notna(recent["rsi"].iloc[prev_swing_idx])
                    and recent["rsi"].iloc[cur_idx] > recent["rsi"].iloc[prev_swing_idx]
                ):
                    score += rsi_div_weight
                    details.append(
                        f"RSI 背離：價格新低但 RSI "
                        f"{recent['rsi'].iloc[cur_idx]:.1f} > "
                        f"前低 {recent['rsi'].iloc[prev_swing_idx]:.1f}"
                    )

        # ── 2b. Stochastic RSI divergence (more sensitive) ───────────────
        stoch_div_weight = getattr(w, "stoch_rsi_divergence", 0)
        if "stoch_rsi_k" in recent.columns and pd.notna(cur.get("stoch_rsi_k")):
            if prior_swings and price_is_new_low:
                prev_swing_idx = prior_swings[-1]
                # Bullish divergence: price lower, stoch RSI higher
                if (
                    pd.notna(recent["stoch_rsi_k"].iloc[prev_swing_idx])
                    and recent["stoch_rsi_k"].iloc[cur_idx] > recent["stoch_rsi_k"].iloc[prev_swing_idx]
                ):
                    score += stoch_div_weight
                    details.append(
                        f"Stoch RSI 背離：{recent['stoch_rsi_k'].iloc[cur_idx]:.1f} > "
                        f"前低 {recent['stoch_rsi_k'].iloc[prev_swing_idx]:.1f}"
                    )

        # ── 3. Volume declining ──────────────────────────────────────────
        vol_weight = getattr(w, "volume_decline", 0)
        if "volume_ma" in recent.columns and len(recent) >= 15:
            recent_vol_ma = recent["volume_ma"].iloc[-5:].mean()
            prior_vol_ma = recent["volume_ma"].iloc[-15:-5].mean()
            if prior_vol_ma > 0 and recent_vol_ma < prior_vol_ma:
                score += vol_weight
                ratio = recent_vol_ma / prior_vol_ma
                details.append(f"成交量縮小（近期/前期 = {ratio:.2f}）")

        # ── 4. RSI oversold ──────────────────────────────────────────────
        oversold_weight = getattr(w, "oversold", 0)
        if pd.notna(cur.get("rsi")) and cur["rsi"] < self._cfg.rsi_oversold:
            score += oversold_weight
            details.append(f"RSI {cur['rsi']:.1f} < {self._cfg.rsi_oversold}（超賣）")

        # ── 5. OBV confirmation (look for OBV divergence too) ────────────
        obv_weight = getattr(w, "obv_confirm", 0)
        if "obv" in recent.columns and len(recent) >= 5:
            recent_obv_trend = recent["obv"].iloc[-1] - recent["obv"].iloc[-5]
            if recent_obv_trend > 0:  # OBV rising while price falling = bullish
                score += obv_weight
                details.append("OBV 上升（量能背離）")

        # Key levels
        cur_low = float(cur.get("low") or 0)
        atr = float(cur.get("atr") or 0)
        key_levels: dict = {}
        if cur_low > 0:
            key_levels["stop"] = round(cur_low - 0.5 * atr, 6)
            key_levels["support"] = round(cur_low, 6)
            key_levels["target"] = round(float(recent["high"].max()), 6)

        return StrategyResult(self.name, score, max_score, details, direction="long", key_levels=key_levels)
