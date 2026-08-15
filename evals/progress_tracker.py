"""Compare eval runs and turn failures into improvement guidance.

This module demonstrates the feedback loop a production analytics system needs:
run an eval, inspect failures, improve the SQL generation behavior, and verify
whether the next run fixed the weak cases without regressions.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.local_runner import EvalResult, evaluate_sql_dataset, load_dataset, load_predictions

matplotlib.use("Agg")


@dataclass(frozen=True)
class EvalCaseDelta:
    """Before/after comparison for one eval case."""

    question: str
    difficulty: str
    previous_score: float
    current_score: float
    score_delta: float
    previous_passed: bool
    current_passed: bool
    status: str
    previous_issue: str
    current_issue: str
    recommendation: str


def diagnose_result(result: EvalResult) -> str:
    """Assign a compact failure label to one scored SQL result."""
    if result.validity_score < 1.0:
        return "invalid_sql"
    efficiency_issues = result.details.get("efficiency", {}).get("issues", [])
    if efficiency_issues:
        return str(efficiency_issues[0].get("name", "efficiency_issue"))
    if result.keyword_coverage_score < 1.0:
        return "missing_required_clause"
    if result.similarity_score < 0.72:
        return "semantic_drift"
    if not result.passed:
        return "near_threshold"
    return "passed"


def recommendation_for_issue(issue: str) -> str:
    """Map a diagnosis label to a concrete model/prompt improvement."""
    recommendations = {
        "invalid_sql": "Constrain the generator to read-only SELECT statements and add SQL parsing before execution.",
        "select_star": "Ask for explicit columns unless the user explicitly requests all fields.",
        "cartesian_join": "Require explicit JOIN predicates when multiple tables are used.",
        "select_distinct_star": "Reject DISTINCT * and ask the generator to choose stable business columns.",
        "missing_required_clause": "Strengthen examples for WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, CTEs, and window functions.",
        "semantic_drift": "Add schema-grounded few-shot examples for the affected question pattern.",
        "near_threshold": "Review the generated SQL against the expected query and add a targeted regression case.",
        "passed": "No action needed.",
    }
    return recommendations.get(issue, "Inspect the failed query and add a targeted regression example.")


def _status(previous: EvalResult, current: EvalResult) -> str:
    if not previous.passed and current.passed:
        return "fixed"
    if previous.passed and not current.passed:
        return "regressed"
    if current.combined_score > previous.combined_score + 0.02:
        return "improved"
    if current.combined_score < previous.combined_score - 0.02:
        return "worse"
    return "unchanged"


def compare_eval_results(
    previous_results: list[EvalResult],
    current_results: list[EvalResult],
) -> list[EvalCaseDelta]:
    """Compare two eval result sets keyed by question."""
    previous_by_question = {result.question: result for result in previous_results}
    current_by_question = {result.question: result for result in current_results}
    missing = sorted(set(previous_by_question) ^ set(current_by_question))
    if missing:
        raise ValueError(f"Eval runs must contain the same questions. Mismatch: {missing}")

    deltas: list[EvalCaseDelta] = []
    for question, previous in previous_by_question.items():
        current = current_by_question[question]
        current_issue = diagnose_result(current)
        deltas.append(
            EvalCaseDelta(
                question=question,
                difficulty=current.difficulty,
                previous_score=previous.combined_score,
                current_score=current.combined_score,
                score_delta=round(current.combined_score - previous.combined_score, 4),
                previous_passed=previous.passed,
                current_passed=current.passed,
                status=_status(previous, current),
                previous_issue=diagnose_result(previous),
                current_issue=current_issue,
                recommendation=recommendation_for_issue(current_issue),
            )
        )
    return deltas


def summarize_progress(deltas: list[EvalCaseDelta]) -> dict[str, Any]:
    """Aggregate before/after progress into resume-friendly metrics."""
    if not deltas:
        return {
            "case_count": 0,
            "previous_pass_rate": 0.0,
            "current_pass_rate": 0.0,
            "pass_rate_delta": 0.0,
            "previous_avg_score": 0.0,
            "current_avg_score": 0.0,
            "avg_score_delta": 0.0,
            "fixed_cases": 0,
            "regressions": 0,
            "status_counts": {},
            "remaining_issue_counts": {},
            "top_improvements": [],
            "remaining_failures": [],
        }

    previous_pass_rate = sum(delta.previous_passed for delta in deltas) / len(deltas)
    current_pass_rate = sum(delta.current_passed for delta in deltas) / len(deltas)
    previous_avg = sum(delta.previous_score for delta in deltas) / len(deltas)
    current_avg = sum(delta.current_score for delta in deltas) / len(deltas)
    remaining_failures = [delta for delta in deltas if not delta.current_passed]

    return {
        "case_count": len(deltas),
        "previous_pass_rate": round(previous_pass_rate, 4),
        "current_pass_rate": round(current_pass_rate, 4),
        "pass_rate_delta": round(current_pass_rate - previous_pass_rate, 4),
        "previous_avg_score": round(previous_avg, 4),
        "current_avg_score": round(current_avg, 4),
        "avg_score_delta": round(current_avg - previous_avg, 4),
        "fixed_cases": sum(delta.status == "fixed" for delta in deltas),
        "regressions": sum(delta.status == "regressed" for delta in deltas),
        "status_counts": dict(Counter(delta.status for delta in deltas)),
        "remaining_issue_counts": dict(Counter(delta.current_issue for delta in remaining_failures)),
        "top_improvements": [
            asdict(delta)
            for delta in sorted(deltas, key=lambda item: item.score_delta, reverse=True)[:5]
        ],
        "remaining_failures": [
            asdict(delta)
            for delta in sorted(remaining_failures, key=lambda item: item.current_score)[:5]
        ],
    }


def simulated_previous_predictions() -> dict[str, str]:
    """Prediction set representing an early, weaker SQL generator run."""
    cases = load_dataset("sql_generation")
    predictions = {case.question: case.expected_sql for case in cases}
    overrides = {
        "List all customer names and emails.": "SELECT * FROM customers;",
        "Show total revenue per product category.": (
            "SELECT category, SUM(quantity) AS total_revenue "
            "FROM order_items GROUP BY category;"
        ),
        "Find the average order value per customer.": (
            "SELECT name, AVG(total_amount) AS avg_order_value "
            "FROM customers, orders GROUP BY name;"
        ),
        "Which customers have placed more than 3 orders?": (
            "SELECT c.name, COUNT(o.id) AS order_count "
            "FROM customers c JOIN orders o ON c.id = o.customer_id "
            "GROUP BY c.name ORDER BY order_count DESC;"
        ),
        "Show monthly revenue for the last 12 months.": (
            "SELECT DATE_TRUNC('month', order_date) AS month, SUM(total_amount) AS revenue "
            "FROM orders GROUP BY month ORDER BY month;"
        ),
        "Rank customers by their total spending using a window function.": (
            "SELECT c.name, SUM(o.total_amount) AS total_spent "
            "FROM customers c JOIN orders o ON c.id = o.customer_id "
            "GROUP BY c.name ORDER BY total_spent DESC;"
        ),
        "Calculate the running total of daily revenue.": (
            "SELECT DATE(order_date) AS order_date, SUM(total_amount) AS daily_revenue "
            "FROM orders GROUP BY DATE(order_date) ORDER BY order_date;"
        ),
        "Using a CTE, find the top 3 customers by revenue and show their most recent order date.": (
            "SELECT c.name, SUM(o.total_amount) AS total_revenue "
            "FROM customers c JOIN orders o ON c.id = o.customer_id "
            "GROUP BY c.name ORDER BY total_revenue DESC LIMIT 3;"
        ),
    }
    predictions.update(overrides)
    return predictions


def simulated_current_predictions() -> dict[str, str]:
    """Prediction set representing an improved SQL generator run."""
    cases = load_dataset("sql_generation")
    return {case.question: case.expected_sql for case in cases}


def plot_progress(summary: dict[str, Any], output_dir: Path) -> str:
    """Create a compact before/after chart for the eval loop."""
    path = output_dir / "eval_progress.png"
    labels = ["Pass rate", "Avg score"]
    previous = [summary["previous_pass_rate"], summary["previous_avg_score"]]
    current = [summary["current_pass_rate"], summary["current_avg_score"]]
    x_positions = range(len(labels))

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar([x - 0.18 for x in x_positions], previous, width=0.36, label="Before", color="#64748b")
    ax.bar([x + 0.18 for x in x_positions], current, width=0.36, label="After", color="#0f766e")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Eval Progress After SQL Generation Improvements")
    ax.legend()
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def render_progress_markdown(payload: dict[str, Any]) -> str:
    """Render progress diagnostics into a readable markdown report."""
    summary = payload["summary"]
    lines = [
        "# Eval Progress Demo",
        "",
        "This report demonstrates how evals are used as a feedback loop: run the SQL",
        "generator, diagnose weak cases, make targeted improvements, then verify",
        "whether the next run improved without regressions.",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Pass threshold: {payload.get('pass_threshold', 0.90):.2f}",
        f"- Pass rate: {summary['previous_pass_rate']:.2%} -> {summary['current_pass_rate']:.2%}",
        f"- Average score: {summary['previous_avg_score']:.4f} -> {summary['current_avg_score']:.4f}",
        f"- Fixed cases: {summary['fixed_cases']}",
        f"- Regressions: {summary['regressions']}",
        "",
        "## What Improved",
        "",
    ]
    for item in summary["top_improvements"]:
        lines.append(
            f"- +{item['score_delta']:.4f} ({item['status']}): {item['question']} "
            f"[{item['previous_issue']} -> {item['current_issue']}]"
        )

    lines.extend(["", "## Remaining Failure Types", ""])
    if summary["remaining_issue_counts"]:
        for issue, count in summary["remaining_issue_counts"].items():
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- None in the current run.")

    lines.extend(["", "## Improvement Actions", ""])
    actions = sorted(
        {
            item["recommendation"]
            for item in summary["remaining_failures"]
            if item["recommendation"] != "No action needed."
        }
    )
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- Keep the fixed cases as regression tests and expand coverage with harder joins, CTEs, and window-function cases.")

    lines.extend(["", "## Remaining Weak Cases", ""])
    if summary["remaining_failures"]:
        for item in summary["remaining_failures"]:
            lines.append(
                f"- {item['current_score']:.4f} ({item['current_issue']}): {item['question']}"
            )
    else:
        lines.append("- No failing cases in this demo run.")

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Progress chart: `{payload['chart_path']}`",
            f"- Previous predictions: `{payload['previous_predictions_path']}`",
            f"- Current predictions: `{payload['current_predictions_path']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run_progress_demo(output_dir: str = "output/eval_progress") -> dict[str, Any]:
    """Run a deterministic before/after eval-progress demonstration."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    cases = load_dataset("sql_generation")
    previous_predictions = simulated_previous_predictions()
    current_predictions = simulated_current_predictions()
    previous_results = evaluate_sql_dataset(cases, previous_predictions, pass_threshold=0.90)
    current_results = evaluate_sql_dataset(cases, current_predictions, pass_threshold=0.90)
    deltas = compare_eval_results(previous_results, current_results)
    summary = summarize_progress(deltas)

    previous_path = output_path / "previous_predictions.json"
    current_path = output_path / "current_predictions.json"
    previous_path.write_text(json.dumps(previous_predictions, indent=2))
    current_path.write_text(json.dumps(current_predictions, indent=2))
    chart_path = plot_progress(summary, output_path)
    payload = {
        "dataset": "sql_generation",
        "pass_threshold": 0.90,
        "summary": summary,
        "deltas": [asdict(delta) for delta in deltas],
        "previous_predictions_path": str(previous_path),
        "current_predictions_path": str(current_path),
        "chart_path": chart_path,
    }
    report = render_progress_markdown(payload)
    report_path = output_path / "eval_progress_report.md"
    report_path.write_text(report)
    payload["report_path"] = str(report_path)
    return payload


