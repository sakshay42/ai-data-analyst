"""Braintrust evaluation script for analyst node quality.

Tests statistical accuracy and insight relevance using the analysis
quality dataset with known expected outputs.

Usage:
    poetry run python evals/eval_analysis.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import braintrust
import numpy as np

# Ensure the project root is on the path so scorer imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.scorers.analysis_scorers import InsightRelevance, StatisticalAccuracy

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "analysis_quality.json"


def load_dataset() -> list[dict]:
    """Load the analysis quality evaluation dataset."""
    with open(DATASET_PATH) as f:
        return json.load(f)


def compute_stats(data: list[dict], columns: list[str]) -> dict[str, Any]:
    """Simulate the analyst node by computing basic statistics.

    This mirrors what StatsToolkit.full_analysis() would produce,
    keeping the eval self-contained without requiring external services.
    """
    if not data:
        return {"count": 0, "mean": None, "insights": "no_data"}

    result: dict[str, Any] = {}

    # Identify numeric columns
    numeric_cols = []
    for col in columns:
        sample_values = [row.get(col) for row in data if row.get(col) is not None]
        if sample_values and all(isinstance(v, (int, float)) for v in sample_values):
            numeric_cols.append(col)

    if not numeric_cols:
        result["count"] = len(data)
        return result

    for col in numeric_cols:
        values = [row[col] for row in data if row.get(col) is not None]
        if not values:
            continue

        arr = np.array(values, dtype=float)
        col_stats = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "median": float(np.median(arr)),
            "count": len(arr),
        }

        # Flatten into result with column prefix for multi-column data
        if len(numeric_cols) == 1:
            result.update(col_stats)
        else:
            for stat_name, stat_val in col_stats.items():
                result[f"{stat_name}_{col}"] = stat_val

    # Total for single-numeric distribution data
    if len(numeric_cols) == 1:
        values = [row[numeric_cols[0]] for row in data if row.get(numeric_cols[0]) is not None]
        result["total"] = sum(values)

    # Trend detection (simple: compare first half to second half)
    if len(numeric_cols) >= 2:
        # Use the second numeric column as the metric (first is often an index)
        metric_col = numeric_cols[1]
        values = [row[metric_col] for row in data if row.get(metric_col) is not None]
        if len(values) >= 4:
            mid = len(values) // 2
            first_half_mean = np.mean(values[:mid])
            second_half_mean = np.mean(values[mid:])
            diff_pct = (second_half_mean - first_half_mean) / abs(first_half_mean) if first_half_mean != 0 else 0
            if diff_pct > 0.05:
                result["trend"] = "increasing"
            elif diff_pct < -0.05:
                result["trend"] = "decreasing"
            else:
                result["trend"] = "stable"

    # Correlation detection for two numeric columns
    if len(numeric_cols) == 2:
        col_a, col_b = numeric_cols
        vals_a = [row[col_a] for row in data]
        vals_b = [row[col_b] for row in data]
        if len(vals_a) >= 3:
            corr = float(np.corrcoef(vals_a, vals_b)[0, 1])
            result[f"correlation_{col_a}_{col_b}"] = round(corr, 3)
            if corr > 0.3:
                result["correlation_direction"] = "positive"
            elif corr < -0.3:
                result["correlation_direction"] = "negative"
            else:
                result["correlation_direction"] = "weak"

    # Percentage distribution (for category + count data)
    if "category" in columns and len(numeric_cols) == 1:
        count_col = numeric_cols[0]
        total = sum(row[count_col] for row in data)
        if total > 0:
            for row in data:
                cat = row.get("category")
                if cat:
                    result[f"pct_{cat}"] = round(100.0 * row[count_col] / total, 1)

    return result


def analysis_task(input_data: dict) -> dict[str, Any]:
    """Run analysis on the test case data."""
    computed = compute_stats(input_data["data"], input_data["columns"])

    # Generate simple insights
    insights: list[str] = []
    if computed.get("mean") is not None:
        insights.append(f"Mean value is {computed['mean']}")
    if computed.get("trend"):
        insights.append(f"Trend is {computed['trend']}")
    for key, val in computed.items():
        if "correlation" in key and isinstance(val, (int, float)):
            insights.append(f"Correlation: {key} = {val}")

    return {
        "computed": computed,
        "insights": insights,
        "name": input_data["name"],
    }


def score_statistical_accuracy(output: dict, expected: dict) -> float:
    """Score statistical accuracy of computed results."""
    scorer = StatisticalAccuracy(relative_tolerance=0.05, absolute_tolerance=0.5)
    result = scorer.score(output["computed"], expected)
    return result.score


def score_insight_relevance(output: dict, expected: dict) -> float:
    """Score whether insights capture expected keywords."""
    # Extract keywords from expected dict keys and string values
    keywords: list[str] = []
    for key, val in expected.items():
        if isinstance(val, str) and val != "no_data":
            keywords.append(val)

    if not keywords:
        return 1.0  # No keyword expectations

    scorer = InsightRelevance()
    result = scorer.score(output["insights"], keywords)
    return result.score


def run_eval():
    """Run the Braintrust evaluation."""
    dataset = load_dataset()

    braintrust.Eval(
        "Analysis Quality",
        data=lambda: [
            {
                "input": item,
                "expected": item["expected"],
                "metadata": {"name": item["name"]},
            }
            for item in dataset
        ],
        task=analysis_task,
        scores=[
            score_statistical_accuracy,
            score_insight_relevance,
        ],
    )


if __name__ == "__main__":
    run_eval()
