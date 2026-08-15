"""Tests for experimentation statistics and audit checks."""

import numpy as np

from src.demo.experimentation_demo import run_experimentation_demo, simulate_pricing_experiment
from src.stats.experimentation import (
    benjamini_hochberg,
    difference_in_means,
    difference_in_proportions,
    minimum_detectable_effect_means,
)


def test_difference_in_means_detects_known_lift():
    rng = np.random.default_rng(42)
    control = rng.normal(10.0, 2.0, size=600)
    treatment = rng.normal(11.0, 2.0, size=600)
    result = difference_in_means(control, treatment, metric_name="spend", n_bootstrap=300)
    assert result.effect_absolute > 0.6
    assert result.ci_low > 0
    assert result.p_value < 0.001
    assert result.bootstrap_ci_low is not None


def test_difference_in_proportions_detects_lift():
    result = difference_in_proportions(100, 1000, 140, 1000)
    assert result.effect_absolute > 0
    assert result.metric_type == "proportion"
    assert result.p_value < 0.05
    assert result.mde > 0


def test_benjamini_hochberg_marks_discoveries():
    corrected = benjamini_hochberg([0.001, 0.02, 0.5], alpha=0.05)
    assert corrected[0]["reject"] is True
    assert corrected[2]["reject"] is False
    adjusted = [row["adjusted_p_value"] for row in corrected]
    assert adjusted[0] <= adjusted[1] <= adjusted[2]


def test_minimum_detectable_effect_means_positive():
    mde = minimum_detectable_effect_means(std=2.0, n_control=500, n_treatment=500)
    assert 0 < mde < 1


def test_difference_in_means_rejects_tiny_arms():
    try:
        difference_in_means([1.0], [2.0], n_bootstrap=100)
    except ValueError as exc:
        assert "at least two" in str(exc)
    else:
        raise AssertionError("expected ValueError for tiny experiment arms")


def test_difference_in_proportions_rejects_invalid_counts():
    try:
        difference_in_proportions(11, 10, 3, 10)
    except ValueError as exc:
        assert "control_successes" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid successes")


def test_simulate_pricing_experiment_shape():
    df = simulate_pricing_experiment(n_per_arm=250, seed=7)
    assert len(df) == 500
    assert {"arm", "converted", "revenue_per_user"}.issubset(df.columns)


def test_run_experimentation_demo_creates_artifacts(tmp_path):
    result = run_experimentation_demo(output_dir=str(tmp_path), seed=7)
    assert result["report_path"].endswith("experimentation_demo_report.md")
    assert len(result["results"]) == 2
    assert tmp_path.joinpath("experimentation_demo_report.md").exists()
    assert tmp_path.joinpath("experiment_effects.png").exists()
