"""Market filter — select tradable symbols by volume, rank, and listing age."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.config import ExchangeConfig

logger = logging.getLogger(__name__)


def filter_symbols(
    exchange_info: list[dict[str, Any]],
    tickers: list[dict[str, Any]],
    config: ExchangeConfig,
) -> list[str]:
    """Return a list of symbol names that pass all filter criteria.

    Criteria (from config):
      - 24h quote volume ≥ min_volume_24h
      - Rank within top max_symbols by quote volume
      - Listed for at least min_listing_days
    """
    # Build a set of valid perpetual symbols from exchange info
    info_map: dict[str, dict[str, Any]] = {
        s["symbol"]: s for s in exchange_info
    }

    # Map symbol → 24h quote volume from tickers
    volume_map: dict[str, float] = {}
    for t in tickers:
        sym = t["symbol"]
        if sym in info_map:
            volume_map[sym] = float(t.get("quoteVolume", 0))

    now = datetime.now(tz=timezone.utc)
    min_days = config.min_listing_days

    candidates: list[tuple[str, float]] = []
    for sym, vol in volume_map.items():
        # Volume filter
        if vol < config.min_volume_24h:
            continue

        # Listing age filter
        info = info_map[sym]
        onboard_ts = info.get("onboardDate")
        if onboard_ts:
            onboard = datetime.fromtimestamp(onboard_ts / 1000, tz=timezone.utc)
            if (now - onboard).days < min_days:
                logger.debug("Skipping %s: listed only %d days", sym, (now - onboard).days)
                continue

        candidates.append((sym, vol))

    # Sort by volume descending, take top N
    candidates.sort(key=lambda x: x[1], reverse=True)
    result = [sym for sym, _ in candidates[: config.max_symbols]]

    logger.info(
        "Market filter: %d symbols passed (from %d total)",
        len(result),
        len(volume_map),
    )
    return result
