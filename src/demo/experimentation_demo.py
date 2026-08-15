"""Offline experimentation demo with known treatment effects."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.stats.experimentation import (
    ExperimentResult,
    benjamini_hochberg,
    difference_in_means,
    difference_in_proportions,
)

matplotlib.use("Agg")


def simulate_pricing_experiment(
    n_per_arm: int = 2500,
    conversion_control: float = 0.112,
    conversion_lift: float = 0.014,
    revenue_lift: float = 3.25,
    seed: int = 123,
) -> pd.DataFrame:
    """Simulate a two-arm pricing/offer experiment with known effects."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for arm, conversion_rate, revenue_shift in [
        ("control", conversion_control, 0.0),
        ("treatment", conversion_control + conversion_lift, revenue_lift),
    ]:
        converted = rng.binomial(1, conversion_rate, size=n_per_arm)
        base_revenue = rng.lognormal(mean=3.25, sigma=0.55, size=n_per_arm)
        revenue = converted * (base_revenue + revenue_shift)
        pre_period_spend = rng.gamma(shape=2.0, scale=18.0, size=n_per_arm)
        for idx in range(n_per_arm):
            rows.append(
                {
                    "user_id": f"{arm}_{idx}",
                    "arm": arm,
                    "converted": int(converted[idx]),
                    "revenue_per_user": float(revenue[idx]),
                    "pre_period_spend": float(pre_period_spend[idx]),
                }
            )
    return pd.DataFrame(rows)


def _format_number(value: float, metric_type: str) -> str:
    if metric_type == "proportion":
        return f"{value:.2%}"
    return f"{value:,.3f}"


def result_to_markdown(result: ExperimentResult) -> str:
    """Render one experiment result to markdown."""
    rel = "n/a" if result.effect_relative is None else f"{result.effect_relative:.2%}"
    findings = "\n".join(
        f"- {finding.severity.upper()}: {finding.message}" for finding in result.audit_findings
    )
    return f"""### {result.metric_name}

| Quantity | Value |
|---|---:|
| Control estimate | {_format_number(result.control_estimate, result.metric_type)} |
| Treatment estimate | {_format_number(result.treatment_estimate, result.metric_type)} |
| Absolute effect | {_format_number(result.effect_absolute, result.metric_type)} |
| Relative effect | {rel} |
| {int(result.ci_level * 100)}% CI | [{_format_number(result.ci_low, result.metric_type)}, {_format_number(result.ci_high, result.metric_type)}] |
| p-value | {result.p_value:.4g} |
| Effect size | {result.effect_size:.4f} |
| Approx. power | {result.power:.2%} |
| 80% power MDE | {_format_number(result.mde, result.metric_type)} |

Audit findings:

{findings or "- No audit warnings."}
"""


def plot_experiment_results(results: list[ExperimentResult], output_dir: Path) -> str:
    """Create an effect-size chart with confidence intervals."""
    path = output_dir / "experiment_effects.png"
    labels = [result.metric_name for result in results]
    effects = [result.effect_absolute for result in results]
    lows = [result.effect_absolute - result.ci_low for result in results]
    highs = [result.ci_high - result.effect_absolute for result in results]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.errorbar(effects, labels, xerr=[lows, highs], fmt="o", color="#0f766e", ecolor="#94a3b8", capsize=5)
    ax.axvline(0, color="#334155", linestyle="--", linewidth=1)
    ax.set_title("Treatment Effects with 95% Confidence Intervals")
    ax.set_xlabel("Treatment - control")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def run_experimentation_demo(output_dir: str = "output/experimentation_demo", seed: int = 123) -> dict[str, Any]:
    """Run the simulated experiment demo and export report/chart artifacts."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    df = simulate_pricing_experiment(seed=seed)
    control = df[df["arm"] == "control"]
    treatment = df[df["arm"] == "treatment"]

    conversion = difference_in_proportions(
        int(control["converted"].sum()),
        len(control),
        int(treatment["converted"].sum()),
        len(treatment),
        metric_name="Conversion rate",
    )
    revenue = difference_in_means(
        control["revenue_per_user"].to_numpy(),
        treatment["revenue_per_user"].to_numpy(),
        metric_name="Revenue per user",
        n_bootstrap=1000,
        seed=seed,
    )
    pvalue_table = benjamini_hochberg([conversion.p_value, revenue.p_value])
    chart_path = plot_experiment_results([conversion, revenue], output_path)
    data_path = output_path / "simulated_experiment.csv"
    df.to_csv(data_path, index=False)

    report = f"""# Experimentation Demo

This demo simulates a two-arm pricing/offer experiment with known treatment effects,
then estimates uncertainty, power, and interpretation risks.

## Design

- Control users: {len(control):,}
- Treatment users: {len(treatment):,}
- Metrics: conversion rate and revenue per user
- Methods: two-proportion z-test, Welch t-test, bootstrap CI, effect sizes, power/MDE diagnostics, Benjamini-Hochberg correction

## Results

{result_to_markdown(conversion)}

{result_to_markdown(revenue)}

## Multiple Testing

| Metric | raw p-value | BH adjusted p-value | reject at 5% FDR |
|---|---:|---:|---:|
| Conversion rate | {pvalue_table[0]["p_value"]:.4g} | {pvalue_table[0]["adjusted_p_value"]:.4g} | {pvalue_table[0]["reject"]} |
| Revenue per user | {pvalue_table[1]["p_value"]:.4g} | {pvalue_table[1]["adjusted_p_value"]:.4g} | {pvalue_table[1]["reject"]} |

## Artifacts

- Simulated data: `{data_path}`
- Effect chart: `{chart_path}`
"""
    report_path = output_path / "experimentation_demo_report.md"
    report_path.write_text(report)
    return {
        "output_dir": str(output_path),
        "report_path": str(report_path),
        "chart_path": chart_path,
        "data_path": str(data_path),
        "results": [asdict(conversion), asdict(revenue)],
        "multiple_testing": pvalue_table,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the offline experimentation statistics demo.")
    parser.add_argument("--output-dir", default="output/experimentation_demo")
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()
    result = run_experimentation_demo(output_dir=args.output_dir, seed=args.seed)
    print(f"Generated experimentation demo in {result['output_dir']}")
    print(f"Report: {result['report_path']}")
    print(f"Chart: {result['chart_path']}")


if __name__ == "__main__":
    main()
