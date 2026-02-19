"""Signal state management — deduplication, cooldown, and change detection.

Stores the last notification timestamp and score per (symbol, strategy) pair
in a JSON file, enabling:
  - Cooldown-based suppression
  - Score-delta bypass (if score improved significantly, re-notify early)
  - Invalidation detection (was notified, now below threshold)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import NotificationConfig

logger = logging.getLogger(__name__)

_DEFAULT_STATE_DIR = Path(__file__).resolve().parent.parent
_STATE_FILE = Path(os.environ.get("STATE_DIR", str(_DEFAULT_STATE_DIR))) / "state.json"


class StateManager:
    """Track notification history for deduplication and change detection."""

    def __init__(
        self,
        config: NotificationConfig,
        state_path: Path | None = None,
    ) -> None:
        self._cfg = config
        self._path = state_path or _STATE_FILE
        self._state: dict[str, dict] = self._load()

    # ── Public API ─────────────────────────────────────────────────────────

    def should_notify(self, symbol: str, strategy: str, score: int) -> bool:
        """Check if a notification should be sent.

        Returns True if:
          - No prior record exists (first time or after invalidation), OR
          - The cooldown window has elapsed (scenario E), OR
          - The score improved by >= score_delta_threshold (scenario D).
        """
        entry = self._state.get(self._key(symbol, strategy))

        if entry is None:
            return True  # First time — scenario A

        last_time = datetime.fromisoformat(entry["last_notified"])
        now = datetime.now(tz=timezone.utc)
        hours_elapsed = (now - last_time).total_seconds() / 3600

        if hours_elapsed >= self._cfg.cooldown_hours:
            return True  # Cooldown expired — scenario E

        last_score = entry.get("last_score", 0)
        if score - last_score >= self._cfg.score_delta_threshold:
            return True  # Significant score improvement — scenario D

        logger.debug(
            "Suppressed %s/%s (%.1fh elapsed, delta %+d)",
            symbol, strategy, hours_elapsed, score - last_score,
        )
        return False

    def record(self, symbol: str, strategy: str, score: int) -> None:
        """Record that a notification was just sent for this signal."""
        self._state[self._key(symbol, strategy)] = {
            "last_notified": datetime.now(tz=timezone.utc).isoformat(),
            "last_score": score,
        }
        self._save()

    def is_active(self, symbol: str, strategy: str) -> bool:
        """Return True if this signal has an existing state record."""
        return self._key(symbol, strategy) in self._state

    def get_last_score(self, symbol: str, strategy: str) -> int | None:
        """Return the score from the last recorded notification, or None."""
        entry = self._state.get(self._key(symbol, strategy))
        if entry is None:
            return None
        return entry.get("last_score", 0)

    def invalidate(self, symbol: str, strategy: str) -> None:
        """Remove this signal from state (score dropped below threshold)."""
        key = self._key(symbol, strategy)
        if key in self._state:
            del self._state[key]
            self._save()

    def get_active_signals(self) -> list[dict]:
        """Return all signals currently in state.

        Each item is a dict with keys:
            symbol, strategy, last_score, last_notified
        """
        result = []
        for key, entry in self._state.items():
            symbol, strategy = key.split("__", 1)
            result.append({
                "symbol": symbol,
                "strategy": strategy,
                "last_score": entry.get("last_score", 0),
                "last_notified": entry["last_notified"],
            })
        return result

    # ── Internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _key(symbol: str, strategy: str) -> str:
        return f"{symbol}__{strategy}"

    def _load(self) -> dict[str, dict]:
        if self._path.exists():
            try:
                raw: Any = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return self._migrate(raw)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load state file: %s", exc)
        return {}

    @staticmethod
    def _migrate(raw: dict) -> dict[str, dict]:
        """Migrate old format (plain ISO timestamp) to new {last_notified, last_score}."""
        migrated: dict[str, dict] = {}
        for key, value in raw.items():
            if isinstance(value, str):
                # Old format — assume last_score=0 for delta calculation
                migrated[key] = {"last_notified": value, "last_score": 0}
            elif isinstance(value, dict) and "last_notified" in value:
                migrated[key] = value
            else:
                logger.warning("Skipping unrecognised state entry for key '%s'", key)
        return migrated

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Failed to save state file: %s", exc)

