"""SQL evaluation scorers for syntax validity, correctness, and efficiency."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import sqlparse


@dataclass
class ScorerResult:
    """Standard result returned by all scorers."""

    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


class SQLValidity:
    """Check that generated SQL is syntactically valid using sqlparse.

    Validates:
    - The string parses without error
    - Contains at least one SQL statement
    - The primary statement type is SELECT (no DDL / DML mutations)
    """

    ALLOWED_STATEMENT_TYPES = {"SELECT"}

    def score(self, sql: str) -> ScorerResult:
        """Score the syntactic validity of a SQL string.

        Args:
            sql: The SQL query string to validate.

        Returns:
            ScorerResult with score 1.0 if valid, 0.0 otherwise.
        """
        if not sql or not sql.strip():
            return ScorerResult(
                name="sql_validity",
                score=0.0,
                passed=False,
                details={"error": "Empty SQL string"},
            )

        try:
            parsed = sqlparse.parse(sql)
        except Exception as exc:
            return ScorerResult(
                name="sql_validity",
                score=0.0,
                passed=False,
                details={"error": f"Parse error: {exc}"},
            )

        if not parsed:
            return ScorerResult(
                name="sql_validity",
                score=0.0,
                passed=False,
                details={"error": "No statements found after parsing"},
            )

        # Check statement type of the first (primary) statement
        stmt = parsed[0]
        stmt_type = stmt.get_type()

        if stmt_type and stmt_type.upper() not in self.ALLOWED_STATEMENT_TYPES:
            return ScorerResult(
                name="sql_validity",
                score=0.0,
                passed=False,
                details={"error": f"Disallowed statement type: {stmt_type}"},
            )

        # Check for obviously dangerous keywords
        dangerous_keywords = {"DROP", "TRUNCATE", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE"}
        tokens_upper = sql.upper()
        found_dangerous = [kw for kw in dangerous_keywords if re.search(rf"\b{kw}\b", tokens_upper)]
        if found_dangerous:
            return ScorerResult(
                name="sql_validity",
                score=0.0,
                passed=False,
                details={"error": f"Dangerous keywords found: {found_dangerous}"},
            )

        return ScorerResult(
            name="sql_validity",
            score=1.0,
            passed=True,
            details={"statement_type": stmt_type, "num_statements": len(parsed)},
        )


class SQLCorrectness:
    """Compare actual query output rows against expected rows.

    Accepts a database connection (or callable that executes SQL and returns rows)
    to run the generated SQL and compare results against expected output.
    """

    def __init__(self, execute_fn: Any = None):
        """Initialize with an optional execute function.

        Args:
            execute_fn: Callable that takes a SQL string and returns
                        (rows: list[dict], columns: list[str]).
                        If None, score() requires rows to be passed directly.
        """
        self.execute_fn = execute_fn

    def score(
        self,
        sql: str,
        expected_rows: list[dict[str, Any]] | None = None,
        actual_rows: list[dict[str, Any]] | None = None,
    ) -> ScorerResult:
        """Score correctness by comparing actual vs expected result rows.

        Either provide actual_rows directly, or let the scorer execute the SQL
        via the configured execute_fn.

        Args:
            sql: The generated SQL query.
            expected_rows: The ground-truth result rows.
            actual_rows: Pre-computed actual rows (skip execution if provided).

        Returns:
            ScorerResult with score between 0.0 and 1.0.
        """
        if expected_rows is None:
            return ScorerResult(
                name="sql_correctness",
                score=0.0,
                passed=False,
                details={"error": "No expected_rows provided"},
            )

        # Get actual rows
        if actual_rows is None:
            if self.execute_fn is None:
                return ScorerResult(
                    name="sql_correctness",
                    score=0.0,
                    passed=False,
                    details={"error": "No execute_fn or actual_rows provided"},
                )
            try:
                actual_rows, _ = self.execute_fn(sql)
            except Exception as exc:
                return ScorerResult(
                    name="sql_correctness",
                    score=0.0,
                    passed=False,
                    details={"error": f"Execution failed: {exc}"},
                )

        # Row count match
        expected_count = len(expected_rows)
        actual_count = len(actual_rows)

        if expected_count == 0 and actual_count == 0:
            return ScorerResult(
                name="sql_correctness",
                score=1.0,
                passed=True,
                details={"matched": 0, "total": 0},
            )

        if expected_count == 0 or actual_count == 0:
            return ScorerResult(
                name="sql_correctness",
                score=0.0,
                passed=False,
                details={
                    "expected_count": expected_count,
                    "actual_count": actual_count,
                    "error": "Row count mismatch (one side is empty)",
                },
            )

        # Normalize rows for comparison: lowercase keys, stringify values
        def normalize(rows: list[dict]) -> list[dict[str, str]]:
            return [
                {str(k).lower().strip(): str(v).strip() for k, v in row.items()}
                for row in rows
            ]

        norm_expected = normalize(expected_rows)
        norm_actual = normalize(actual_rows)

        # Match rows (order-insensitive)
        matched = 0
        unmatched_actual = list(norm_actual)
        for exp_row in norm_expected:
            for i, act_row in enumerate(unmatched_actual):
                if exp_row == act_row:
                    matched += 1
                    unmatched_actual.pop(i)
                    break

        total = max(expected_count, actual_count)
        score = matched / total if total > 0 else 0.0
        passed = score >= 0.8  # 80% threshold

        return ScorerResult(
            name="sql_correctness",
            score=round(score, 4),
            passed=passed,
            details={
                "matched": matched,
                "expected_count": expected_count,
                "actual_count": actual_count,
            },
        )


class SQLEfficiency:
    """Detect common SQL anti-patterns that indicate inefficient queries.

    Checks for:
    - SELECT * usage (should specify columns)
    - Missing WHERE clause on large-table queries
    - Missing LIMIT on unbounded queries
    - Cartesian joins (comma-separated FROM without JOIN or WHERE)
    - Nested subqueries where CTEs would be clearer (informational)
    """

    # Tables considered "large" that should have WHERE / LIMIT clauses
    LARGE_TABLES = {"orders", "order_items", "reviews", "customers", "products"}

    ANTI_PATTERNS = [
        {
            "name": "select_star",
            "pattern": r"\bSELECT\s+\*\b",
            "message": "SELECT * detected - prefer explicit column names",
            "severity": 0.15,
        },
        {
            "name": "cartesian_join",
            "pattern": r"\bFROM\s+\w+\s*,\s*\w+\b",
            "message": "Possible Cartesian join - use explicit JOIN syntax",
            "severity": 0.25,
        },
        {
            "name": "select_distinct_star",
            "pattern": r"\bSELECT\s+DISTINCT\s+\*\b",
            "message": "SELECT DISTINCT * is almost always a mistake",
            "severity": 0.30,
        },
    ]

    def score(self, sql: str, tables: list[str] | None = None) -> ScorerResult:
        """Score the efficiency of a SQL query.

        Args:
            sql: The SQL query string.
            tables: List of tables referenced (used for large-table checks).

        Returns:
            ScorerResult with score 1.0 (no issues) decremented by severity per issue.
        """
        if not sql or not sql.strip():
            return ScorerResult(
                name="sql_efficiency",
                score=0.0,
                passed=False,
                details={"error": "Empty SQL string"},
            )

        issues: list[dict[str, str]] = []
        penalty = 0.0
        sql_upper = sql.upper()

        # Check regex-based anti-patterns
        for ap in self.ANTI_PATTERNS:
            if re.search(ap["pattern"], sql, re.IGNORECASE):
                issues.append({"name": ap["name"], "message": ap["message"]})
                penalty += ap["severity"]

        # Check for missing WHERE on large tables
        if tables:
            large_tables_used = [t for t in tables if t.lower() in self.LARGE_TABLES]
            if large_tables_used and "WHERE" not in sql_upper:
                has_group_by = "GROUP BY" in sql_upper
                has_limit = "LIMIT" in sql_upper
                if not has_group_by and not has_limit:
                    issues.append({
                        "name": "missing_where_on_large_table",
                        "message": (
                            f"No WHERE or LIMIT on large table(s): {large_tables_used}"
                        ),
                    })
                    penalty += 0.20

        # Check for deeply nested subqueries (more than 2 levels of SELECT)
        select_count = len(re.findall(r"\bSELECT\b", sql_upper))
        if select_count > 3:
            issues.append({
                "name": "deep_nesting",
                "message": f"Deeply nested query ({select_count} SELECT statements) - consider CTEs",
            })
            penalty += 0.10

        score = max(0.0, 1.0 - penalty)
        passed = score >= 0.6

        return ScorerResult(
            name="sql_efficiency",
            score=round(score, 4),
            passed=passed,
            details={"issues": issues, "total_penalty": round(penalty, 4)},
        )
