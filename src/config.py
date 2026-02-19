"""Configuration management — loads config.yaml + .env secrets via pydantic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Project root is two levels up from this file (src/config.py → project root)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"
_ENV_PATH = _PROJECT_ROOT / ".env"


# ── Sub-models ────────────────────────────────────────────────────────────────

class ExchangeConfig(BaseModel):
    name: str = "binance"
    base_url: str = "https://fapi.binance.com"
    market_type: str = "usdt_perpetual"
    min_volume_24h: float = 20_000_000
    max_symbols: int = 200
    min_listing_days: int = 7
    max_concurrent_requests: int = 10
    kline_limit: int = 100


class ScanConfig(BaseModel):
    interval_minutes: int = 15
    timeframes: list[str] = Field(default_factory=lambda: ["4h", "1h"])


class StrategyWeights(BaseModel):
    """Allow arbitrary weight keys per strategy."""

    model_config = {"extra": "allow"}

    def total(self) -> int:
        return sum(
            v for v in self.model_dump().values() if isinstance(v, (int, float))
        )


class TrendConfig(BaseModel):
    enabled: bool = True
    short_enabled: bool = True
    timeframe: str = "4h"
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_threshold: float = 50
    volume_multiplier: float = 1.5
    score_threshold: int = 6
    weights: StrategyWeights = Field(default_factory=StrategyWeights)


class DivergenceConfig(BaseModel):
    enabled: bool = True
    short_enabled: bool = True
    timeframe: str = "1h"
    lookback: int = 20
    rsi_oversold: float = 40
    rsi_overbought: float = 60
    swing_window: int = 5
    score_threshold: int = 6
    weights: StrategyWeights = Field(default_factory=StrategyWeights)


class BreakoutConfig(BaseModel):
    enabled: bool = True
    short_enabled: bool = True
    timeframe: str = "1h"
    consolidation_bars: int = 24
    range_threshold_pct: float = 5.0
    volume_multiplier: float = 2.0
    score_threshold: int = 6
    weights: StrategyWeights = Field(default_factory=StrategyWeights)


class StrategiesConfig(BaseModel):
    trend: TrendConfig = Field(default_factory=TrendConfig)
    divergence: DivergenceConfig = Field(default_factory=DivergenceConfig)
    breakout: BreakoutConfig = Field(default_factory=BreakoutConfig)


class BtcFilterConfig(BaseModel):
    enabled: bool = False
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_bearish: float = 40
    max_funding_rate: float = 0.0005


class NotificationConfig(BaseModel):
    cooldown_hours: int = 4
    strong_signal_threshold: int = 8
    score_delta_threshold: int = 2
    status_schedule_hours: list[int] = Field(
        default_factory=lambda: [0, 4, 8, 12, 16, 20]
    )


class LoggingConfig(BaseModel):
    level: str = "INFO"
    heartbeat_interval_hours: int = 1


# ── Root config ────────────────────────────────────────────────────────────────

class AppConfig(BaseModel):
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    strategies: StrategiesConfig = Field(default_factory=StrategiesConfig)
    btc_filter: BtcFilterConfig = Field(default_factory=BtcFilterConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Secrets — loaded from env
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


def _load_dotenv(env_path: Path) -> None:
    """Minimal .env loader — sets os.environ for keys not already set."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load YAML config and overlay .env secrets.

    Parameters
    ----------
    config_path:
        Override the default config.yaml location (useful for tests).
    """
    _load_dotenv(_ENV_PATH)

    path = config_path or _CONFIG_PATH
    data: dict[str, Any] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    # Inject secrets from environment
    data["telegram_bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    data["telegram_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID", "")

    return AppConfig(**data)
