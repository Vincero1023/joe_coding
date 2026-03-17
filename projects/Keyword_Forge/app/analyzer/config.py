from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzerConfig:
    profit_weight: float = 0.60
    opportunity_weight: float = 0.40
    high_priority_threshold: float = 0.75
    medium_priority_threshold: float = 0.50
    minimum_score: float = 0.40
    max_tokens: int = 6


DEFAULT_CONFIG = AnalyzerConfig()
