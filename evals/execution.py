"""Execution-based SQL correctness checks for bundled eval cases."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionScorerResult:
    """Result of running generated SQL against expected SQL on the same fixture."""

    score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


def create_ecommerce_eval_connection() -> sqlite3.Connection:
    """Create a deterministic in-memory database for bundled SQL eval cases."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            total_amount REAL NOT NULL
        );
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            rating REAL NOT NULL
        );
        """
    )
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?)",
        [
            (1, "Ada Lovelace", "ada@example.com"),
            (2, "Grace Hopper", "grace@example.com"),
            (3, "Katherine Johnson", "katherine@example.com"),
            (4, "Mary Jackson", "mary@example.com"),
            (5, "Dorothy Vaughan", "dorothy@example.com"),
            (6, "Alan Turing", "alan@example.com"),
        ],
    )
    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?)",
        [
            (1, "Laptop", "Electronics", 1200.0),
            (2, "Headphones", "Electronics", 150.0),
            (3, "Desk Lamp", "Home", 45.0),
            (4, "Novel", "Books", 18.0),
            (5, "Coffee Maker", "Home", 90.0),
            (6, "Tablet", "Electronics", 500.0),
        ],
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?)",
        [
            (1, 1, "2024-01-05", 1200.0),
            (2, 1, "2024-02-10", 300.0),
            (3, 1, "2024-03-15", 150.0),
            (4, 1, "2024-04-20", 90.0),
            (5, 2, "2024-01-18", 500.0),
            (6, 2, "2024-02-22", 45.0),
            (7, 3, "2024-03-03", 210.0),
            (8, 3, "2024-03-21", 75.0),
            (9, 4, "2024-04-12", 18.0),
            (10, 5, "2024-05-09", 1500.0),
            (11, 5, "2024-06-11", 120.0),
            (12, 6, "2024-07-01", 60.0),
        ],
    )
    conn.executemany(
        "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, 1, 1, 1200.0),
            (2, 2, 2, 2, 150.0),
            (3, 3, 2, 1, 150.0),
            (4, 4, 5, 1, 90.0),
            (5, 5, 6, 1, 500.0),
            (6, 6, 3, 1, 45.0),
            (7, 7, 2, 1, 150.0),
            (8, 7, 4, 3, 20.0),
            (9, 8, 3, 1, 75.0),
            (10, 9, 4, 1, 18.0),
            (11, 10, 1, 1, 1200.0),
            (12, 10, 6, 1, 300.0),
            (13, 11, 5, 2, 60.0),
            (14, 12, 3, 1, 60.0),
        ],
    )
    conn.executemany(
        "INSERT INTO reviews VALUES (?, ?, ?)",
        [
            (1, 1, 4.8),
            (2, 1, 4.9),
            (3, 1, 4.7),
            (4, 1, 4.6),
            (5, 1, 4.5),
            (6, 2, 4.0),
            (7, 2, 4.2),
            (8, 2, 4.1),
            (9, 2, 4.3),
            (10, 2, 4.4),
            (11, 3, 3.5),
            (12, 3, 3.7),
            (13, 3, 3.6),
            (14, 3, 3.8),
            (15, 3, 3.9),
        ],
    )
    return conn


def translate_postgres_to_sqlite(sql: str) -> str:
    """Translate the small PostgreSQL subset in bundled evals to SQLite."""
    translated = sql.strip().rstrip(";")
    translated = re.sub(
        r"DATE_TRUNC\(\s*'month'\s*,\s*([^)]+?)\s*\)",
        r"substr(\1, 1, 7)",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"CURRENT_DATE\s*-\s*INTERVAL\s*'12 months'",
        "'2024-01-01'",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(r"\bDATE\s*\(([^)]+)\)", r"date(\1)", translated, flags=re.IGNORECASE)
    return translated


def _normalize_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def normalize_rows(rows: list[sqlite3.Row]) -> list[tuple[str, ...]]:
    """Normalize row values for order-sensitive comparison."""
    return [tuple(_normalize_value(value) for value in row) for row in rows]


def execute_sql(conn: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    """Execute translated SQL and return all rows."""
    return conn.execute(translate_postgres_to_sqlite(sql)).fetchall()


def score_sql_execution(actual_sql: str, expected_sql: str) -> ExecutionScorerResult:
    """Compare generated SQL output against expected SQL output."""
    conn = create_ecommerce_eval_connection()
    try:
        expected_rows = normalize_rows(execute_sql(conn, expected_sql))
    except Exception as exc:
        return ExecutionScorerResult(
            score=0.0,
            passed=False,
            details={"error": f"Expected SQL failed on fixture: {exc}"},
        )

    try:
        actual_rows = normalize_rows(execute_sql(conn, actual_sql))
    except Exception as exc:
        return ExecutionScorerResult(
            score=0.0,
            passed=False,
            details={
                "error": f"Generated SQL failed on fixture: {exc}",
                "expected_row_count": len(expected_rows),
            },
        )
    finally:
        conn.close()

    passed = actual_rows == expected_rows
    return ExecutionScorerResult(
        score=1.0 if passed else 0.0,
        passed=passed,
        details={
            "expected_row_count": len(expected_rows),
            "actual_row_count": len(actual_rows),
            "expected_preview": expected_rows[:5],
            "actual_preview": actual_rows[:5],
        },
    )
