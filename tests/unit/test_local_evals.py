"""Tests for the local eval runner."""

from evals.local_runner import (
    evaluate_sql_dataset,
    load_dataset,
    render_markdown_report,
    run_local_eval,
    summarize_results,
)


def test_load_sql_generation_dataset():
    cases = load_dataset("sql_generation")
    assert cases
    assert cases[0].question
    assert cases[0].expected_sql.upper().startswith("SELECT")


def test_evaluate_sql_dataset_scores_expected_sql():
    cases = load_dataset("sql_generation")[:2]
    results = evaluate_sql_dataset(cases)
    assert len(results) == 2
    assert all(result.validity_score == 1.0 for result in results)


def test_summarize_results_has_aggregate_metrics():
    results = evaluate_sql_dataset(load_dataset("sql_generation")[:3])
    summary = summarize_results(results)
    assert summary["case_count"] == 3
    assert 0.0 <= summary["pass_rate"] <= 1.0
    assert "easy" in summary["by_difficulty"]
    assert "avg_similarity" in summary
    assert "weakest_cases" in summary


def test_run_local_eval_returns_serializable_payload():
    payload = run_local_eval("sql_generation")
    assert payload["dataset"] == "sql_generation"
    assert payload["dataset_info"]["source"] == "local"
    assert payload["summary"]["case_count"] > 0
    assert isinstance(payload["results"], list)


def test_prediction_mode_tracks_coverage_and_similarity():
    cases = load_dataset("sql_generation")[:2]
    predictions = {cases[0].question: "SELECT name FROM customers;"}
    results = evaluate_sql_dataset(cases, predictions)
    summary = summarize_results(results)
    assert results[0].used_prediction is True
    assert results[1].used_prediction is False
    assert 0.0 <= results[0].similarity_score <= 1.0
    assert summary["prediction_coverage"] == 0.5


def test_markdown_report_contains_eval_summary():
    payload = run_local_eval("sql_generation")
    report = render_markdown_report(payload)
    assert "# Eval Report: sql_generation" in report
    assert "Pass rate" in report
