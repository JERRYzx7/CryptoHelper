"""Telegram notification sender with message formatting and retry."""

from __future__ import annotations

import html
import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from telegram import Bot
from telegram.constants import ParseMode

if TYPE_CHECKING:
    from src.strategies.base import StrategyResult

logger = logging.getLogger(__name__)

# TradingView link template
_TV_URL = "https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}.P"

# Known indicator keywords for signal strength calculation
_INDICATOR_KEYWORDS = [
    "EMA", "SMA", "MACD", "RSI", "ADX", "OBV", "VWAP",
    "布林", "Bollinger", "成交量", "Volume", "量能",
    "ATR", "Stochastic", "KD", "CCI", "MFI",
]


def _fmt_price(v: float) -> str:
    """Format a price value with appropriate decimal places."""
    if v >= 1000:
        return f"{v:.2f}"
    elif v >= 1:
        return f"{v:.4f}"
    else:
        return f"{v:.6f}"


def _count_unique_indicators(details: list[str]) -> int:
    """Count unique indicator confirmations from detail strings."""
    found = set()
    for detail in details:
        detail_upper = detail.upper()
        for kw in _INDICATOR_KEYWORDS:
            if kw.upper() in detail_upper:
                found.add(kw.upper())
    return len(found) if found else len(details)


def _get_signal_strength(indicator_count: int) -> str:
    """Get signal strength label based on indicator count."""
    if indicator_count >= 4:
        return f"🔥 強（{indicator_count} 指標共識）"
    elif indicator_count >= 2:
        return f"⚡ 中等（{indicator_count} 指標共識）"
    else:
        return f"⚠️ 弱（{indicator_count} 指標共識）"


def _deduplicate_details(details: list[str]) -> list[str]:
    """Deduplicate similar detail entries while preserving order."""
    seen = set()
    result = []
    for d in details:
        normalized = d.strip().lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(d)
    return result


# ── Pure formatting functions (testable without network) ───────────────────────


def format_aggregated_signal(
    symbol: str,
    results: list["StrategyResult"],
) -> str:
    """Format aggregated signal for a symbol with direction and strength.

    Parameters
    ----------
    symbol:
        Trading pair symbol (e.g., "SOLUSDT").
    results:
        All triggered strategies for this symbol.

    Returns
    -------
    Formatted message string with direction, strength, and details.
    """
    lines: list[str] = []

    # Header
    lines.append(f"📊 <b>{symbol}</b> ══════════════")
    lines.append("")

    # Determine direction based on strategy names
    long_strategies = []
    short_strategies = []
    for r in results:
        if "(空)" in r.strategy_name or r.direction == "short":
            short_strategies.append(r)
        else:
            long_strategies.append(r)

    if long_strategies and not short_strategies:
        direction_line = "🟢 建議：做多"
    elif short_strategies and not long_strategies:
        direction_line = "🔴 建議：做空"
    else:
        direction_line = "⚪ 觀望（多空分歧）"

    lines.append(direction_line)

    # Aggregate all details and calculate signal strength
    all_details: list[str] = []
    for r in results:
        all_details.extend(r.details)
    unique_details = _deduplicate_details(all_details)
    indicator_count = _count_unique_indicators(unique_details)
    strength_line = f"📈 信號強度：{_get_signal_strength(indicator_count)}"
    lines.append(strength_line)
    lines.append("")

    # Triggered strategies section
    lines.append("【觸發策略】")
    for r in results:
        lines.append(f"• {html.escape(r.strategy_name)} {r.score}/{r.max_score}")
    lines.append("")

    # Signal details section (long or short based on majority)
    if long_strategies and not short_strategies:
        lines.append("【多頭訊號】")
    elif short_strategies and not long_strategies:
        lines.append("【空頭訊號】")
    else:
        lines.append("【訊號詳情】")

    for detail in unique_details:
        lines.append(f"  ✓ {html.escape(detail)}")
    lines.append("")

    # Key levels from first result that has them
    key_levels = None
    for r in results:
        if r.key_levels:
            key_levels = r.key_levels
            break

    if key_levels:
        lines.append("【建議價位】")
        if "entry" in key_levels:
            lines.append(f"  💰 入場：${_fmt_price(key_levels['entry'])}")
        if "stop" in key_levels:
            lines.append(f"  🛑 止損：${_fmt_price(key_levels['stop'])}")
        if "target" in key_levels:
            lines.append(f"  🎯 目標：${_fmt_price(key_levels['target'])}")
        
        # Calculate risk-reward ratio if entry and stop exist
        if "entry" in key_levels and "stop" in key_levels and "target" in key_levels:
            entry_price = key_levels["entry"]
            stop_price = key_levels["stop"]
            target_price = key_levels["target"]
            risk = abs(entry_price - stop_price)
            reward = abs(target_price - entry_price)
            if risk > 0:
                rr_ratio = reward / risk
                lines.append(f"  📊 風報比：1:{rr_ratio:.1f}")
        
        lines.append("")
        lines.append("【關鍵價位】")
        if "support" in key_levels:
            lines.append(f"  支撐：${_fmt_price(key_levels['support'])}")
        if "resistance" in key_levels:
            lines.append(f"  壓力：${_fmt_price(key_levels['resistance'])}")
        lines.append("")

    # TradingView link
    tv_url = _TV_URL.format(symbol=symbol)
    lines.append(f'<a href="{tv_url}">📈 TradingView</a>')
    lines.append("══════════════════════════")

    return "\n".join(lines)

