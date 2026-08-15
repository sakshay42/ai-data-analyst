"""Database query tool for executing read-only SQL."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from loguru import logger

from src.db.connection import DatabasePool


def create_db_query_tool(pool: DatabasePool, max_rows: int = 10_000):
    """Create a db_query tool bound to a specific pool."""

    @tool
    def db_query_tool(sql: str) -> dict[str, Any]:
        """Execute a read-only SQL query against the database.

        Args:
            sql: The SQL query to execute. Must be a SELECT statement.

        Returns:
            Dictionary with 'columns', 'rows', and 'row_count'.
        """
        sql_stripped = sql.strip().rstrip(";")
        upper = sql_stripped.upper()

        # Block non-SELECT statements
        if not upper.startswith("SELECT") and not upper.startswith("WITH"):
            return {"error": "Only SELECT and WITH (CTE) statements are allowed."}

        # Block DDL/DML keywords
        forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT"}
        tokens = set(upper.split())
        if tokens & forbidden:
            return {"error": f"Forbidden SQL keywords detected: {tokens & forbidden}"}

        try:
            rows, columns = pool.execute_query(sql_stripped, max_rows=max_rows)
            logger.info("Query executed: {} rows returned", len(rows))
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
        except Exception as e:
            logger.error("Query failed: {}", str(e))
            return {"error": str(e)}

    return db_query_tool
