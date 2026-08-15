"""Analysis evaluation scorers for statistical accuracy and insight relevance."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScorerResult:
    """Standard result returned by all scorers."""

    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


class StatisticalAccuracy:
    """Compare computed statistics against expected values within tolerance.

    Supports checking: mean, std, min, max, median, count, correlation values,
    and trend direction.
    """

    # Numeric keys that should be compared with tolerance
    NUMERIC_KEYS = {"mean", "std", "min", "max", "median", "count", "total"}

    def __init__(self, relative_tolerance: float = 0.05, absolute_tolerance: float = 0.5):
        """Initialize with tolerance thresholds.

        Args:
            relative_tolerance: Maximum allowed relative difference (default 5%).
            absolute_tolerance: Maximum allowed absolute difference for small values.
        """
        self.relative_tolerance = relative_tolerance
        self.absolute_tolerance = absolute_tolerance

    def _values_close(self, actual: float, expected: float) -> bool:
        """Check if two numeric values are close within tolerance."""
        if expected == 0:
            return abs(actual) <= self.absolute_tolerance
        relative_diff = abs(actual - expected) / abs(expected)
        absolute_diff = abs(actual - expected)
        return relative_diff <= self.relative_tolerance or absolute_diff <= self.absolute_tolerance

    def score(
        self,
        computed: dict[str, Any],
        expected: dict[str, Any],
    ) -> ScorerResult:
        """Score computed statistics against expected values.

        Args:
            computed: Dictionary of computed statistical values.
            expected: Dictionary of expected statistical values.

        Returns:
            ScorerResult with score based on fraction of matching values.
        """
        if not expected:
            return ScorerResult(
                name="statistical_accuracy",
                score=1.0,
                passed=True,
                details={"message": "No expected values provided"},
            )

        checks: list[dict[str, Any]] = []
        passed_checks = 0
        total_checks = 0

        for key, exp_value in expected.items():
            if exp_value is None:
                # Null expected means we expect the key to be absent or None
                actual_value = computed.get(key)
                ok = actual_value is None
                checks.append({"key": key, "expected": None, "actual": actual_value, "ok": ok})
                total_checks += 1
                if ok:
                    passed_checks += 1
                continue

            actual_value = computed.get(key)
            if actual_value is None:
                checks.append({
                    "key": key,
                    "expected": exp_value,
                    "actual": None,
                    "ok": False,
                    "error": "Key not found in computed results",
                })
                total_checks += 1
                continue

            # Numeric comparison
            if isinstance(exp_value, (int, float)) and isinstance(actual_value, (int, float)):
                if math.isnan(exp_value) or math.isnan(actual_value):
                    ok = math.isnan(exp_value) and math.isnan(actual_value)
                else:
                    ok = self._values_close(float(actual_value), float(exp_value))
                checks.append({
                    "key": key,
                    "expected": exp_value,
                    "actual": actual_value,
                    "ok": ok,
                })
                total_checks += 1
                if ok:
                    passed_checks += 1

            # String comparison (e.g., trend direction)
            elif isinstance(exp_value, str):
                ok = str(actual_value).lower().strip() == exp_value.lower().strip()
                checks.append({
                    "key": key,
                    "expected": exp_value,
                    "actual": actual_value,
                    "ok": ok,
                })
                total_checks += 1
                if ok:
                    passed_checks += 1
            else:
                # Fallback: equality check
                ok = actual_value == exp_value
                checks.append({
                    "key": key,
                    "expected": exp_value,
                    "actual": actual_value,
                    "ok": ok,
                })
                total_checks += 1
                if ok:
                    passed_checks += 1

        score = passed_checks / total_checks if total_checks > 0 else 0.0
        passed = score >= 0.8

        return ScorerResult(
            name="statistical_accuracy",
            score=round(score, 4),
            passed=passed,
            details={
                "passed_checks": passed_checks,
                "total_checks": total_checks,
                "checks": checks,
            },
        )


class InsightRelevance:
    """Check that generated insights mention expected keywords.

    Performs case-insensitive keyword matching against the list of insight
    strings to verify the analysis captured the important themes.
    """

    def score(
        self,
        insights: list[str],
        expected_keywords: list[str],
    ) -> ScorerResult:
        """Score insight relevance by keyword coverage.

        Args:
            insights: List of insight strings from the analyst.
            expected_keywords: Keywords that should appear in the insights.

        Returns:
            ScorerResult with score based on fraction of keywords found.
        """
        if not expected_keywords:
            return ScorerResult(
                name="insight_relevance",
                score=1.0,
                passed=True,
                details={"message": "No expected keywords provided"},
            )

        if not insights:
            return ScorerResult(
                name="insight_relevance",
                score=0.0,
                passed=False,
                details={"error": "No insights provided", "missing": expected_keywords},
            )

        # Combine all insights into a single searchable text
        combined_text = " ".join(insights).lower()

        found: list[str] = []
        missing: list[str] = []

        for keyword in expected_keywords:
            if keyword.lower() in combined_text:
                found.append(keyword)
            else:
                missing.append(keyword)

        total = len(expected_keywords)
        score = len(found) / total if total > 0 else 0.0
        passed = score >= 0.6  # At least 60% of keywords found

        return ScorerResult(
            name="insight_relevance",
            score=round(score, 4),
            passed=passed,
            details={"found": found, "missing": missing, "total_keywords": total},
        )
