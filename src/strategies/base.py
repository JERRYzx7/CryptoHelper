"""Abstract base class for all scanning strategies.

Each strategy evaluates an enriched OHLCV DataFrame and returns a
``StrategyResult`` containing the score, max possible score, and a list
of human-readable detail strings describing which conditions fired.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class StrategyResult:
    """Immutable result of a strategy evaluation."""

    strategy_name: str
    score: int
    max_score: int
    details: list[str] = field(default_factory=list)
    direction: str = "long"   # "long" 📈 or "short" 📉
    key_levels: dict = field(default_factory=dict)
    # key_levels may contain: stop, target, support, resistance

    @property
    def passed(self) -> bool:
        """Whether the score meets the threshold (set externally)."""
        # Threshold check is done by the caller because the threshold
        # lives in config, not inside the result.
        return self.score > 0

    def __str__(self) -> str:
        lines = [f"【{self.strategy_name}】 Score: {self.score}/{self.max_score}"]
        lines.extend(f"  ✓ {d}" for d in self.details)
        return "\n".join(lines)


class BaseStrategy(ABC):
    """Strategy interface — subclasses implement ``evaluate``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name (used in notifications)."""

    @property
    @abstractmethod
    def timeframe(self) -> str:
        """Expected timeframe, e.g. '4h' or '1h'."""

    @abstractmethod
    def evaluate(self, df: pd.DataFrame) -> StrategyResult:
        """Score the latest bar(s) of *df* against this strategy's rules.

        Parameters
        ----------
        df:
            OHLCV DataFrame already enriched via
            ``indicators.technical.enrich_dataframe``.

        Returns
        -------
        StrategyResult with score, max_score, and detail strings.
        """