def format_scan_report(
    invalidated: list[dict],
    still_valid: list[dict],
    new_discoveries: list[tuple[str, "StrategyResult"]],
) -> str:
    """Build the three-section scan event message.

    Parameters
    ----------
    invalidated:
        List of dicts with keys: symbol, strategy, old_score, new_score.
    still_valid:
        List of dicts with keys: symbol, strategy, last_score.
        These are active signals within cooldown (shown for context).
    new_discoveries:
        List of (symbol, StrategyResult) for newly triggered or improved signals.
    """
    lines: list[str] = []

    # ── Section 1: Invalidated ────────────────────────────────────────────
    if invalidated:
        lines.append("❌ <b>訊號已失效</b>")
        for item in invalidated:
            lines.append(
                f"  {item['symbol']} {item['strategy']} "
                f"({item['old_score']} → {item['new_score']})"
            )
        lines.append("")

    # ── Section 2: Still valid (context only) ────────────────────────────
    if still_valid:
        lines.append(f"♻️ <b>持續有效（共 {len(still_valid)} 個）</b>")
        for item in still_valid:
            lines.append(
                f"  {item['symbol']} {item['strategy']} Score {item['last_score']}"
            )
        lines.append("")

    # ── Section 3: New discoveries ────────────────────────────────────────
    if new_discoveries:
        lines.append("🆕 <b>新發現</b>")
        for symbol, result in new_discoveries:
            dir_emoji = "📈" if result.direction == "long" else "📉"
            dir_label = "做多" if result.direction == "long" else "做空"
            lines.append(f"")
            lines.append(f"  <b>{symbol}</b>  {dir_emoji} {dir_label}")
            lines.append(f"  【{result.strategy_name}】Score {result.score}/{result.max_score}")
            for detail in result.details:
                lines.append(f"    ✓ {html.escape(detail)}")
            kl = result.key_levels
            if kl:
                parts = []
                if "stop" in kl:
                    parts.append(f"止損 {_fmt_price(kl['stop'])}")
                if "target" in kl:
                    parts.append(f"目標 {_fmt_price(kl['target'])}")
                if parts:
                    lines.append(f"  🎯 {' ｜ '.join(parts)}")
                if "support" in kl:
                    lines.append(f"  📌 支撐 {_fmt_price(kl['support'])}")
                if "resistance" in kl:
                    lines.append(f"  📌 壓力 {_fmt_price(kl['resistance'])}")
            tv_url = _TV_URL.format(symbol=symbol)
            lines.append(f'  <a href="{tv_url}">📈 TradingView</a>')

    return "\n".join(lines).strip()


