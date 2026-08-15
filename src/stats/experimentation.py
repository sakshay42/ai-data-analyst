"""Experimentation analysis with uncertainty and audit checks.

This module is intentionally deterministic and dependency-light. It provides
the statistical layer a PhD-level reviewer would expect: uncertainty intervals,
effect sizes, power/MDE diagnostics, multiple-testing correction, and warnings
when a conclusion is not well supported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import asin, sqrt
from typing import Literal

import numpy as np
from scipy import optimize, stats


Severity = Literal["info", "warning", "error"]
MetricType = Literal["continuous", "proportion"]


@dataclass(frozen=True)
class StatAuditFinding:
    """One statistical audit finding."""

    code: str
    severity: Severity
    message: str


@dataclass(frozen=True)
class ExperimentResult:
    """Summary of one two-arm experiment analysis."""

    metric_name: str
    metric_type: MetricType
    control_label: str
    treatment_label: str
    n_control: int
    n_treatment: int
    control_estimate: float
    treatment_estimate: float
    effect_absolute: float
    effect_relative: float | None
    standard_error: float
    ci_level: float
    ci_low: float
    ci_high: float
    p_value: float
    test_statistic: float
    effect_size: float
    power: float
    mde: float
    bootstrap_ci_low: float | None = None
    bootstrap_ci_high: float | None = None
    audit_findings: list[StatAuditFinding] = field(default_factory=list)

    @property
    def statistically_significant(self) -> bool:
        return self.p_value < 1 - self.ci_level

    @property
    def ci_excludes_zero(self) -> bool:
        return self.ci_low > 0 or self.ci_high < 0


def _relative_effect(effect: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return effect / abs(baseline)


def bootstrap_mean_difference_ci(
    control: np.ndarray,
    treatment: np.ndarray,
    ci_level: float = 0.95,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap percentile CI for treatment-control mean difference."""
    rng = np.random.default_rng(seed)
    control = np.asarray(control, dtype=float)
    treatment = np.asarray(treatment, dtype=float)
    diffs = np.empty(n_bootstrap)
    for idx in range(n_bootstrap):
        control_sample = rng.choice(control, size=len(control), replace=True)
        treatment_sample = rng.choice(treatment, size=len(treatment), replace=True)
        diffs[idx] = treatment_sample.mean() - control_sample.mean()
    alpha = 1 - ci_level
    return (
        float(np.quantile(diffs, alpha / 2)),
        float(np.quantile(diffs, 1 - alpha / 2)),
    )


def power_two_sample_means(
    effect: float,
    std: float,
    n_control: int,
    n_treatment: int,
    alpha: float = 0.05,
) -> float:
    """Approximate two-sided power for a two-sample mean test."""
    if std <= 0 or n_control <= 1 or n_treatment <= 1:
        return 0.0
    se = std * sqrt(1 / n_control + 1 / n_treatment)
    noncentrality = abs(effect) / se
    critical = stats.norm.ppf(1 - alpha / 2)
    power = 1 - stats.norm.cdf(critical - noncentrality) + stats.norm.cdf(-critical - noncentrality)
    return float(np.clip(power, 0.0, 1.0))


def minimum_detectable_effect_means(
    std: float,
    n_control: int,
    n_treatment: int,
    alpha: float = 0.05,
    target_power: float = 0.80,
) -> float:
    """Approximate MDE for a two-sample mean test."""
    if std <= 0 or n_control <= 1 or n_treatment <= 1:
        return float("inf")
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_power = stats.norm.ppf(target_power)
    return float((z_alpha + z_power) * std * sqrt(1 / n_control + 1 / n_treatment))


def power_two_sample_proportions(
    baseline_rate: float,
    effect: float,
    n_control: int,
    n_treatment: int,
    alpha: float = 0.05,
) -> float:
    """Approximate two-sided power for a difference in proportions."""
    p1 = baseline_rate
    p2 = baseline_rate + effect
    if not 0 < p1 < 1 or not 0 < p2 < 1:
        return 0.0
    se_null = sqrt(p1 * (1 - p1) * (1 / n_control + 1 / n_treatment))
    se_alt = sqrt(p1 * (1 - p1) / n_control + p2 * (1 - p2) / n_treatment)
    if se_null <= 0 or se_alt <= 0:
        return 0.0
    critical = stats.norm.ppf(1 - alpha / 2) * se_null
    power = 1 - stats.norm.cdf((critical - abs(effect)) / se_alt) + stats.norm.cdf((-critical - abs(effect)) / se_alt)
    return float(np.clip(power, 0.0, 1.0))


