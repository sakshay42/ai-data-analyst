"""Hugging Face text-to-SQL dataset adapters.

The adapter normalizes public benchmark rows, such as BIRD or Spider variants,
into the project's EvalCase shape. Runtime loading uses streaming by default so
small eval samples do not require downloading full datasets.
"""

from __future__ import annotations

import re
from itertools import islice
from typing import Any, Iterable

from evals.local_runner import EvalCase

DEFAULT_HF_TEXT2SQL_DATASETS = {
    "bird": {
        "repo": "birdsql/bird23-train-filtered",
        "split": "train",
        "description": "BIRD text-to-SQL training subset.",
    },
    "bird-chat": {
        "repo": "lianghsun/bird-text2sql-bench",
        "split": "train",
        "description": "BIRD formatted as chat-style text-to-SQL examples.",
    },
}

QUESTION_KEYS = ("question", "input", "prompt", "utterance", "natural_language")
SQL_KEYS = ("SQL", "sql", "query", "gold_sql", "expected_sql", "target", "answer")
DIFFICULTY_KEYS = ("difficulty", "difficulty_level", "hardness")
TABLE_KEYS = ("tables", "table_names", "required_tables")
DB_KEYS = ("db_id", "database_id", "database")


def _first_string(row: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def infer_tables_from_sql(sql: str) -> list[str]:
    """Extract table names after FROM/JOIN clauses with lightweight parsing."""
    matches = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)(?:\s+as)?\b", sql, flags=re.I)
    tables = []
    for match in matches:
        table = match.split(".")[-1].strip('"')
        if table and table.lower() not in {"select", "where"} and table not in tables:
            tables.append(table)
    return tables


def normalize_hf_sql_row(row: dict[str, Any], index: int = 0) -> EvalCase:
    """Convert one Hugging Face row into an EvalCase."""
    question = _first_string(row, QUESTION_KEYS)
    expected_sql = _first_string(row, SQL_KEYS)
    if not question or not expected_sql:
        raise ValueError(
            f"Could not normalize Hugging Face row {index}; expected question and SQL fields."
        )

    difficulty = _first_string(row, DIFFICULTY_KEYS) or "external"
    tables_value = next((row.get(key) for key in TABLE_KEYS if row.get(key)), None)
    if isinstance(tables_value, str):
        tables = [part.strip() for part in re.split(r"[,|]", tables_value) if part.strip()]
    elif isinstance(tables_value, list):
        tables = [str(part) for part in tables_value if str(part).strip()]
    else:
        tables = infer_tables_from_sql(expected_sql)

    db_id = _first_string(row, DB_KEYS)
    if db_id and db_id not in tables:
        tables = [db_id, *tables]

    metadata = {"source": "huggingface", "row_index": index}
    for key in ("db_id", "evidence", "context", "schema", "dataset"):
        if key in row and row[key] not in (None, ""):
            metadata[key] = row[key]

    return EvalCase(
        question=question,
        expected_sql=expected_sql,
        difficulty=difficulty,
        tables=tables,
        metadata=metadata,
    )


def rows_to_eval_cases(rows: Iterable[dict[str, Any]], limit: int | None = None) -> list[EvalCase]:
    """Normalize iterable rows into eval cases, skipping malformed rows."""
    selected_rows = islice(rows, limit) if limit is not None else rows
    cases: list[EvalCase] = []
    for index, row in enumerate(selected_rows):
        try:
            cases.append(normalize_hf_sql_row(dict(row), index=index))
        except ValueError:
            continue
    return cases


def load_huggingface_sql_dataset(
    repo: str,
    split: str = "train",
    limit: int = 50,
    config: str | None = None,
    streaming: bool = True,
) -> list[EvalCase]:
    """Load and normalize a small text-to-SQL sample from Hugging Face."""
    try:
        from datasets import load_dataset as hf_load_dataset
    except ImportError as exc:
        raise RuntimeError(
            "Hugging Face datasets is not installed. Run `uvx poetry install` first."
        ) from exc

    kwargs: dict[str, Any] = {"split": split, "streaming": streaming}
    if config:
        dataset = hf_load_dataset(repo, config, **kwargs)
    else:
        dataset = hf_load_dataset(repo, **kwargs)
    return rows_to_eval_cases(dataset, limit=limit)


def resolve_hf_preset(name: str) -> dict[str, str]:
    """Resolve a known text-to-SQL benchmark preset."""
    if name not in DEFAULT_HF_TEXT2SQL_DATASETS:
        available = ", ".join(sorted(DEFAULT_HF_TEXT2SQL_DATASETS))
        raise ValueError(f"Unknown Hugging Face preset '{name}'. Available: {available}")
    return DEFAULT_HF_TEXT2SQL_DATASETS[name]
