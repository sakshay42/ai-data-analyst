"""Tests for Pydantic state models."""

import pytest

from src.graph.state import (
    AnalysisPlan,
    AnalysisResult,
    AnalystState,
    ChartArtifact,
    QueryResult,
)


class TestAnalysisPlan:
    def test_default_values(self):
        plan = AnalysisPlan()
        assert plan.question == ""
        assert plan.sub_questions == []
        assert plan.required_tables == []
        assert plan.analysis_type == ""
        assert plan.suggested_visualizations == []

    def test_populated(self):
        plan = AnalysisPlan(
            question="Top products?",
            sub_questions=["Revenue by product"],
            required_tables=["products"],
            analysis_type="ranking",
            suggested_visualizations=["bar"],
        )
        assert plan.question == "Top products?"
        assert len(plan.sub_questions) == 1


class TestQueryResult:
    def test_default_values(self):
        qr = QueryResult()
        assert qr.sql == ""
        assert qr.columns == []
        assert qr.rows == []
        assert qr.row_count == 0
        assert qr.error == ""

    def test_with_error(self):
        qr = QueryResult(sql="SELECT bad", error="syntax error")
        assert qr.error == "syntax error"

    def test_with_data(self):
        qr = QueryResult(
            sql="SELECT 1",
            columns=["id"],
            rows=[{"id": 1}],
            row_count=1,
        )
        assert qr.row_count == 1


class TestAnalysisResult:
    def test_default_values(self):
        ar = AnalysisResult()
        assert ar.summary_stats == {}
        assert ar.correlations == {}
        assert ar.tests == []
        assert ar.trends == {}
        assert ar.insights == []

    def test_with_insights(self):
        ar = AnalysisResult(insights=["Revenue is growing"])
        assert len(ar.insights) == 1


class TestChartArtifact:
    def test_default_values(self):
        ca = ChartArtifact()
        assert ca.path == ""
        assert ca.chart_type == ""

    def test_populated(self):
        ca = ChartArtifact(
            path="/tmp/chart.png",
            chart_type="bar",
            title="Test",
            description="A test chart",
        )
        assert ca.path == "/tmp/chart.png"


class TestAnalystState:
    def test_default_values(self):
        state = AnalystState()
        assert state.question == ""
        assert state.schema_summary == ""
        assert state.sql_retry_count == 0
        assert state.report == ""
        assert state.errors == []

    def test_errors_list_default(self):
        state = AnalystState()
        assert isinstance(state.errors, list)

    def test_full_state(self, sample_state):
        assert sample_state.question == "What are the top 5 products by revenue?"
        assert sample_state.query_result.row_count == 5
        assert len(sample_state.charts) == 1
        assert sample_state.plan.analysis_type == "ranking"
