"""Tests for the analyst agent."""

import pytest

from src.agents.analyst import analyst_node
from src.graph.state import AnalystState, QueryResult


class TestAnalystNode:
    def test_with_data(self):
        state = AnalystState(
            query_result=QueryResult(
                sql="SELECT 1",
                columns=["value", "count"],
                rows=[
                    {"value": 10.0, "count": 5},
                    {"value": 20.0, "count": 10},
                    {"value": 30.0, "count": 15},
                ],
                row_count=3,
            )
        )
        result = analyst_node(state)

        assert "analysis" in result
        analysis = result["analysis"]
        assert analysis.summary_stats  # should have descriptive stats
        assert len(analysis.insights) > 0

    def test_empty_data(self):
        state = AnalystState(
            query_result=QueryResult(sql="SELECT 1", columns=[], rows=[], row_count=0)
        )
        result = analyst_node(state)

        assert "No data available" in result["analysis"].insights[0]

    def test_error_state(self):
        state = AnalystState(
            query_result=QueryResult(sql="bad", error="syntax error")
        )
        result = analyst_node(state)

        assert "No data available" in result["analysis"].insights[0]

    def test_stats_accuracy(self):
        state = AnalystState(
            query_result=QueryResult(
                sql="SELECT 1",
                columns=["x"],
                rows=[{"x": 1.0}, {"x": 2.0}, {"x": 3.0}, {"x": 4.0}, {"x": 5.0}],
                row_count=5,
            )
        )
        result = analyst_node(state)
        stats = result["analysis"].summary_stats

        assert "x" in stats
        assert abs(stats["x"]["mean"] - 3.0) < 0.01
        assert abs(stats["x"]["min"] - 1.0) < 0.01
        assert abs(stats["x"]["max"] - 5.0) < 0.01
