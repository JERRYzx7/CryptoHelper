"""Telegram notification sender with message formatting and retry."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from telegram import Bot
from telegram.constants import ParseMode

if TYPE_CHECKING:
    from src.strategies.base import StrategyResult

logger = logging.getLogger(__name__)

# TradingView link template
_TV_URL = "https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}.P"


def _fmt_price(v: float) -> str:
    """Format a price value with appropriate decimal places."""
    if v >= 1000:
        return f"{v:.2f}"
    elif v >= 1:
        return f"{v:.4f}"
    else:
        return f"{v:.6f}"


# ── Pure formatting functions (testable without network) ───────────────────────

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
        """Send the three-section scan event notification."""
        if not self._bot:
            logger.warning("Telegram bot not configured, skipping scan report")
            return
        text = format_scan_report(invalidated, still_valid, new_discoveries)
        if text:
            await self._send(text)

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

