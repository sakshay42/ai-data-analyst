"""Conditional routing functions for the LangGraph state machine."""

from __future__ import annotations

from src.graph.state import AnalystState

MAX_SQL_RETRIES = 2


def route_after_sql(state: AnalystState) -> str:
    """Route after SQL execution: error → retry/reporter, empty → reporter, success → analyst."""
    qr = state.query_result

    if qr.error:
        if state.sql_retry_count < MAX_SQL_RETRIES:
            return "sql_error_handler"
        return "reporter"  # retries exhausted

    if qr.row_count == 0:
        return "reporter"  # partial report with no data

    return "analyst"
