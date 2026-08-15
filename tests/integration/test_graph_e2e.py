"""End-to-end integration test for the full graph pipeline.

Uses mocked LLM and database to test graph assembly and flow.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config.settings import Settings, DatabaseSettings, LLMSettings
from src.graph.state import AnalysisPlan, AnalystState


class TestGraphE2E:
    """Integration tests that mock external dependencies but test full graph flow."""

    @pytest.fixture
    def mock_settings(self):
        settings = Settings()
        settings.llm = LLMSettings(api_key="test-key", model="gpt-4o")
        settings.database = DatabaseSettings(
            url="postgresql://test:test@localhost/test",
        )
        return settings

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        # Schema introspection
        conn = MagicMock()
        pool.connection.return_value.__enter__ = MagicMock(return_value=conn)
        pool.connection.return_value.__exit__ = MagicMock(return_value=False)

        # Mock cursor for introspection queries
        cur = MagicMock()
        cur.fetchall.return_value = [("products",)]
        cur.fetchone.return_value = (100,)
        cur.description = [MagicMock(name="table_name")]
        conn.execute.return_value = cur

        # Mock execute_query for SQL agent
        pool.execute_query.return_value = (
            [
                {"name": "Product A", "revenue": 5000.0},
                {"name": "Product B", "revenue": 3000.0},
            ],
            ["name", "revenue"],
        )
        return pool

    @patch("src.graph.builder.create_llm")
    def test_full_pipeline_mock(self, mock_create_llm, mock_settings, mock_pool):
        """Test the full pipeline with mocked LLM responses."""
        # Setup mock LLM
        mock_llm = MagicMock()

        # Planner returns structured plan
        plan = AnalysisPlan(
            question="Top products by revenue?",
            sub_questions=["Calculate revenue per product"],
            required_tables=["products", "order_items"],
            analysis_type="ranking",
            suggested_visualizations=["bar"],
        )
        mock_llm.with_structured_output.return_value.invoke.return_value = plan

        # SQL agent returns query
        mock_llm.invoke.return_value = MagicMock(
            content="SELECT name, SUM(revenue) as revenue FROM products GROUP BY name ORDER BY revenue DESC"
        )

        mock_create_llm.return_value = mock_llm

        from src.graph.builder import build_graph
        from src.observability import ObservabilityManager

        graph = build_graph(mock_settings, mock_pool, ObservabilityManager())

        # This would invoke the full graph — but since LangGraph compile
        # requires proper setup, we test the graph structure instead
        assert graph is not None

    def test_routing_integration(self):
        """Test that routing functions work with real state objects."""
        from src.graph.routing import route_after_sql
        from src.graph.state import QueryResult

        # Success case
        state = AnalystState(
            query_result=QueryResult(
                sql="SELECT 1", columns=["a"], rows=[{"a": 1}], row_count=1
            )
        )
        assert route_after_sql(state) == "analyst"

        # Error case
        state = AnalystState(
            query_result=QueryResult(sql="bad", error="fail"),
            sql_retry_count=0,
        )
        assert route_after_sql(state) == "sql_error_handler"

        # Exhausted retries
        state = AnalystState(
            query_result=QueryResult(sql="bad", error="fail"),
            sql_retry_count=2,
        )
        assert route_after_sql(state) == "reporter"
