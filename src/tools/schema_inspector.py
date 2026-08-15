"""Schema inspector tool wrapping the introspection layer."""

from __future__ import annotations

from langchain_core.tools import tool

from src.db.connection import DatabasePool
from src.db.introspect import SchemaIntrospector


def create_schema_inspector_tool(pool: DatabasePool):
    """Create a schema inspector tool bound to a pool."""
    introspector = SchemaIntrospector(pool)

    @tool
    def schema_inspector_tool(action: str = "summary", table: str = "", column: str = "") -> str:
        """Inspect the database schema.

        Args:
            action: One of 'summary' (full schema), 'sample' (sample values for a column).
            table: Table name (required for 'sample' action).
            column: Column name (required for 'sample' action).

        Returns:
            Schema summary or sample values as text.
        """
        if action == "summary":
            return introspector.get_schema_summary()
        elif action == "sample":
            if not table or not column:
                return "Error: 'table' and 'column' are required for 'sample' action."
            values = introspector.get_sample_values(table, column)
            return f"Sample values for {table}.{column}: {values}"
        else:
            return f"Unknown action: {action}. Use 'summary' or 'sample'."

    return schema_inspector_tool
