"""Tests for Hugging Face text-to-SQL dataset normalization."""

import pytest

from evals.huggingface_loader import (
    infer_tables_from_sql,
    normalize_hf_sql_row,
    resolve_hf_preset,
    rows_to_eval_cases,
)


def test_normalize_bird_style_row():
    row = {
        "question": "Which customers placed orders?",
        "SQL": "SELECT c.name FROM customers c JOIN orders o ON c.id = o.customer_id",
        "db_id": "ecommerce",
        "evidence": "join customers to orders",
    }
    case = normalize_hf_sql_row(row)
    assert case.question == "Which customers placed orders?"
    assert case.expected_sql.startswith("SELECT")
    assert case.tables[:3] == ["ecommerce", "customers", "orders"]
    assert case.metadata["db_id"] == "ecommerce"
    assert case.metadata["source"] == "huggingface"


def test_normalize_spider_style_row():
    row = {
        "question": "Count products",
        "query": "SELECT COUNT(*) FROM products",
        "difficulty": "easy",
    }
    case = normalize_hf_sql_row(row)
    assert case.difficulty == "easy"
    assert case.tables == ["products"]


def test_rows_to_eval_cases_skips_malformed_rows():
    rows = [
        {"question": "Count products", "query": "SELECT COUNT(*) FROM products"},
        {"question": "Missing SQL"},
    ]
    cases = rows_to_eval_cases(rows)
    assert len(cases) == 1


def test_infer_tables_from_sql_handles_joins():
    tables = infer_tables_from_sql(
        "SELECT * FROM public.customers c JOIN orders o ON c.id = o.customer_id"
    )
    assert tables == ["customers", "orders"]


def test_resolve_hf_preset():
    preset = resolve_hf_preset("bird")
    assert preset["repo"] == "birdsql/bird23-train-filtered"
    with pytest.raises(ValueError):
        resolve_hf_preset("unknown")
