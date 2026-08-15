"""Tests for the SQL agent."""

from unittest.mock import MagicMock

import pytest

from src.agents.sql_agent import create_sql_agent_node, create_sql_error_handler_node
from src.graph.state import AnalysisPlan, AnalystState, QueryResult


class TestSqlAgentNode:
    def test_successful_query(self, mock_llm, mock_db_pool):
        mock_llm.invoke.return_value = MagicMock(content="SELECT id, name FROM products")
        mock_db_pool.execute_query.return_value = (
            [{"id": 1, "name": "Product A"}],
            ["id", "name"],
        )

        node = create_sql_agent_node(mock_llm, mock_db_pool)
        state = AnalystState(
            question="List products",
            schema_summary="Table: products",
            plan=AnalysisPlan(question="List products", required_tables=["products"]),
        )
        result = node(state)

        assert "query_result" in result
        assert result["query_result"].row_count == 1
        assert result["query_result"].error == ""

    def test_query_execution_error(self, mock_llm, mock_db_pool):
        mock_llm.invoke.return_value = MagicMock(content="SELECT bad_col FROM products")
        mock_db_pool.execute_query.side_effect = Exception("column not found")

        node = create_sql_agent_node(mock_llm, mock_db_pool)
        state = AnalystState(
            question="test",
            plan=AnalysisPlan(question="test"),
        )
        result = node(state)

        assert result["query_result"].error == "column not found"
        assert len(result["errors"]) == 1

    def test_strips_markdown_fences(self, mock_llm, mock_db_pool):
        mock_llm.invoke.return_value = MagicMock(content="```sql\nSELECT 1\n```")
        mock_db_pool.execute_query.return_value = ([{"?column?": 1}], ["?column?"])

        node = create_sql_agent_node(mock_llm, mock_db_pool)
        state = AnalystState(question="test", plan=AnalysisPlan(question="test"))
        result = node(state)

        assert "```" not in result["query_result"].sql


class TestSqlErrorHandlerNode:
    def test_retry_increments_count(self, mock_llm, mock_db_pool):
        mock_llm.invoke.return_value = MagicMock(content="SELECT 1")
        mock_db_pool.execute_query.return_value = ([{"v": 1}], ["v"])

        node = create_sql_error_handler_node(mock_llm, mock_db_pool)
        state = AnalystState(
            question="test",
            plan=AnalysisPlan(question="test"),
            query_result=QueryResult(sql="bad sql", error="syntax error"),
            sql_retry_count=0,
        )
        result = node(state)

        assert result["sql_retry_count"] == 1

    def test_retry_with_error_context(self, mock_llm, mock_db_pool):
        mock_llm.invoke.return_value = MagicMock(content="SELECT 1")
        mock_db_pool.execute_query.return_value = ([{"v": 1}], ["v"])

        node = create_sql_error_handler_node(mock_llm, mock_db_pool)
        state = AnalystState(
            query_result=QueryResult(sql="SELECT bad", error="column missing"),
            plan=AnalysisPlan(question="test"),
        )
        node(state)

        call_args = mock_llm.invoke.call_args[0][0]
        assert "column missing" in call_args[1].content