def minimum_detectable_effect_proportions(
    baseline_rate: float,
    n_control: int,
    n_treatment: int,
    alpha: float = 0.05,
    target_power: float = 0.80,
) -> float:
    """Approximate absolute MDE for a two-sample proportion test."""
    if not 0 < baseline_rate < 1:
        return float("inf")

    def objective(effect: float) -> float:
        return power_two_sample_proportions(
            baseline_rate, effect, n_control, n_treatment, alpha=alpha
        ) - target_power

    upper = min(0.99 - baseline_rate, max(0.01, 0.5 - baseline_rate / 2))
    if objective(upper) < 0:
        return float("inf")
    return float(optimize.brentq(objective, 1e-6, upper))


def benjamini_hochberg(p_values: list[float], alpha: float = 0.05) -> list[dict[str, float | bool]]:
    """Benjamini-Hochberg FDR correction."""
    if not p_values:
        return []
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    if any(p < 0 or p > 1 for p in p_values):
        raise ValueError("p-values must be between 0 and 1")

    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    m = len(p_values)
    adjusted = [1.0] * m
    discoveries = [False] * m
    running_min = 1.0
    threshold_rank = -1

    for rank, (original_idx, p_value) in enumerate(indexed, start=1):
        if p_value <= alpha * rank / m:
            threshold_rank = rank

    for rank, (original_idx, p_value) in reversed(list(enumerate(indexed, start=1))):
        running_min = min(running_min, p_value * m / rank)
        adjusted[original_idx] = min(1.0, running_min)

    if threshold_rank >= 1:
        for rank, (original_idx, _) in enumerate(indexed, start=1):
            discoveries[original_idx] = rank <= threshold_rank

    return [
        {
            "p_value": float(p),
            "adjusted_p_value": float(adjusted[idx]),
            "reject": bool(discoveries[idx]),
        }
        for idx, p in enumerate(p_values)
    ]


def audit_experiment_result(
    result: ExperimentResult,
    min_n_per_arm: int = 100,
    min_power: float = 0.80,
    practical_effect_threshold: float | None = None,
) -> list[StatAuditFinding]:
    """Flag common statistical interpretation risks."""
    findings: list[StatAuditFinding] = []
    if result.n_control < min_n_per_arm or result.n_treatment < min_n_per_arm:
        findings.append(
            StatAuditFinding(
                code="LOW_SAMPLE_SIZE",
                severity="warning",
                message=f"At least one arm has fewer than {min_n_per_arm} observations.",
            )
        )
    if result.power < min_power:
        findings.append(
            StatAuditFinding(
                code="LOW_POWER",
                severity="warning",
                message=f"Estimated power is {result.power:.1%}, below the {min_power:.0%} target.",
            )
        )
    if not result.ci_excludes_zero:
        findings.append(
            StatAuditFinding(
                code="CI_INCLUDES_ZERO",
                severity="info",
                message="The confidence interval includes zero; avoid claiming a directional effect.",
            )
        )
    if practical_effect_threshold is not None and abs(result.effect_absolute) < practical_effect_threshold:
        findings.append(
            StatAuditFinding(
                code="LOW_PRACTICAL_SIGNIFICANCE",
                severity="info",
                message="The estimated effect is below the configured practical significance threshold.",
            )
        )
    if result.statistically_significant and not result.ci_excludes_zero:
        findings.append(
            StatAuditFinding(
                code="INCONSISTENT_INFERENCE",
                severity="error",
                message="P-value and confidence interval disagree; inspect inputs and assumptions.",
            )
        )
    return findings


