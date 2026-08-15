"""Tests for the visualizer agent."""

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from src.agents.visualizer import ChartSpec, ChartSpecs, create_visualizer_node
from src.graph.state import AnalysisPlan, AnalysisResult, AnalystState, QueryResult


class TestVisualizerNode:
    def test_generates_chart(self, mock_llm):
        specs = ChartSpecs(
            charts=[
                ChartSpec(chart_type="bar", x_column="name", y_column="revenue", title="Test Bar")
            ]
        )
        mock_llm.with_structured_output.return_value.invoke.return_value = specs

        with tempfile.TemporaryDirectory() as tmpdir:
            node = create_visualizer_node(mock_llm, output_dir=tmpdir)
            state = AnalystState(
                question="test",
                plan=AnalysisPlan(suggested_visualizations=["bar"]),
                query_result=QueryResult(
                    sql="SELECT 1",
                    columns=["name", "revenue"],
                    rows=[
                        {"name": "A", "revenue": 100},
                        {"name": "B", "revenue": 200},
                    ],
                    row_count=2,
                ),
                analysis=AnalysisResult(insights=["test insight"]),
            )
            result = node(state)

            assert len(result["charts"]) == 1
            assert os.path.exists(result["charts"][0].path)
            assert result["charts"][0].chart_type == "bar"

    def test_no_data_returns_empty(self, mock_llm):
        node = create_visualizer_node(mock_llm)
        state = AnalystState(
            query_result=QueryResult(sql="test", error="failed"),
        )
        result = node(state)

        assert result["charts"] == []

    def test_invalid_columns_skipped(self, mock_llm):
        specs = ChartSpecs(
            charts=[
                ChartSpec(
                    chart_type="bar",
                    x_column="nonexistent",
                    y_column="also_nonexistent",
                    title="Bad Chart",
                )
            ]
        )
        mock_llm.with_structured_output.return_value.invoke.return_value = specs

        with tempfile.TemporaryDirectory() as tmpdir:
            node = create_visualizer_node(mock_llm, output_dir=tmpdir)
            state = AnalystState(
                question="test",
                plan=AnalysisPlan(),
                query_result=QueryResult(
                    sql="SELECT 1",
                    columns=["name", "value"],
                    rows=[{"name": "A", "value": 1}],
                    row_count=1,
                ),
                analysis=AnalysisResult(),
            )
            result = node(state)

            assert len(result["charts"]) == 0
