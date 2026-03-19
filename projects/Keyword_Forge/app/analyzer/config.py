from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzerConfig:
    monetization_weight: float = 0.40
    volume_weight: float = 0.35
    rarity_weight: float = 0.25
    high_priority_threshold: float = 70.0
    medium_priority_threshold: float = 50.0
    minimum_score: float = 20.0
    max_tokens: int = 8


DEFAULT_CONFIG = AnalyzerConfig()
