"""Tests for eval progress diagnostics."""

from evals.local_runner import evaluate_sql_dataset, load_dataset
from evals.progress_tracker import (
    compare_eval_results,
    diagnose_result,
    run_progress_demo,
    simulated_current_predictions,
    simulated_previous_predictions,
    summarize_progress,
)


def test_compare_eval_results_tracks_fixed_cases():
    cases = load_dataset("sql_generation")
    previous = evaluate_sql_dataset(cases, simulated_previous_predictions(), pass_threshold=0.90)
    current = evaluate_sql_dataset(cases, simulated_current_predictions(), pass_threshold=0.90)
    deltas = compare_eval_results(previous, current)
    summary = summarize_progress(deltas)
    assert summary["case_count"] == len(cases)
    assert summary["current_avg_score"] >= summary["previous_avg_score"]
    assert summary["fixed_cases"] >= 1
    assert summary["regressions"] == 0


def test_diagnose_result_identifies_missing_clause():
    case = load_dataset("sql_generation")[7]
    result = evaluate_sql_dataset(
        [case],
        {case.question: "SELECT c.name, COUNT(o.id) FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name;"},
    )[0]
    assert diagnose_result(result) in {"missing_required_clause", "near_threshold", "passed"}


def test_run_progress_demo_creates_report_and_chart(tmp_path):
    payload = run_progress_demo(output_dir=str(tmp_path))
    assert payload["summary"]["case_count"] > 0
    assert tmp_path.joinpath("eval_progress_report.md").exists()
    assert tmp_path.joinpath("eval_progress.png").exists()
    assert tmp_path.joinpath("previous_predictions.json").exists()
    assert tmp_path.joinpath("current_predictions.json").exists()
