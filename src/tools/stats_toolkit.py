"""Statistical analysis toolkit using pandas and scipy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class StatsResult:
    """Result container for statistical analysis."""

    summary: dict[str, Any] = field(default_factory=dict)
    tests: list[dict[str, Any]] = field(default_factory=list)
    correlations: dict[str, float] = field(default_factory=dict)
    trends: dict[str, Any] = field(default_factory=dict)


class StatsToolkit:
    """Statistical analysis on query result DataFrames."""

    def __init__(self, data: list[dict[str, Any]], columns: list[str]) -> None:
        self.df = pd.DataFrame(data, columns=columns) if data else pd.DataFrame()

    @property
    def is_empty(self) -> bool:
        return self.df.empty

    def descriptive_stats(self, columns: list[str] | None = None) -> dict[str, Any]:
        """Compute descriptive statistics for numeric columns."""
        if self.is_empty:
            return {}
        cols = columns or self.df.select_dtypes(include=[np.number]).columns.tolist()
        if not cols:
            return {}
        desc = self.df[cols].describe().to_dict()
        # Add additional stats
        for col in cols:
            series = self.df[col].dropna()
            if len(series) > 0:
                desc[col]["skewness"] = float(series.skew())
                desc[col]["kurtosis"] = float(series.kurtosis())
                desc[col]["median"] = float(series.median())
        return desc

    def correlation_matrix(self, columns: list[str] | None = None) -> dict[str, dict[str, float]]:
        """Compute pairwise Pearson correlations."""
        if self.is_empty:
            return {}
        cols = columns or self.df.select_dtypes(include=[np.number]).columns.tolist()
        if len(cols) < 2:
            return {}
        return self.df[cols].corr().to_dict()

    def t_test(self, col_a: str, col_b: str) -> dict[str, Any]:
        """Independent two-sample t-test."""
        a = self.df[col_a].dropna()
        b = self.df[col_b].dropna()
        stat, pvalue = stats.ttest_ind(a, b, equal_var=False)
        return {
            "test": "welch_t_test",
            "statistic": float(stat),
            "p_value": float(pvalue),
            "significant_at_05": pvalue < 0.05,
            "col_a_mean": float(a.mean()),
            "col_b_mean": float(b.mean()),
        }

    def trend_analysis(self, date_col: str, value_col: str) -> dict[str, Any]:
        """Simple linear trend on a time series."""
        if self.is_empty:
            return {}
        df = self.df[[date_col, value_col]].dropna().copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)
        x = np.arange(len(df))
        y = df[value_col].values.astype(float)
        if len(x) < 2:
            return {"error": "Not enough data points for trend analysis."}
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_value**2),
            "p_value": float(p_value),
            "std_err": float(std_err),
            "direction": "increasing" if slope > 0 else "decreasing",
            "data_points": len(x),
        }

    def group_comparison(self, group_col: str, value_col: str) -> dict[str, Any]:
        """Compare numeric values across groups."""
        if self.is_empty:
            return {}
        grouped = self.df.groupby(group_col)[value_col]
        summary = grouped.agg(["count", "mean", "std", "min", "max"]).to_dict("index")

        # One-way ANOVA if 3+ groups
        groups = [g[value_col].dropna().values for _, g in self.df.groupby(group_col)]
        groups = [g for g in groups if len(g) > 0]
        anova = {}
        if len(groups) >= 2:
            stat, pvalue = stats.f_oneway(*groups)
            anova = {
                "f_statistic": float(stat),
                "p_value": float(pvalue),
                "significant_at_05": pvalue < 0.05,
            }

        return {"group_stats": summary, "anova": anova}

    def full_analysis(self) -> StatsResult:
        """Run comprehensive analysis and return StatsResult."""
        result = StatsResult()
        result.summary = self.descriptive_stats()
        corr = self.correlation_matrix()
        if corr:
            # Flatten to top pairs
            pairs = {}
            cols = list(corr.keys())
            for i, c1 in enumerate(cols):
                for c2 in cols[i + 1 :]:
                    pairs[f"{c1}_vs_{c2}"] = corr[c1].get(c2, 0.0)
            result.correlations = pairs
        return result
