"""策略一：趨勢啟動型（Trend Initiation Model）

Timeframe: 4H

Conditions:
  1. EMA20 上穿 EMA50（Golden Cross — current bar above, previous below）
  2. MACD Histogram 由負轉正
  3. RSI > threshold
  4. Volume > multiplier × Volume MA
"""

from __future__ import annotations

import pandas as pd

from src.config import TrendConfig
from src.strategies.base import BaseStrategy, StrategyResult


class TrendStrategy(BaseStrategy):
    """Detect nascent trend initiation via EMA cross + momentum confirmation."""

    def __init__(self, config: TrendConfig) -> None:
        self._cfg = config

    @property
    def name(self) -> str:
        return "趨勢啟動型"

    @property
    def timeframe(self) -> str:
        return self._cfg.timeframe

    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        w = self._cfg.weights
        score = 0
        details: list[str] = []
        max_score = int(w.total())

        if len(df) < 2:
            return StrategyResult(self.name, 0, max_score)

        cur = df.iloc[-1]
        prev = df.iloc[-2]

        # 1. EMA Golden Cross: current EMA_fast > EMA_slow AND previous was <=
        ema_cross_weight = getattr(w, "ema_cross", 0)
        if (
            pd.notna(cur.get("ema_fast"))
            and pd.notna(cur.get("ema_slow"))
            and pd.notna(prev.get("ema_fast"))
            and pd.notna(prev.get("ema_slow"))
        ):
            if cur["ema_fast"] > cur["ema_slow"] and prev["ema_fast"] <= prev["ema_slow"]:
                score += ema_cross_weight
                details.append(
                    f"EMA{self._cfg.ema_fast} ↑穿 EMA{self._cfg.ema_slow}"
                )

        # 2. MACD Histogram cross zero (negative → positive)
        macd_cross_weight = getattr(w, "macd_cross", 0)
        if pd.notna(cur.get("macd_hist")) and pd.notna(prev.get("macd_hist")):
            if cur["macd_hist"] > 0 and prev["macd_hist"] <= 0:
                score += macd_cross_weight
                details.append("MACD 金叉（Histogram 由負轉正）")

        # 3. RSI above threshold
        rsi_weight = getattr(w, "rsi_above", 0)
        if pd.notna(cur.get("rsi")) and cur["rsi"] > self._cfg.rsi_threshold:
            score += rsi_weight
            details.append(f"RSI {cur['rsi']:.1f} > {self._cfg.rsi_threshold}")

        # 4. Volume surge
        vol_weight = getattr(w, "volume_surge", 0)
        if pd.notna(cur.get("volume")) and pd.notna(cur.get("volume_ma")):
            ratio = cur["volume"] / cur["volume_ma"] if cur["volume_ma"] > 0 else 0
            if ratio > self._cfg.volume_multiplier:
                score += vol_weight
                details.append(f"Volume {ratio:.1f}x（>{self._cfg.volume_multiplier}x）")

        # 5. ADX strong trend
        adx_weight = getattr(w, "adx_strong", 0)
        if pd.notna(cur.get("adx")) and cur["adx"] > self._cfg.adx_threshold:
            score += adx_weight
            details.append(f"ADX {cur['adx']:.1f} > {self._cfg.adx_threshold}（強趨勢）")

        # 6. OBV confirmation (rising OBV confirms uptrend)
        obv_weight = getattr(w, "obv_confirm", 0)
        if pd.notna(cur.get("obv")) and pd.notna(prev.get("obv")):
            if cur["obv"] > prev["obv"]:
                score += obv_weight
                details.append("OBV 上升（量能確認）")

        # Key levels
        cur_close = float(cur.get("close") or 0)
        ema_s = float(cur.get("ema_slow") or 0)
        atr = float(cur.get("atr") or 0)
        key_levels: dict = {}
        if cur_close > 0 and atr > 0:
            # Entry: current close or slightly better (pullback entry)
            key_levels["entry"] = round(cur_close, 6)
            # Stop: below slow EMA or 1.5 ATR below entry
            stop = ema_s if ema_s > 0 else round(cur_close - 1.5 * atr, 6)
            key_levels["stop"] = round(stop, 6)
            # Target: 3 ATR above entry (1:2 risk-reward)
            key_levels["target"] = round(cur_close + 3 * atr, 6)
        if ema_s > 0:
            key_levels["support"] = round(ema_s, 6)

        return StrategyResult(self.name, score, max_score, details, direction="long", key_levels=key_levels)
