"""Tests for live SQL prediction generation helpers."""

from dataclasses import dataclass

from evals.generate_sql_predictions import (
    clean_sql_response,
    generate_sql_for_case,
    run_live_sql_benchmark,
    schema_context_for_case,
)
from evals.local_runner import load_dataset


@dataclass
class FakeResponse:
    content: str


class FakeLLM:
    def invoke(self, messages):
        return FakeResponse("```sql\nSELECT name, email FROM customers;\n```")


def test_clean_sql_response_removes_markdown_fences():
    assert clean_sql_response("```sql\nSELECT 1\n```") == "SELECT 1;"


def test_schema_context_for_local_case_contains_tables():
    case = load_dataset("sql_generation")[0]
    context = schema_context_for_case(case, source="local")
    assert "customers" in context
    assert "orders.customer_id" in context


def test_generate_sql_for_case_uses_llm_response():
    case = load_dataset("sql_generation")[0]
    sql = generate_sql_for_case(case, FakeLLM())
    assert sql == "SELECT name, email FROM customers;"


def test_run_live_sql_benchmark_with_fake_llm_creates_artifacts(tmp_path):
    payload = run_live_sql_benchmark(
        limit=1,
        output_dir=str(tmp_path),
        llm=FakeLLM(),
        model="fake-model",
    )
    assert payload["model"] == "fake-model"
    assert payload["summary"]["case_count"] == 16
    assert tmp_path.joinpath("predictions.json").exists()
    assert tmp_path.joinpath("live_sql_benchmark_report.md").exists()


def test_run_live_sql_benchmark_can_enable_execution(tmp_path):
    payload = run_live_sql_benchmark(
        limit=1,
        output_dir=str(tmp_path),
        llm=FakeLLM(),
        model="fake-model",
        execution=True,
    )
    assert payload["execution_enabled"] is True
    assert payload["summary"]["execution_accuracy"] is not None
