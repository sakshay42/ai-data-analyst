"""Statistics-focused methods for experiments and audit checks."""

from src.stats.experimentation import (
    ExperimentResult,
    StatAuditFinding,
    benjamini_hochberg,
    bootstrap_mean_difference_ci,
    difference_in_means,
    difference_in_proportions,
    minimum_detectable_effect_means,
    minimum_detectable_effect_proportions,
    power_two_sample_means,
    power_two_sample_proportions,
)

__all__ = [
    "ExperimentResult",
    "StatAuditFinding",
    "benjamini_hochberg",
    "bootstrap_mean_difference_ci",
    "difference_in_means",
    "difference_in_proportions",
    "minimum_detectable_effect_means",
    "minimum_detectable_effect_proportions",
    "power_two_sample_means",
    "power_two_sample_proportions",
]
