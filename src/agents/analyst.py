"""Analyst agent: performs statistical analysis on query results."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.graph.state import AnalysisResult, AnalystState
from src.tools.stats_toolkit import StatsToolkit


def analyst_node(state: AnalystState) -> dict[str, Any]:
    """Run statistical analysis on the query results."""
    qr = state.query_result

    if qr.error or not qr.rows:
        logger.warning("No data to analyze (error={}, rows={})", qr.error, qr.row_count)
        return {
            "analysis": AnalysisResult(
                insights=["No data available for analysis."],
            )
        }

    toolkit = StatsToolkit(data=qr.rows, columns=qr.columns)
    result = toolkit.full_analysis()

    # Generate textual insights
    insights: list[str] = []
    if result.summary:
        for col, stats_dict in result.summary.items():
            mean = stats_dict.get("mean")
            std = stats_dict.get("std")
            if mean is not None and std is not None:
                insights.append(
                    f"{col}: mean={mean:.2f}, std={std:.2f}, "
                    f"range=[{stats_dict.get('min', 'N/A')}, {stats_dict.get('max', 'N/A')}]"
                )

    if result.correlations:
        strong = {k: v for k, v in result.correlations.items() if abs(v) > 0.7}
        if strong:
            insights.append(f"Strong correlations: {strong}")

    logger.info("Analysis produced {} insights", len(insights))

    return {
        "analysis": AnalysisResult(
            summary_stats=result.summary,
            correlations=result.correlations,
            tests=[],
            trends=result.trends,
            insights=insights,
        )
    }