def difference_in_means(
    control: list[float] | np.ndarray,
    treatment: list[float] | np.ndarray,
    metric_name: str = "metric",
    control_label: str = "control",
    treatment_label: str = "treatment",
    ci_level: float = 0.95,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> ExperimentResult:
    """Welch test, analytic CI, bootstrap CI, Cohen d, power, and audit checks."""
    if not 0 < ci_level < 1:
        raise ValueError("ci_level must be between 0 and 1")
    if n_bootstrap < 100:
        raise ValueError("n_bootstrap must be at least 100")
    control_arr = np.asarray(control, dtype=float)
    treatment_arr = np.asarray(treatment, dtype=float)
    control_arr = control_arr[~np.isnan(control_arr)]
    treatment_arr = treatment_arr[~np.isnan(treatment_arr)]
    n_control = len(control_arr)
    n_treatment = len(treatment_arr)
    if n_control < 2 or n_treatment < 2:
        raise ValueError("each arm must have at least two non-missing observations")
    mean_control = float(control_arr.mean())
    mean_treatment = float(treatment_arr.mean())
    effect = mean_treatment - mean_control
    var_control = float(control_arr.var(ddof=1))
    var_treatment = float(treatment_arr.var(ddof=1))
    se = sqrt(var_control / n_control + var_treatment / n_treatment)
    test = stats.ttest_ind(treatment_arr, control_arr, equal_var=False)
    df_num = (var_control / n_control + var_treatment / n_treatment) ** 2
    df_den = (var_control**2 / (n_control**2 * (n_control - 1))) + (
        var_treatment**2 / (n_treatment**2 * (n_treatment - 1))
    )
    df = df_num / df_den if df_den > 0 else n_control + n_treatment - 2
    alpha = 1 - ci_level
    critical = stats.t.ppf(1 - alpha / 2, df)
    ci_low = effect - critical * se
    ci_high = effect + critical * se
    pooled_std = sqrt(
        ((n_control - 1) * var_control + (n_treatment - 1) * var_treatment)
        / max(n_control + n_treatment - 2, 1)
    )
    effect_size = effect / pooled_std if pooled_std > 0 else 0.0
    boot_low, boot_high = bootstrap_mean_difference_ci(
        control_arr, treatment_arr, ci_level=ci_level, n_bootstrap=n_bootstrap, seed=seed
    )
    power = power_two_sample_means(effect, pooled_std, n_control, n_treatment, alpha=alpha)
    mde = minimum_detectable_effect_means(pooled_std, n_control, n_treatment, alpha=alpha)
    partial = ExperimentResult(
        metric_name=metric_name,
        metric_type="continuous",
        control_label=control_label,
        treatment_label=treatment_label,
        n_control=n_control,
        n_treatment=n_treatment,
        control_estimate=mean_control,
        treatment_estimate=mean_treatment,
        effect_absolute=float(effect),
        effect_relative=_relative_effect(effect, mean_control),
        standard_error=float(se),
        ci_level=ci_level,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        p_value=float(test.pvalue),
        test_statistic=float(test.statistic),
        effect_size=float(effect_size),
        power=power,
        mde=mde,
        bootstrap_ci_low=boot_low,
        bootstrap_ci_high=boot_high,
    )
    return ExperimentResult(**{**partial.__dict__, "audit_findings": audit_experiment_result(partial)})


def difference_in_proportions(
    control_successes: int,
    control_total: int,
    treatment_successes: int,
    treatment_total: int,
    metric_name: str = "conversion_rate",
    control_label: str = "control",
    treatment_label: str = "treatment",
    ci_level: float = 0.95,
) -> ExperimentResult:
    """Two-sample proportion z-test with CI, Cohen h, power, MDE, and audit checks."""
    if not 0 < ci_level < 1:
        raise ValueError("ci_level must be between 0 and 1")
    if control_total <= 0 or treatment_total <= 0:
        raise ValueError("arm totals must be positive")
    if not 0 <= control_successes <= control_total:
        raise ValueError("control_successes must be between 0 and control_total")
    if not 0 <= treatment_successes <= treatment_total:
        raise ValueError("treatment_successes must be between 0 and treatment_total")
    p_control = control_successes / control_total
    p_treatment = treatment_successes / treatment_total
    effect = p_treatment - p_control
    pooled = (control_successes + treatment_successes) / (control_total + treatment_total)
    se_null = sqrt(pooled * (1 - pooled) * (1 / control_total + 1 / treatment_total))
    se_unpooled = sqrt(
        p_control * (1 - p_control) / control_total
        + p_treatment * (1 - p_treatment) / treatment_total
    )
    z_stat = effect / se_null if se_null > 0 else 0.0
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
    alpha = 1 - ci_level
    critical = stats.norm.ppf(1 - alpha / 2)
    ci_low = effect - critical * se_unpooled
    ci_high = effect + critical * se_unpooled
    cohen_h = 2 * asin(sqrt(p_treatment)) - 2 * asin(sqrt(p_control))
    power = power_two_sample_proportions(p_control, effect, control_total, treatment_total, alpha=alpha)
    mde = minimum_detectable_effect_proportions(p_control, control_total, treatment_total, alpha=alpha)
    partial = ExperimentResult(
        metric_name=metric_name,
        metric_type="proportion",
        control_label=control_label,
        treatment_label=treatment_label,
        n_control=control_total,
        n_treatment=treatment_total,
        control_estimate=float(p_control),
        treatment_estimate=float(p_treatment),
        effect_absolute=float(effect),
        effect_relative=_relative_effect(effect, p_control),
        standard_error=float(se_unpooled),
        ci_level=ci_level,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        p_value=float(p_value),
        test_statistic=float(z_stat),
        effect_size=float(cohen_h),
        power=power,
        mde=mde,
    )
    return ExperimentResult(**{**partial.__dict__, "audit_findings": audit_experiment_result(partial)})