def run_progress_comparison(
    previous_predictions_path: Path,
    current_predictions_path: Path,
    dataset_name: str = "sql_generation",
    output_dir: str = "output/eval_progress",
    pass_threshold: float = 0.90,
) -> dict[str, Any]:
    """Compare two user-supplied prediction files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    cases = load_dataset(dataset_name)
    previous_results = evaluate_sql_dataset(
        cases, load_predictions(previous_predictions_path), pass_threshold=pass_threshold
    )
    current_results = evaluate_sql_dataset(
        cases, load_predictions(current_predictions_path), pass_threshold=pass_threshold
    )
    deltas = compare_eval_results(previous_results, current_results)
    summary = summarize_progress(deltas)
    chart_path = plot_progress(summary, output_path)
    payload = {
        "dataset": dataset_name,
        "pass_threshold": pass_threshold,
        "summary": summary,
        "deltas": [asdict(delta) for delta in deltas],
        "previous_predictions_path": str(previous_predictions_path),
        "current_predictions_path": str(current_predictions_path),
        "chart_path": chart_path,
    }
    report = render_progress_markdown(payload)
    report_path = output_path / "eval_progress_report.md"
    report_path.write_text(report)
    payload["report_path"] = str(report_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare eval runs and diagnose progress.")
    parser.add_argument("--dataset", default="sql_generation")
    parser.add_argument("--previous-predictions", type=Path, default=None)
    parser.add_argument("--current-predictions", type=Path, default=None)
    parser.add_argument("--output-dir", default="output/eval_progress")
    parser.add_argument("--pass-threshold", type=float, default=0.90)
    args = parser.parse_args()

    if args.previous_predictions or args.current_predictions:
        if not args.previous_predictions or not args.current_predictions:
            raise SystemExit("Both --previous-predictions and --current-predictions are required.")
        payload = run_progress_comparison(
            previous_predictions_path=args.previous_predictions,
            current_predictions_path=args.current_predictions,
            dataset_name=args.dataset,
            output_dir=args.output_dir,
            pass_threshold=args.pass_threshold,
        )
    else:
        payload = run_progress_demo(output_dir=args.output_dir)

    print(f"Generated eval progress report: {payload['report_path']}")
    print(f"Chart: {payload['chart_path']}")


if __name__ == "__main__":
    main()
