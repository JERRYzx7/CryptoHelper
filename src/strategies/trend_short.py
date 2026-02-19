"""策略一（空）：趨勢反轉型-空頭（Bearish Trend Model）

Timeframe: 4H  (reuses TrendConfig)

Conditions:
  1. EMA20 下穿 EMA50（Death Cross）
  2. MACD Histogram 由正轉負（Dead Cross）
  3. RSI < rsi_threshold
  4. Volume > multiplier × Volume MA
"""

from __future__ import annotations

import pandas as pd

from src.config import TrendConfig
from src.strategies.base import BaseStrategy, StrategyResult


class BearishTrendStrategy(BaseStrategy):
    """Detect downtrend initiation via EMA death cross + momentum confirmation."""

    def __init__(self, config: TrendConfig) -> None:
        self._cfg = config

    @property
    def name(self) -> str:
        return "趨勢啟動型(空)"

    @property
    def timeframe(self) -> str:
        return self._cfg.timeframe

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        w = self._cfg.weights
        score = 0
        details: list[str] = []
        max_score = int(w.total())

        if len(df) < 2:
            return StrategyResult(self.name, 0, max_score, direction="short")

        cur = df.iloc[-1]
        prev = df.iloc[-2]

        # 1. EMA Death Cross: cur fast < slow AND prev fast >= slow
        ema_cross_weight = getattr(w, "ema_cross", 0)
        if (
            pd.notna(cur.get("ema_fast"))
            and pd.notna(cur.get("ema_slow"))
            and pd.notna(prev.get("ema_fast"))
            and pd.notna(prev.get("ema_slow"))
        ):
            if cur["ema_fast"] < cur["ema_slow"] and prev["ema_fast"] >= prev["ema_slow"]:
                score += ema_cross_weight
                details.append(f"EMA{self._cfg.ema_fast} ↓穿 EMA{self._cfg.ema_slow}（死叉）")

        # 2. MACD Histogram cross zero (positive → negative)
        macd_cross_weight = getattr(w, "macd_cross", 0)
        if pd.notna(cur.get("macd_hist")) and pd.notna(prev.get("macd_hist")):
            if cur["macd_hist"] < 0 and prev["macd_hist"] >= 0:
                score += macd_cross_weight
                details.append("MACD 死叉（Histogram 由正轉負）")

        # 3. RSI below threshold
        rsi_weight = getattr(w, "rsi_above", 0)
        if pd.notna(cur.get("rsi")) and cur["rsi"] < self._cfg.rsi_threshold:
            score += rsi_weight
            details.append(f"RSI {cur['rsi']:.1f} < {self._cfg.rsi_threshold}")

        # 4. Volume surge
        vol_weight = getattr(w, "volume_surge", 0)
        if pd.notna(cur.get("volume")) and pd.notna(cur.get("volume_ma")):
            ratio = cur["volume"] / cur["volume_ma"] if cur["volume_ma"] > 0 else 0
            if ratio > self._cfg.volume_multiplier:
                score += vol_weight
                details.append(f"Volume {ratio:.1f}x（>{self._cfg.volume_multiplier}x）")

        # Key levels
        cur_close = float(cur.get("close") or 0)
        ema_s = float(cur.get("ema_slow") or 0)
        atr = float(cur.get("atr") or 0)
        key_levels: dict = {}
        if cur_close > 0 and atr > 0:
            stop = ema_s if ema_s > 0 else round(cur_close + 1.5 * atr, 6)
            key_levels["stop"] = round(stop, 6)
            key_levels["target"] = round(cur_close - 3 * atr, 6)
        if ema_s > 0:
            key_levels["resistance"] = round(ema_s, 6)

        return StrategyResult(self.name, score, max_score, details, direction="short", key_levels=key_levels)
