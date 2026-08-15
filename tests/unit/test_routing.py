"""Tests for conditional routing functions."""

import pytest

from src.graph.routing import MAX_SQL_RETRIES, route_after_sql
from src.graph.state import AnalystState, QueryResult


class TestRouteAfterSql:
    def test_success_routes_to_analyst(self):
        state = AnalystState(
            query_result=QueryResult(
                sql="SELECT 1",
                columns=["a"],
                rows=[{"a": 1}],
                row_count=1,
            )
        )
        assert route_after_sql(state) == "analyst"

    def test_error_first_retry(self):
        state = AnalystState(
            query_result=QueryResult(sql="bad", error="syntax error"),
            sql_retry_count=0,
        )
        assert route_after_sql(state) == "sql_error_handler"

    def test_error_second_retry(self):
        state = AnalystState(
            query_result=QueryResult(sql="bad", error="still bad"),
            sql_retry_count=1,
        )
        assert route_after_sql(state) == "sql_error_handler"

    def test_error_retries_exhausted(self):
        state = AnalystState(
            query_result=QueryResult(sql="bad", error="giving up"),
            sql_retry_count=MAX_SQL_RETRIES,
        )
        assert route_after_sql(state) == "reporter"

    def test_empty_result_routes_to_reporter(self):
        state = AnalystState(
            query_result=QueryResult(
                sql="SELECT 1 WHERE false",
                columns=["a"],
                rows=[],
                row_count=0,
            )
        )
        assert route_after_sql(state) == "reporter"
