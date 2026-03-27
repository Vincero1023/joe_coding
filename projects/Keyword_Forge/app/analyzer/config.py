from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalyzerConfig:
    monetization_weight: float = 0.40
    volume_weight: float = 0.35
    rarity_weight: float = 0.25
    profitability_monetization_weight: float = 0.70
    profitability_volume_weight: float = 0.10
    profitability_click_weight: float = 0.20
    attackability_opportunity_weight: float = 0.30
    attackability_rarity_weight: float = 0.05
    attackability_competition_weight: float = 0.25
    attackability_volume_weight: float = 0.15
    attackability_click_weight: float = 0.25
    profitability_a_threshold: float = 72.0
    profitability_b_threshold: float = 64.0
    profitability_c_threshold: float = 56.0
    profitability_d_threshold: float = 47.0
    profitability_e_threshold: float = 38.0
    attackability_1_threshold: float = 74.0
    attackability_2_threshold: float = 66.0
    attackability_3_threshold: float = 58.0
    attackability_4_threshold: float = 49.0
    attackability_5_threshold: float = 40.0
    high_priority_threshold: float = 70.0
    medium_priority_threshold: float = 50.0
    minimum_score: float = 20.0
    max_tokens: int = 8


DEFAULT_CONFIG = AnalyzerConfig()
