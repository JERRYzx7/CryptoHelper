"""Binance Futures API data fetcher — async with rate limiting and retry."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import pandas as pd

from src.config import ExchangeConfig

logger = logging.getLogger(__name__)

# Column names for the OHLCV DataFrame returned by the fetcher.
OHLCV_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
]


class BinanceFetcher:
    """Async Binance Futures data fetcher with concurrency & retry control.

    Usage::

        async with BinanceFetcher(exchange_cfg) as fetcher:
            symbols = await fetcher.get_tradable_symbols()
            df = await fetcher.fetch_klines("BTCUSDT", "4h")
    """

    def __init__(self, config: ExchangeConfig) -> None:
        self._cfg = config
        self._base = config.base_url
        self._sem = asyncio.Semaphore(config.max_concurrent_requests)
        self._session: aiohttp.ClientSession | None = None

    # ── Context manager ────────────────────────────────────────────────────

    async def __aenter__(self) -> "BinanceFetcher":
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    # ── Public API ─────────────────────────────────────────────────────────

    async def get_exchange_info(self) -> list[dict[str, Any]]:
        """Return all perpetual USDT symbol info dicts."""
        data = await self._get("/fapi/v1/exchangeInfo")
        return [
            s
            for s in data.get("symbols", [])
            if s.get("contractType") == "PERPETUAL"
            and s.get("quoteAsset") == "USDT"
            and s.get("status") == "TRADING"
        ]

    async def get_ticker_24h(self) -> list[dict[str, Any]]:
        """Return 24h ticker data for all symbols."""
        return await self._get("/fapi/v1/ticker/24hr")

    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV klines for *symbol* and return as a DataFrame.

        The DataFrame has columns: open_time, open, high, low, close, volume,
        close_time, quote_volume, trades, taker_buy_volume,
        taker_buy_quote_volume. All price / volume columns are float64.
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit or self._cfg.kline_limit,
        }
        raw: list[list] = await self._get("/fapi/v1/klines", params=params)
        df = pd.DataFrame(raw, columns=OHLCV_COLUMNS)
        # Drop the useless last column
        df.drop(columns=["ignore"], inplace=True)
        # Cast numeric columns
        for col in ["open", "high", "low", "close", "volume", "quote_volume",
                     "taker_buy_volume", "taker_buy_quote_volume"]:
            df[col] = df[col].astype(float)
        df["trades"] = df["trades"].astype(int)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        return df

    async def fetch_klines_batch(
        self,
        symbols: list[str],
        interval: str,
        limit: int | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Fetch klines for multiple symbols concurrently.

        Returns a dict mapping symbol → DataFrame. Symbols that fail after
        all retries are silently omitted with a warning log.
        """
        async def _fetch_one(sym: str) -> tuple[str, pd.DataFrame | None]:
            try:
                df = await self.fetch_klines(sym, interval, limit)
                return sym, df
            except Exception:
                logger.warning("Failed to fetch %s %s, skipping", sym, interval)
                return sym, None

        results = await asyncio.gather(*[_fetch_one(s) for s in symbols])
        return {sym: df for sym, df in results if df is not None}

    # ── Internal ───────────────────────────────────────────────────────────

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        _retries: int = 3,
    ) -> Any:
        """GET with semaphore-based concurrency control + exponential backoff."""
        assert self._session is not None, "Use `async with BinanceFetcher(...):`"
        url = f"{self._base}{path}"

        for attempt in range(1, _retries + 1):
            async with self._sem:
                try:
                    async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 429:
                            wait = 2 ** attempt
                            logger.warning("Rate limited, waiting %ds…", wait)
                            await asyncio.sleep(wait)
                            continue
                        resp.raise_for_status()
                        return await resp.json()
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    if attempt == _retries:
                        logger.error("Request failed after %d attempts: %s %s", _retries, url, exc)
                        raise
                    wait = 2 ** attempt
                    logger.warning("Attempt %d/%d failed, retrying in %ds…", attempt, _retries, wait)
                    await asyncio.sleep(wait)

        raise RuntimeError(f"Unreachable: {url}")  # pragma: no cover
