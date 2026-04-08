"""Main entry point for the crypto scanner.

Continuously monitors configured trading pairs on Binance futures, runs
strategy checks every 15 minutes, and sends Telegram notifications for signals.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import AppConfig, load_config
from src.data.fetcher import BinanceFetcher
from src.data.market_filter import filter_symbols
from src.indicators.technical import enrich_dataframe
from src.notifier import TelegramNotifier
from src.scheduler import create_scheduler
from src.state_manager import StateManager
from src.strategies.base import BaseStrategy, StrategyResult
from src.strategies.breakout import BreakoutStrategy
from src.strategies.breakout_short import BearishBreakoutStrategy
from src.strategies.divergence import DivergenceStrategy
from src.strategies.divergence_short import BearishDivergenceStrategy
from src.strategies.trend import TrendStrategy
from src.strategies.trend_short import BearishTrendStrategy

logger = logging.getLogger("crypto_scanner")

_TST = ZoneInfo("Asia/Taipei")


# ── Setup ──────────────────────────────────────────────────────────────────────

def _setup_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


def _build_strategies(config: AppConfig) -> list[BaseStrategy]:
    """Instantiate enabled strategies."""
    strategies: list[BaseStrategy] = []
    sc = config.strategies

    if sc.trend.enabled:
        strategies.append(TrendStrategy(sc.trend))
    if sc.trend.short_enabled:
        strategies.append(BearishTrendStrategy(sc.trend))
    if sc.divergence.enabled:
        strategies.append(DivergenceStrategy(sc.divergence))
    if sc.divergence.short_enabled:
        strategies.append(BearishDivergenceStrategy(sc.divergence))
    if sc.breakout.enabled:
        strategies.append(BreakoutStrategy(sc.breakout))
    if sc.breakout.short_enabled:
        strategies.append(BearishBreakoutStrategy(sc.breakout))

    logger.info("Enabled strategies: %s", [s.name for s in strategies])
    return strategies


def _get_threshold(config: AppConfig, strategy: BaseStrategy) -> int:
    """Look up the score threshold for a strategy from config."""
    sc = config.strategies
    name_map = {
        "趨勢啟動型":    sc.trend.score_threshold,
        "趨勢啟動型(空)": sc.trend.score_threshold,
        "背離反轉型":    sc.divergence.score_threshold,
        "背離反轉型(空)": sc.divergence.score_threshold,
        "爆量突破型":    sc.breakout.score_threshold,
        "爆量突破型(空)": sc.breakout.score_threshold,
    }
    return name_map.get(strategy.name, 6)


# ── Core Scan Loop ─────────────────────────────────────────────────────────────

async def run_scan(
    config: AppConfig,
    fetcher: BinanceFetcher,
    strategies: list[BaseStrategy],
    state: StateManager,
    notifier: TelegramNotifier,
    activity: dict,
) -> None:
    """Execute one full scan cycle and send a consolidated notification if needed.

    Parameters
    ----------
    activity:
        Shared in-memory counter dict with keys ``new`` and ``invalidated``,
        reset by the scheduled status report after each fixed-time window.
    """
    logger.info("═══ Scan cycle started ═══")

    try:
        # 1. Get and filter symbol list
        exchange_info = await fetcher.get_exchange_info()
        tickers = await fetcher.get_ticker_24h()
        symbols = filter_symbols(exchange_info, tickers, config.exchange)

        if not symbols:
            logger.warning("No symbols passed filter, skipping cycle")
            return

        # 2. Group strategies by timeframe to minimise API calls
        tf_strategies: dict[str, list[BaseStrategy]] = {}
        for strat in strategies:
            tf_strategies.setdefault(strat.timeframe, []).append(strat)

        # 3. Collect ALL results from this scan
        # Key: (symbol, strategy_name) → (result, threshold)
        scan_results: dict[tuple[str, str], tuple[StrategyResult, int]] = {}

        for tf, strats in tf_strategies.items():
            logger.info("Fetching %s klines for %d symbols…", tf, len(symbols))
            kline_map = await fetcher.fetch_klines_batch(symbols, tf)

            for symbol, df in kline_map.items():
                enriched = enrich_dataframe(
                    df,
                    ema_fast=config.strategies.trend.ema_fast,
                    ema_slow=config.strategies.trend.ema_slow,
                )
                for strat in strats:
                    result = strat.evaluate(enriched)
                    threshold = _get_threshold(config, strat)
                    scan_results[(symbol, strat.name)] = (result, threshold)

        # 4. Categorise results into three buckets
        new_discoveries: list[tuple[str, StrategyResult]] = []
        invalidated: list[dict] = []
        still_valid: list[dict] = []

        for (symbol, strategy_name), (result, threshold) in scan_results.items():
            if result.score >= threshold:
                if state.should_notify(symbol, strategy_name, result.score):
                    # Scenario A / D / E — new discovery
                    new_discoveries.append((symbol, result))
                    state.record(symbol, strategy_name, result.score)
                    activity["new"] += 1
                    logger.info(
                        "🆕 %s %s (score %d/%d)",
                        symbol, strategy_name, result.score, result.max_score,
                    )
                elif state.is_active(symbol, strategy_name):
                    # Scenario C — still valid, within cooldown
                    still_valid.append({
                        "symbol": symbol,
                        "strategy": strategy_name,
                        "last_score": state.get_last_score(symbol, strategy_name),
                    })
            else:
                if state.is_active(symbol, strategy_name):
                    # Scenario F — signal invalidated
                    old_score = state.get_last_score(symbol, strategy_name) or 0
                    invalidated.append({
                        "symbol": symbol,
                        "strategy": strategy_name,
                        "old_score": old_score,
                        "new_score": result.score,
                    })
                    state.invalidate(symbol, strategy_name)
                    activity["invalidated"] += 1
                    logger.info("❌ %s %s invalidated (%d→%d)", symbol, strategy_name, old_score, result.score)

        # 5. Send consolidated notification only if something changed
        if invalidated or new_discoveries:
            await notifier.send_scan_report(invalidated, still_valid, new_discoveries)

    except Exception:
        logger.exception("Scan cycle failed")
        try:
            await notifier.send_error("Scan cycle encountered an error — check logs")
        except Exception:
            logger.exception("Failed to send error notification")

    logger.info("═══ Scan cycle finished ═══")


# ── Entry Point ────────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()
    _setup_logging(config.logging.level)

    logger.info("Crypto Scanner starting…")

    strategies = _build_strategies(config)
    state = StateManager(config.notification)
    notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)

    # Shared activity counter — tracks events since last status report
    activity: dict = {"new": 0, "invalidated": 0}

    # Continuous scheduler mode
    async def _run() -> None:
        async with BinanceFetcher(config.exchange) as fetcher:
            # Send startup message
            await notifier.send_startup_message()

            # Run one scan immediately on startup
            await run_scan(config, fetcher, strategies, state, notifier, activity)

            async def _scan_job() -> None:
                await run_scan(config, fetcher, strategies, state, notifier, activity)

            async def _status_job() -> None:
                hour = datetime.now(tz=_TST).hour
                active = state.get_active_signals()
                new_count = activity["new"]
                inv_count = activity["invalidated"]
                await notifier.send_status_report(
                    hour=hour,
                    new_count=new_count,
                    invalidated_count=inv_count,
                    active_signals=active,
                )
                activity["new"] = 0
                activity["invalidated"] = 0
                logger.info(
                    "📊 Status report sent (%02d:00 TST): %d active, "
                    "+%d new, -%d invalidated",
                    hour, len(active), new_count, inv_count,
                )

            scheduler = create_scheduler(
                config,
                scan_func=_scan_job,
                status_func=_status_job,
            )
            scheduler.start()

            logger.info("Scanner running. Press Ctrl+C to stop.")
            try:
                while True:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                scheduler.shutdown()
                logger.info("Scanner stopped.")

    asyncio.run(_run())


if __name__ == "__main__":
    main()

