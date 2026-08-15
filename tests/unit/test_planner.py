"""Tests for the planner agent."""

from unittest.mock import MagicMock

from src.agents.planner import create_planner_node
from src.graph.state import AnalysisPlan, AnalystState


class TestPlannerNode:
    def test_returns_plan(self, mock_llm):
        mock_plan = AnalysisPlan(
            question="Top products?",
            sub_questions=["Revenue per product"],
            required_tables=["products", "order_items"],
            analysis_type="ranking",
            suggested_visualizations=["bar"],
        )
        mock_llm.with_structured_output.return_value.invoke.return_value = mock_plan

        node = create_planner_node(mock_llm)
        state = AnalystState(
            question="Top products?",
            schema_summary="Table: products (id, name)",
        )
        result = node(state)

        assert "plan" in result
        assert result["plan"].analysis_type == "ranking"
        assert "products" in result["plan"].required_tables

    def test_calls_llm_with_schema(self, mock_llm):
        mock_plan = AnalysisPlan(question="test")
        mock_llm.with_structured_output.return_value.invoke.return_value = mock_plan

        node = create_planner_node(mock_llm)
        state = AnalystState(
            question="Test?",
            schema_summary="Schema here",
        )
        node(state)

        call_args = mock_llm.with_structured_output.return_value.invoke.call_args
        messages = call_args[0][0]
        assert "Schema here" in messages[1].content

    def test_structured_output_called_with_plan_type(self, mock_llm):
        mock_plan = AnalysisPlan()
        mock_llm.with_structured_output.return_value.invoke.return_value = mock_plan

        node = create_planner_node(mock_llm)
        node(AnalystState(question="test"))

        mock_llm.with_structured_output.assert_called_once_with(AnalysisPlan)
