"""策略二（空）：背離反轉型-空頭（Bearish Divergence Model）

Timeframe: 1H  (reuses DivergenceConfig)

Conditions:
  1. 價格創最近 lookback 根 K 線新高
  2. RSI 未跟創新高（Bearish Divergence：價格更高但 RSI 更低）
  3. 成交量逐步放大（追高跡象）
  4. RSI > rsi_overbought（超買區）
"""

from __future__ import annotations

import pandas as pd

from src.config import DivergenceConfig
from src.strategies.base import BaseStrategy, StrategyResult


def _find_swing_highs(series: pd.Series, window: int) -> list[int]:
    """Return indices of swing highs — local maximums in *series*."""
    highs: list[int] = []
    for i in range(window, len(series) - window):
        segment = series.iloc[i - window: i + window + 1]
        if series.iloc[i] == segment.max():
            highs.append(i)
    return highs


class BearishDivergenceStrategy(BaseStrategy):
    """Detect bearish RSI divergence at potential reversal tops."""

    def __init__(self, config: DivergenceConfig) -> None:
        self._cfg = config

    @property
    def name(self) -> str:
        return "背離反轉型(空)"

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
            return StrategyResult(self.name, 0, max_score, direction="short")

        recent = df.iloc[-lookback:].copy().reset_index(drop=True)
        cur_idx = len(recent) - 1
        cur = recent.iloc[cur_idx]

        # ── 1. Price new high ─────────────────────────────────────────────
        price_high_weight = getattr(w, "price_new_low", 0)  # reuse same weight key
        price_is_new_high = cur["high"] >= recent["high"].max()
        if price_is_new_high:
            score += price_high_weight
            details.append(f"價格創 {lookback} 根 K 線新高")

        # ── 2. RSI bearish divergence ────────────────────────────────────
        rsi_div_weight = getattr(w, "rsi_divergence", 0)
        swing_window = self._cfg.swing_window

        if "rsi" in recent.columns and pd.notna(cur.get("rsi")):
            swing_highs = _find_swing_highs(recent["high"], swing_window)
            prior_swings = [i for i in swing_highs if i < cur_idx - swing_window]
            if prior_swings and price_is_new_high:
                prev_swing_idx = prior_swings[-1]
                if (
                    recent["high"].iloc[cur_idx] > recent["high"].iloc[prev_swing_idx]
                    and pd.notna(recent["rsi"].iloc[prev_swing_idx])
                    and recent["rsi"].iloc[cur_idx] < recent["rsi"].iloc[prev_swing_idx]
                ):
                    score += rsi_div_weight
                    details.append(
                        f"RSI 背離：價格新高但 RSI "
                        f"{recent['rsi'].iloc[cur_idx]:.1f} < "
                        f"前高 {recent['rsi'].iloc[prev_swing_idx]:.1f}"
                    )

            # 2b. Stochastic RSI divergence (more sensitive)
            stoch_div_weight = getattr(w, "stoch_rsi_divergence", 0)
            if "stoch_rsi_k" in recent.columns and pd.notna(cur.get("stoch_rsi_k")):
                if prior_swings and price_is_new_high:
                    prev_swing_idx = prior_swings[-1]
                    # Bearish divergence: price higher, stoch RSI lower
                    if (
                        pd.notna(recent["stoch_rsi_k"].iloc[prev_swing_idx])
                        and recent["stoch_rsi_k"].iloc[cur_idx] < recent["stoch_rsi_k"].iloc[prev_swing_idx]
                    ):
                        score += stoch_div_weight
                        details.append(
                            f"Stoch RSI 背離：{recent['stoch_rsi_k'].iloc[cur_idx]:.1f} < "
                            f"前高 {recent['stoch_rsi_k'].iloc[prev_swing_idx]:.1f}"
                        )

        # ── 3. Volume expanding (chasing tops) ──────────────────────────
        vol_weight = getattr(w, "volume_decline", 0)
        if "volume_ma" in recent.columns and len(recent) >= 15:
            recent_vol_ma = recent["volume_ma"].iloc[-5:].mean()
            prior_vol_ma = recent["volume_ma"].iloc[-15:-5].mean()
            if prior_vol_ma > 0 and recent_vol_ma > prior_vol_ma:
                score += vol_weight
                ratio = recent_vol_ma / prior_vol_ma
                details.append(f"成交量放大（近期/前期 = {ratio:.2f}）")

        # ── 4. RSI overbought ────────────────────────────────────────────
        overbought_weight = getattr(w, "oversold", 0)  # reuse same weight key
        if pd.notna(cur.get("rsi")) and cur["rsi"] > self._cfg.rsi_overbought:
            score += overbought_weight
            details.append(f"RSI {cur['rsi']:.1f} > {self._cfg.rsi_overbought}（超買）")

        # ── 5. OBV confirmation (look for OBV divergence too) ────────────
        obv_weight = getattr(w, "obv_confirm", 0)
        if "obv" in recent.columns and len(recent) >= 5:
            recent_obv_trend = recent["obv"].iloc[-1] - recent["obv"].iloc[-5]
            if recent_obv_trend < 0:  # OBV falling while price rising = bearish
                score += obv_weight
                details.append("OBV 下降（量能背離）")

        # Key levels
        cur_close = float(cur.get("close") or 0)
        cur_high = float(cur.get("high") or 0)
        atr = float(cur.get("atr") or 0)
        key_levels: dict = {}
        if cur_high > 0:
            # Entry: current close
            key_levels["entry"] = round(cur_close, 6)
            # Stop: slightly above swing high (0.5 ATR buffer)
            key_levels["stop"] = round(cur_high + 0.5 * atr, 6)
            # Resistance: swing high level
            key_levels["resistance"] = round(cur_high, 6)
            # Target: recent swing low
            key_levels["target"] = round(float(recent["low"].min()), 6)

        return StrategyResult(self.name, score, max_score, details, direction="short", key_levels=key_levels)
