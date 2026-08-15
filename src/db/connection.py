"""PostgreSQL connection pool using psycopg3."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from loguru import logger
from psycopg_pool import ConnectionPool

from src.config.settings import DatabaseSettings


class DatabasePool:
    """Manages a psycopg3 connection pool with read-only defaults."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._pool: ConnectionPool | None = None

    def open(self) -> None:
        """Open the connection pool."""
        if self._pool is not None:
            return
        self._pool = ConnectionPool(
            conninfo=self._settings.url,
            min_size=self._settings.pool_min,
            max_size=self._settings.pool_max,
            open=True,
            kwargs={"autocommit": True},
        )
        logger.info(
            "Database pool opened (min={}, max={})",
            self._settings.pool_min,
            self._settings.pool_max,
        )

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None
            logger.info("Database pool closed")

    @contextmanager
    def connection(self) -> Generator:
        """Yield a read-only connection with statement timeout."""
        if self._pool is None:
            self.open()
        with self._pool.connection() as conn:
            conn.execute(
                f"SET statement_timeout = '{self._settings.statement_timeout}'"
            )
            conn.execute("SET default_transaction_read_only = ON")
            yield conn

    def execute_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        max_rows: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Execute a read-only query and return (rows_as_dicts, column_names)."""
        limit = max_rows or self._settings.max_rows
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            columns = [desc.name for desc in cur.description] if cur.description else []
            rows = cur.fetchmany(limit)
            result = [dict(zip(columns, row)) for row in rows]
            logger.debug("Query returned {} rows", len(result))
            return result, columns


_pool: DatabasePool | None = None


def get_pool(settings: DatabaseSettings) -> DatabasePool:
    """Return a singleton database pool."""
    global _pool
    if _pool is None:
        _pool = DatabasePool(settings)
        _pool.open()
    return _pool