def format_status_report(
    hour: int,
    new_count: int,
    invalidated_count: int,
    active_signals: list[dict],
) -> str:
    """Build the fixed-schedule status report message.

    Parameters
    ----------
    hour:
        Scheduled hour (TST, 0-23) — shown as HH:00 in the message.
    new_count:
        Number of new discoveries since last status report.
    invalidated_count:
        Number of invalidations since last status report.
    active_signals:
        All currently active signals from StateManager.get_active_signals().
    """
    time_str = f"{hour:02d}:00"
    active_count = len(active_signals)

    lines = [
        f"📊 <b>定時回報（{time_str} TST）</b>",
        f"過去 4h：🆕 {new_count} 個新發現 ｜ ❌ {invalidated_count} 個失效",
        f"♻️ 目前持續有效：{active_count} 個",
    ]
    return "\n".join(lines)


def format_signal_message(
    symbol: str,
    results: list["StrategyResult"],
) -> str:
    """Legacy per-symbol signal formatter — kept for backward compatibility."""
    lines: list[str] = [f"📊 <b>{symbol}</b>", ""]

    for r in results:
        lines.append(f"<b>【{r.strategy_name}】</b>")
        lines.append(f"Score: {r.score}/{r.max_score}")
        lines.append("")
        for d in r.details:
            lines.append(f"  ✓ {html.escape(d)}")
        lines.append("")

    tv_url = _TV_URL.format(symbol=symbol)
    lines.append(f'<a href="{tv_url}">📈 TradingView</a>')
    return "\n".join(lines)


# ── TelegramNotifier ───────────────────────────────────────────────────────────

class TelegramNotifier:
    """Send formatted signals to a Telegram chat."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot = Bot(token=bot_token) if bot_token else None
        self._chat_id = chat_id

    async def send_scan_report(
        self,
        invalidated: list[dict],
        still_valid: list[dict],
        new_discoveries: list[tuple[str, "StrategyResult"]],
    ) -> None:
        """Send scan event notifications with new aggregated format for discoveries.

        For new discoveries, groups by symbol and sends individual messages
        using the new aggregated signal format with direction recommendations
        and signal strength.
        """
        if not self._bot:
            logger.warning("Telegram bot not configured, skipping scan report")
            return

        # Send status sections (invalidated + still valid) if any
        status_text = format_scan_report(invalidated, still_valid, [])
        if status_text:
            await self._send(status_text)

        # Group new discoveries by symbol and send aggregated messages
        if new_discoveries:
            grouped: dict[str, list["StrategyResult"]] = defaultdict(list)
            for symbol, result in new_discoveries:
                grouped[symbol].append(result)

            for symbol, results in grouped.items():
                aggregated_text = format_aggregated_signal(symbol, results)
                await self._send(aggregated_text)

    async def send_status_report(
        self,
        hour: int,
        new_count: int,
        invalidated_count: int,
        active_signals: list[dict],
    ) -> None:
        """Send the fixed-schedule status report."""
        if not self._bot:
            return
        text = format_status_report(hour, new_count, invalidated_count, active_signals)
        await self._send(text)

    async def send_startup_message(self) -> None:
        """Send a welcome/startup message."""
        if not self._bot:
            return
        text = "🚀 <b>Scanner Started</b>\n掃描器已成功啟動並開始監控市場！"
        await self._send(text)

    async def send_signal(
        self,
        symbol: str,
        results: list["StrategyResult"],
    ) -> None:
        """Legacy per-symbol signal sender — kept for backward compatibility."""
        if not self._bot:
            logger.warning("Telegram bot token not configured, skipping notification")
            return
        text = format_signal_message(symbol, results)
        await self._send(text)

    async def send_error(self, error: str) -> None:
        """Send an error alert."""
        if not self._bot:
            return
        text = f"🚨 <b>Scanner Error</b>\n<code>{error}</code>"
        await self._send(text)

    async def _send(self, text: str, retries: int = 3) -> None:
        """Send with retry logic."""
        assert self._bot is not None

        for attempt in range(1, retries + 1):
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                return
            except Exception as exc:
                logger.warning(
                    "Telegram send attempt %d/%d failed: %s",
                    attempt,
                    retries,
                    exc,
                )
                if attempt == retries:
                    logger.error("Telegram send failed after %d attempts", retries)
                    raise

