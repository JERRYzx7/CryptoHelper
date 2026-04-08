"""策略三：爆量突破型（Volume Breakout Model）

Timeframe: 1H

Conditions:
  1. 最近 consolidation_bars 根 K 線屬於盤整區間
     盤整定義：(highest_high - lowest_low) / lowest_low ≤ range_threshold_pct%
  2. 當前收盤價突破盤整區間高點
  3. 成交量 > volume_multiplier × Volume MA
  4. ATR 擴張（current ATR > ATR 20-period MA）
"""

from __future__ import annotations

import pandas as pd

from src.config import BreakoutConfig
from src.strategies.base import BaseStrategy, StrategyResult


class BreakoutStrategy(BaseStrategy):
    """Detect volume-driven breakouts from consolidation ranges."""

    def __init__(self, config: BreakoutConfig) -> None:
        self._cfg = config

    @property
    def name(self) -> str:
        return "爆量突破型"

    @property
    def timeframe(self) -> str:
        return self._cfg.timeframe

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        w = self._cfg.weights
        score = 0
        details: list[str] = []
        max_score = int(w.total())
        bars = self._cfg.consolidation_bars

        if len(df) < bars + 1:
            return StrategyResult(self.name, 0, max_score)

        # The consolidation zone is the *bars* candles BEFORE the current one
        consol = df.iloc[-(bars + 1):-1]
        cur = df.iloc[-1]

        consol_high = consol["high"].max()
        consol_low = consol["low"].min()
        range_pct = ((consol_high - consol_low) / consol_low * 100) if consol_low > 0 else float("inf")

        # ── 1. Consolidation ─────────────────────────────────────────────
        consol_weight = getattr(w, "consolidation", 0)
        is_consolidated = range_pct <= self._cfg.range_threshold_pct
        if is_consolidated:
            score += consol_weight
            details.append(f"盤整區間 {range_pct:.1f}%（≤{self._cfg.range_threshold_pct}%）")

        # ── 2. Breakout ──────────────────────────────────────────────────
        breakout_weight = getattr(w, "breakout", 0)
        if is_consolidated and pd.notna(cur.get("close")) and cur["close"] > consol_high:
            score += breakout_weight
            details.append(
                f"收盤 {cur['close']:.4f} 突破區間高點 {consol_high:.4f}"
            )

        # ── 3. Volume surge ──────────────────────────────────────────────
        vol_weight = getattr(w, "volume_surge", 0)
        if pd.notna(cur.get("volume")) and pd.notna(cur.get("volume_ma")):
            ratio = cur["volume"] / cur["volume_ma"] if cur["volume_ma"] > 0 else 0
            if ratio > self._cfg.volume_multiplier:
                score += vol_weight
                details.append(f"Volume {ratio:.1f}x（>{self._cfg.volume_multiplier}x）")

        # ── 4. ATR expansion ─────────────────────────────────────────────
        atr_weight = getattr(w, "atr_expansion", 0)
        if "atr" in df.columns and pd.notna(cur.get("atr")):
            atr_ma = df["atr"].iloc[-20:].mean() if len(df) >= 20 else df["atr"].mean()
            if cur["atr"] > atr_ma:
                score += atr_weight
                details.append(
                    f"ATR 擴張 {cur['atr']:.4f} > MA {atr_ma:.4f}"
                )

        # ── 5. Bollinger Bands breakout (price above upper band) ─────────
        bb_weight = getattr(w, "bb_breakout", 0)
        if pd.notna(cur.get("close")) and pd.notna(cur.get("bb_upper")):
            if cur["close"] > cur["bb_upper"]:
                score += bb_weight
                details.append(f"突破 BB 上軌 {cur['bb_upper']:.4f}")

        # ── 6. OBV confirmation (rising OBV on breakout) ─────────────────
        obv_weight = getattr(w, "obv_confirm", 0)
        if pd.notna(cur.get("obv")) and len(df) >= 5:
            obv_trend = df["obv"].iloc[-1] - df["obv"].iloc[-5]
            if obv_trend > 0:
                score += obv_weight
                details.append("OBV 上升（突破有量）")

        # Key levels (breakout: measured move target)
        cur_close = float(cur.get("close") or 0)
        key_levels: dict = {}
        if is_consolidated and consol_low > 0:
            range_size = consol_high - consol_low
            # Entry: current close (just broke out)
            key_levels["entry"] = round(cur_close, 6)
            # Stop: below consolidation low
            key_levels["stop"] = round(consol_low, 6)
            # Support: old resistance becomes new support
            key_levels["support"] = round(consol_high, 6)
            # Target: measured move (range height projected up)
            key_levels["target"] = round(consol_high + range_size, 6)

        return StrategyResult(self.name, score, max_score, details, direction="long", key_levels=key_levels)
