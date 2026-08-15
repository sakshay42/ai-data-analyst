"""Database schema introspection via information_schema and pg_catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.db.connection import DatabasePool


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    column_default: str | None = None
    is_primary_key: bool = False


@dataclass
class TableInfo:
    schema: str
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count_estimate: int = 0


class SchemaIntrospector:
    """Introspect PostgreSQL schema metadata."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    def get_tables(self, schema: str = "public") -> list[TableInfo]:
        """Return all tables with columns and estimated row counts."""
        tables: list[TableInfo] = []
        with self._pool.connection() as conn:
            # Get tables
            cur = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                (schema,),
            )
            table_names = [row[0] for row in cur.fetchall()]

            for tname in table_names:
                table = TableInfo(schema=schema, name=tname)

                # Get columns
                cur = conn.execute(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, tname),
                )
                for row in cur.fetchall():
                    table.columns.append(
                        ColumnInfo(
                            name=row[0],
                            data_type=row[1],
                            is_nullable=row[2] == "YES",
                            column_default=row[3],
                        )
                    )

                # Get primary keys
                cur = conn.execute(
                    """
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    JOIN pg_class c ON c.oid = i.indrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE i.indisprimary AND c.relname = %s AND n.nspname = %s
                    """,
                    (tname, schema),
                )
                pk_names = {row[0] for row in cur.fetchall()}
                for col in table.columns:
                    col.is_primary_key = col.name in pk_names

                # Estimated row count
                cur = conn.execute(
                    """
                    SELECT reltuples::bigint
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = %s AND n.nspname = %s
                    """,
                    (tname, schema),
                )
                row = cur.fetchone()
                table.row_count_estimate = max(0, row[0]) if row else 0

                tables.append(table)

        return tables

    def get_schema_summary(self, schema: str = "public") -> str:
        """Return a text summary of the database schema suitable for LLM context."""
        tables = self.get_tables(schema)
        lines: list[str] = [f"Database schema '{schema}':\n"]
        for t in tables:
            lines.append(f"Table: {t.name} (~{t.row_count_estimate} rows)")
            for c in t.columns:
                pk = " [PK]" if c.is_primary_key else ""
                nullable = " NULL" if c.is_nullable else " NOT NULL"
                lines.append(f"  - {c.name}: {c.data_type}{nullable}{pk}")
            lines.append("")
        return "\n".join(lines)

    def get_sample_values(
        self, table: str, column: str, limit: int = 10, schema: str = "public"
    ) -> list[Any]:
        """Return sample distinct values from a column."""
        with self._pool.connection() as conn:
            cur = conn.execute(
                f"SELECT DISTINCT {column} FROM {schema}.{table} LIMIT %s",  # noqa: S608
                (limit,),
            )
            return [row[0] for row in cur.fetchall()]
