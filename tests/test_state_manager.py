"""Tests for the state manager deduplication logic."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.config import NotificationConfig
from src.state_manager import StateManager


@pytest.fixture
def tmp_state(tmp_path: Path):
    """Provide a fresh state file path."""
    return tmp_path / "state.json"


@pytest.fixture
def config():
    return NotificationConfig(
        cooldown_hours=4,
        strong_signal_threshold=8,
        score_delta_threshold=2,
    )


class TestStateManager:
    def test_first_notification_allowed(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=6) is True

    def test_cooldown_blocks_second_notification(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=6)
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=6) is False

    def test_different_strategy_not_blocked(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=6)
        assert sm.should_notify("BTCUSDT", "爆量突破型", score=6) is True

    def test_different_symbol_not_blocked(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=6)
        assert sm.should_notify("ETHUSDT", "趨勢啟動型", score=6) is True

    def test_score_delta_bypasses_cooldown(self, config, tmp_state):
        """Score improvement >= score_delta_threshold bypasses cooldown."""
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=6)
        # delta = 8 - 6 = 2 >= 2 → bypass
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=8) is True

    def test_score_delta_below_threshold_blocked(self, config, tmp_state):
        """Small score change does NOT bypass cooldown."""
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=6)
        # delta = 7 - 6 = 1 < 2 → blocked
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=7) is False

    def test_cooldown_expires(self, config, tmp_state):
        old_time = datetime.now(tz=timezone.utc) - timedelta(hours=5)
        key = "BTCUSDT__趨勢啟動型"
        tmp_state.write_text(
            json.dumps({key: {"last_notified": old_time.isoformat(), "last_score": 6}}),
            encoding="utf-8",
        )
        sm = StateManager(config, state_path=tmp_state)
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=6) is True

    def test_state_persists_to_disk(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("SOLUSDT", "背離反轉型", score=7)
        assert tmp_state.exists()
        data = json.loads(tmp_state.read_text(encoding="utf-8"))
        assert "SOLUSDT__背離反轉型" in data
        assert data["SOLUSDT__背離反轉型"]["last_score"] == 7

    def test_corrupt_state_file_handled(self, config, tmp_state):
        tmp_state.write_text("not valid json", encoding="utf-8")
        sm = StateManager(config, state_path=tmp_state)
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=6) is True

    def test_invalidate_removes_from_state(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=6)
        assert sm.is_active("BTCUSDT", "趨勢啟動型") is True
        sm.invalidate("BTCUSDT", "趨勢啟動型")
        assert sm.is_active("BTCUSDT", "趨勢啟動型") is False

    def test_after_invalidation_trigger_allowed(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=6)
        sm.invalidate("BTCUSDT", "趨勢啟動型")
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=6) is True

    def test_get_last_score(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=7)
        assert sm.get_last_score("BTCUSDT", "趨勢啟動型") == 7

    def test_get_last_score_not_active_returns_none(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        assert sm.get_last_score("BTCUSDT", "趨勢啟動型") is None

    def test_get_active_signals(self, config, tmp_state):
        sm = StateManager(config, state_path=tmp_state)
        sm.record("BTCUSDT", "趨勢啟動型", score=8)
        sm.record("ETHUSDT", "爆量突破型", score=9)
        active = sm.get_active_signals()
        assert len(active) == 2
        symbols = {s["symbol"] for s in active}
        assert symbols == {"BTCUSDT", "ETHUSDT"}

    def test_backward_compat_old_format(self, config, tmp_state):
        """Old state format (plain ISO timestamp string) migrates with last_score=0."""
        old_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        key = "BTCUSDT__趨勢啟動型"
        tmp_state.write_text(
            json.dumps({key: old_time.isoformat()}), encoding="utf-8"
        )
        sm = StateManager(config, state_path=tmp_state)
        # last_score=0; delta = 6-0 = 6 >= 2 → bypass cooldown
        assert sm.get_last_score("BTCUSDT", "趨勢啟動型") == 0
        assert sm.should_notify("BTCUSDT", "趨勢啟動型", score=6) is True

