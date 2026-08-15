"""Tests for MCP helper functions that do not require the MCP SDK runtime."""

from src.mcp_server.server import (
    analyze_rows,
    compare_sql_prediction_runs,
    evaluate_sql_predictions,
    evaluate_sql_predictions_report,
    list_huggingface_eval_presets,
    list_eval_cases,
    project_info,
    read_project_file,
    run_eval_progress_demo,
    run_sql_eval,
    score_sql,
)
from evals.progress_tracker import simulated_current_predictions, simulated_previous_predictions


def test_project_info_lists_entrypoints():
    info = project_info()
    assert info["name"] == "ai-data-analyst"
    assert info["entrypoints"]["mcp_server"] == "src/mcp_server/server.py"
    assert info["entrypoints"]["eval_progress"] == "evals/progress_tracker.py"
    assert info["entrypoints"]["live_sql_benchmark"] == "evals/generate_sql_predictions.py"
    assert "sql_generation" in info["eval_datasets"]


def test_score_sql_blocks_mutation():
    result = score_sql("DROP TABLE customers")
    assert result["passed"] is False
    assert result["validity"]["score"] == 0.0


def test_score_sql_accepts_select():
    result = score_sql("SELECT id, name FROM customers LIMIT 10", tables=["customers"])
    assert result["validity"]["passed"] is True
    assert result["combined_score"] > 0


def test_list_eval_cases_hides_expected_sql():
    cases = list_eval_cases("sql_generation")
    assert cases
    assert "question" in cases[0]
    assert "expected_sql" not in cases[0]


def test_list_huggingface_eval_presets():
    presets = list_huggingface_eval_presets()
    assert "bird" in presets
    assert presets["bird"]["repo"] == "birdsql/bird23-train-filtered"


def test_run_sql_eval_supports_markdown_report():
    report = run_sql_eval("sql_generation", format="markdown")
    assert "# Eval Report: sql_generation" in report


def test_evaluate_sql_predictions_reports_missing_predictions():
    cases = list_eval_cases("sql_generation")
    payload = evaluate_sql_predictions(
        predictions=[{"question": cases[0]["question"], "sql": "SELECT name FROM customers;"}]
    )
    assert payload["mode"] == "mcp_predictions"
    assert payload["summary"]["prediction_coverage"] > 0
    assert payload["missing_predictions"]


def test_evaluate_sql_predictions_markdown_report():
    cases = list_eval_cases("sql_generation")
    report = evaluate_sql_predictions_report(
        predictions=[{"question": cases[0]["question"], "sql": "SELECT name FROM customers;"}]
    )
    assert "Missing Predictions" in report


def test_compare_sql_prediction_runs_returns_progress_summary():
    previous = [
        {"question": question, "sql": sql}
        for question, sql in simulated_previous_predictions().items()
    ]
    current = [
        {"question": question, "sql": sql}
        for question, sql in simulated_current_predictions().items()
    ]
    payload = compare_sql_prediction_runs(previous, current)
    assert payload["summary"]["current_avg_score"] >= payload["summary"]["previous_avg_score"]


def test_run_eval_progress_demo_supports_markdown():
    report = run_eval_progress_demo(format="markdown")
    assert "# Eval Progress Demo" in report
    assert "Fixed cases" in report


def test_analyze_rows_returns_summary_for_numeric_data():
    result = analyze_rows(
        rows=[{"category": "a", "revenue": 10}, {"category": "b", "revenue": 20}],
        columns=["category", "revenue"],
    )
    assert result["row_count"] == 2
    assert "revenue" in result["summary"]


def test_read_project_file_is_allow_listed():
    assert "AI Data Analyst" in read_project_file("README.md")
