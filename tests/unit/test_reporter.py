"""Tests for the reporter agent."""

from unittest.mock import MagicMock

from src.agents.reporter import create_reporter_node
from src.graph.state import (
    AnalysisPlan,
    AnalysisResult,
    AnalystState,
    ChartArtifact,
    QueryResult,
)


class TestReporterNode:
    def test_generates_report(self, mock_llm):
        mock_llm.invoke.return_value = MagicMock(
            content="# Report\n\nExecutive Summary: Revenue is strong."
        )

        node = create_reporter_node(mock_llm)
        state = AnalystState(
            question="Revenue analysis?",
            query_result=QueryResult(sql="SELECT 1", columns=["a"], rows=[{"a": 1}], row_count=1),
            analysis=AnalysisResult(insights=["Revenue growing"]),
            charts=[ChartArtifact(path="chart.png", chart_type="bar", title="Test", description="desc")],
        )
        result = node(state)

        assert "report" in result
        assert "Report" in result["report"]

    def test_includes_question_in_context(self, mock_llm):
        mock_llm.invoke.return_value = MagicMock(content="Report")

        node = create_reporter_node(mock_llm)
        state = AnalystState(
            question="Specific question here",
            query_result=QueryResult(sql="SELECT 1"),
            analysis=AnalysisResult(),
        )
        node(state)

        call_args = mock_llm.invoke.call_args[0][0]
        assert "Specific question here" in call_args[1].content

    def test_handles_errors_in_state(self, mock_llm):
        mock_llm.invoke.return_value = MagicMock(content="Report with errors noted")

        node = create_reporter_node(mock_llm)
        state = AnalystState(
            question="test",
            query_result=QueryResult(sql="bad", error="syntax error"),
            analysis=AnalysisResult(),
            errors=["SQL error: syntax error"],
        )
        node(state)

        call_args = mock_llm.invoke.call_args[0][0]
        assert "syntax error" in call_args[1].content
