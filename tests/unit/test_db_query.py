"""Tests for the db_query tool."""

from unittest.mock import MagicMock

import pytest

from src.tools.db_query import create_db_query_tool


class TestDbQueryTool:
    def setup_method(self):
        self.pool = MagicMock()
        self.pool.execute_query.return_value = (
            [{"id": 1, "name": "Test"}],
            ["id", "name"],
        )
        self.tool = create_db_query_tool(self.pool)

    def test_valid_select(self):
        result = self.tool.invoke({"sql": "SELECT id, name FROM products"})
        assert result["row_count"] == 1
        assert result["columns"] == ["id", "name"]

    def test_valid_cte(self):
        result = self.tool.invoke({"sql": "WITH cte AS (SELECT 1) SELECT * FROM cte"})
        assert "error" not in result

    def test_blocks_insert(self):
        result = self.tool.invoke({"sql": "INSERT INTO products VALUES (1, 'bad')"})
        assert "error" in result
        assert "Only SELECT" in result["error"]

    def test_blocks_delete(self):
        result = self.tool.invoke({"sql": "DELETE FROM products"})
        assert "error" in result

    def test_blocks_drop(self):
        result = self.tool.invoke({"sql": "SELECT 1; DROP TABLE products"})
        assert "error" in result
        assert "Forbidden" in result["error"]

    def test_blocks_update(self):
        result = self.tool.invoke({"sql": "UPDATE products SET name = 'x'"})
        assert "error" in result

    def test_handles_execution_error(self):
        self.pool.execute_query.side_effect = Exception("connection refused")
        result = self.tool.invoke({"sql": "SELECT 1"})
        assert result["error"] == "connection refused"

    def test_strips_semicolons(self):
        self.tool.invoke({"sql": "SELECT 1;"})
        call_args = self.pool.execute_query.call_args[0][0]
        assert not call_args.endswith(";")
