from __future__ import annotations

import pytest

from src.notifier import format_scan_report, format_status_report
from src.strategies.base import StrategyResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def _result(name: str, score: int, max_score: int, details: list[str],
            direction: str = "long", key_levels: dict | None = None) -> StrategyResult:
    return StrategyResult(
        strategy_name=name, score=score, max_score=max_score,
        details=details, direction=direction, key_levels=key_levels or {},
    )


# ── format_scan_report ─────────────────────────────────────────────────────────

class TestFormatScanReport:
    def test_new_discovery_section_present(self):
        r = _result("趨勢啟動型", 8, 8, ["EMA20 ↑穿 EMA50", "MACD 金叉"])
        msg = format_scan_report(
            invalidated=[],
            still_valid=[],
            new_discoveries=[("BTCUSDT", r)],
        )
        assert "🆕" in msg
        assert "BTCUSDT" in msg
        assert "趨勢啟動型" in msg
        assert "EMA20 ↑穿 EMA50" in msg
        assert "MACD 金叉" in msg

    def test_invalidated_section_present(self):
        msg = format_scan_report(
            invalidated=[{"symbol": "SOLUSDT", "strategy": "趨勢啟動型", "old_score": 8, "new_score": 2}],
            still_valid=[],
            new_discoveries=[],
        )
        assert "❌" in msg
        assert "SOLUSDT" in msg
        assert "8" in msg
        assert "2" in msg

    def test_still_valid_section_present(self):
        r = _result("爆量突破型", 9, 9, [])
        msg = format_scan_report(
            invalidated=[],
            still_valid=[{"symbol": "ETHUSDT", "strategy": "背離反轉型", "last_score": 7}],
            new_discoveries=[("BNBUSDT", r)],
        )
        assert "♻️" in msg
        assert "ETHUSDT" in msg

    def test_all_three_sections_in_correct_order(self):
        r = _result("爆量突破型", 9, 9, ["突破區間"])
        msg = format_scan_report(
            invalidated=[{"symbol": "SOLUSDT", "strategy": "趨勢啟動型", "old_score": 8, "new_score": 2}],
            still_valid=[{"symbol": "ETHUSDT", "strategy": "背離反轉型", "last_score": 7}],
            new_discoveries=[("BNBUSDT", r)],
        )
        idx_invalid = msg.index("❌")
        idx_valid = msg.index("♻️")
        idx_new = msg.index("🆕")
        assert idx_invalid < idx_valid < idx_new

    def test_empty_sections_omitted(self):
        """Sections with no entries should not appear in output."""
        r = _result("趨勢啟動型", 8, 8, [])
        msg = format_scan_report(
            invalidated=[],
            still_valid=[],
            new_discoveries=[("BTCUSDT", r)],
        )
        assert "❌" not in msg
        assert "♻️" not in msg
        assert "🆕" in msg

    def test_tradingview_link_in_new_discovery(self):
        r = _result("趨勢啟動型", 8, 8, [])
        msg = format_scan_report(
            invalidated=[],
            still_valid=[],
            new_discoveries=[("BTCUSDT", r)],
        )
        assert "tradingview.com" in msg.lower()

    def test_score_shown_for_new_discovery(self):
        r = _result("趨勢啟動型", 8, 8, [])
        msg = format_scan_report(
            invalidated=[],
            still_valid=[],
            new_discoveries=[("BTCUSDT", r)],
        )
        assert "8/8" in msg

    def test_multiple_new_discoveries(self):
        r1 = _result("趨勢啟動型", 8, 8, ["EMA Cross"])
        r2 = _result("爆量突破型", 9, 9, ["Volume surge"])
        msg = format_scan_report(
            invalidated=[],
            still_valid=[],
            new_discoveries=[("BTCUSDT", r1), ("ETHUSDT", r2)],
        )
        assert "BTCUSDT" in msg
        assert "ETHUSDT" in msg
        assert "EMA Cross" in msg
        assert "Volume surge" in msg


# ── format_status_report ───────────────────────────────────────────────────────

class TestFormatStatusReport:
    def test_contains_scheduled_time(self):
        msg = format_status_report(hour=8, new_count=0, invalidated_count=0, active_signals=[])
        assert "08:00" in msg

    def test_midnight_formatted_correctly(self):
        msg = format_status_report(hour=0, new_count=0, invalidated_count=0, active_signals=[])
        assert "00:00" in msg

    def test_activity_counts_shown(self):
        msg = format_status_report(hour=12, new_count=3, invalidated_count=1, active_signals=[])
        assert "3" in msg
        assert "1" in msg

    def test_active_signal_count_shown(self):
        signals = [
            {"symbol": "BTCUSDT", "strategy": "趨勢啟動型", "last_score": 8},
            {"symbol": "ETHUSDT", "strategy": "爆量突破型", "last_score": 9},
        ]
        msg = format_status_report(hour=4, new_count=0, invalidated_count=0, active_signals=signals)
        assert "2" in msg
        assert "持續有效" in msg

    def test_zero_active_no_error(self):
        msg = format_status_report(hour=16, new_count=0, invalidated_count=0, active_signals=[])
        assert "00:00" not in msg  # not 0:00
        assert "16:00" in msg
        assert "0" in msg


# ── Direction and Key Levels in Notifications ─────────────────────────────────

class TestDirectionAndKeyLevelsInNotification:
    def test_long_direction_shown(self):
        r = _result("趨勢啟動型", 8, 8, [], direction="long")
        msg = format_scan_report([], [], [("BTCUSDT", r)])
        assert "📈" in msg
        assert "做多" in msg

    def test_short_direction_shown(self):
        r = _result("趨勢啟動型(空)", 8, 8, [], direction="short")
        msg = format_scan_report([], [], [("BTCUSDT", r)])
        assert "📉" in msg
        assert "做空" in msg

    def test_key_levels_stop_and_target_shown(self):
        r = _result("爆量突破型", 9, 9, [],
                    key_levels={"stop": 95.1234, "target": 110.5678, "support": 97.0})
        msg = format_scan_report([], [], [("ETHUSDT", r)])
        assert "止損" in msg
        assert "目標" in msg
        assert "支撐" in msg

    def test_key_levels_resistance_shown_for_short(self):
        r = _result("趨勢啟動型(空)", 8, 8, [], direction="short",
                    key_levels={"stop": 110.0, "target": 95.0, "resistance": 108.0})
        msg = format_scan_report([], [], [("SOLUSDT", r)])
        assert "壓力" in msg
        assert "止損" in msg

    def test_no_key_levels_no_extra_lines(self):
        r = _result("趨勢啟動型", 8, 8, [])
        msg = format_scan_report([], [], [("BTCUSDT", r)])
        assert "止損" not in msg
        assert "目標" not in msg

    def test_html_escape_in_details(self):
        r = _result("背離反轉型", 7, 8, ["RSI 25.3 < 40（超賣）"])
        msg = format_scan_report([], [], [("XRPUSDT", r)])
        assert "&lt;" in msg  # < escaped
        assert "<40" not in msg  # raw < not present in HTML
