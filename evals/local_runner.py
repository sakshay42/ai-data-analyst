"""Local evaluation runner for offline SQL scorer checks.

This runner does not require API keys or a live database. By default it scores
expected SQL from the bundled dataset so the scorer pipeline can be validated
locally. Pass a predictions JSON file to score model outputs against the same
cases.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.scorers.sql_scorers import SQLEfficiency, SQLValidity

DATASET_DIR = Path(__file__).resolve().parent / "datasets"


@dataclass(frozen=True)
class EvalCase:
    """One SQL evaluation case loaded from JSON."""

    question: str
    expected_sql: str
    difficulty: str
    tables: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalResult:
    """Serializable result for one evaluated SQL prediction."""

    question: str
    difficulty: str
    tables: list[str]
    sql: str
    expected_sql: str
    validity_score: float
    efficiency_score: float
    similarity_score: float
    keyword_coverage_score: float
    combined_score: float
    passed: bool
    used_prediction: bool
    metadata: dict[str, Any]
    details: dict[str, Any]


def normalize_sql(sql: str) -> str:
    """Normalize SQL for lightweight text comparison."""
    return " ".join(sql.strip().rstrip(";").lower().split())


def sql_similarity(actual_sql: str, expected_sql: str) -> float:
    """Return a stable similarity score between two SQL strings."""
    actual = normalize_sql(actual_sql)
    expected = normalize_sql(expected_sql)
    if not actual and not expected:
        return 1.0
    return round(difflib.SequenceMatcher(None, actual, expected).ratio(), 4)


def sql_keyword_coverage(actual_sql: str, expected_sql: str) -> float:
    """Score whether important SQL clauses from expected SQL appear in actual SQL."""
    keywords = [
        "select",
        "from",
        "join",
        "where",
        "group by",
        "having",
        "order by",
        "limit",
        "with",
        "over",
    ]
    expected = normalize_sql(expected_sql)
    actual = normalize_sql(actual_sql)
    required = [keyword for keyword in keywords if keyword in expected]
    if not required:
        return 1.0
    matched = sum(1 for keyword in required if keyword in actual)
    return round(matched / len(required), 4)


def load_dataset(name: str = "sql_generation") -> list[EvalCase]:
    """Load an eval dataset by name from evals/datasets."""
    path = DATASET_DIR / f"{name}.json"
    if not path.exists():
        available = sorted(p.stem for p in DATASET_DIR.glob("*.json"))
        raise FileNotFoundError(f"Unknown dataset '{name}'. Available: {available}")

    raw_cases = json.loads(path.read_text())
    return [
        EvalCase(
            question=case["question"],
            expected_sql=case["expected_sql"],
            difficulty=case.get("difficulty", "unknown"),
            tables=case.get("tables", []),
            metadata=case.get("metadata", {}),
        )
        for case in raw_cases
    ]


def load_eval_cases(
    source: str = "local",
    dataset_name: str = "sql_generation",
    hf_repo: str | None = None,
    hf_preset: str | None = None,
    hf_split: str = "train",
    hf_config: str | None = None,
    limit: int = 50,
) -> tuple[list[EvalCase], dict[str, Any]]:
    """Load eval cases from local JSON or a Hugging Face text-to-SQL dataset."""
    if source == "local":
        cases = load_dataset(dataset_name)
        return cases, {"source": "local", "dataset": dataset_name}
    if source != "huggingface":
        raise ValueError("source must be 'local' or 'huggingface'.")

    from evals.huggingface_loader import load_huggingface_sql_dataset, resolve_hf_preset

    resolved_repo = hf_repo
    resolved_split = hf_split
    preset = None
    if hf_preset:
        preset = resolve_hf_preset(hf_preset)
        resolved_repo = resolved_repo or preset["repo"]
        resolved_split = hf_split or preset["split"]
    if not resolved_repo:
        raise ValueError("Hugging Face source requires --hf-repo or --hf-preset.")

    cases = load_huggingface_sql_dataset(
        repo=resolved_repo,
        split=resolved_split,
        limit=limit,
        config=hf_config,
        streaming=True,
    )
    return cases, {
        "source": "huggingface",
        "dataset": resolved_repo,
        "preset": hf_preset,
        "split": resolved_split,
        "config": hf_config,
        "limit": limit,
    }


def load_predictions(path: Path) -> dict[str, str]:
    """Load predictions keyed by question.

    Accepted shapes:
    - {"Question text": "SELECT ..."}
    - [{"question": "Question text", "sql": "SELECT ..."}, ...]
    - [{"question": "Question text", "generated_sql": "SELECT ..."}, ...]
    """
    raw = json.loads(path.read_text())
    if isinstance(raw, dict):
        return {str(question): str(sql) for question, sql in raw.items()}
    if isinstance(raw, list):
        predictions: dict[str, str] = {}
        for item in raw:
            if not isinstance(item, dict) or "question" not in item:
                raise ValueError("Prediction list items must include 'question'.")
            sql = item.get("sql", item.get("generated_sql", item.get("prediction")))
            if sql is None:
                raise ValueError(
                    "Prediction list items must include 'sql', 'generated_sql', or 'prediction'."
                )
            predictions[str(item["question"])] = str(sql)
        return predictions
    raise ValueError("Predictions must be a JSON object or a list of objects.")


def evaluate_sql_dataset(
    cases: list[EvalCase],
    predictions: dict[str, str] | None = None,
    pass_threshold: float = 0.75,
) -> list[EvalResult]:
    """Score SQL for each case using local validity and efficiency scorers."""
    validity = SQLValidity()
    efficiency = SQLEfficiency()
    predictions = predictions or {}

    results: list[EvalResult] = []
    for case in cases:
        used_prediction = case.question in predictions
        sql = predictions.get(case.question, case.expected_sql)
        validity_result = validity.score(sql)
        efficiency_result = efficiency.score(sql, tables=case.tables)
        similarity = sql_similarity(sql, case.expected_sql)
        keyword_coverage = sql_keyword_coverage(sql, case.expected_sql)
        combined = round(
            (
                validity_result.score * 0.35
                + efficiency_result.score * 0.25
                + similarity * 0.25
                + keyword_coverage * 0.15
            ),
            4,
        )
        results.append(
            EvalResult(
                question=case.question,
                difficulty=case.difficulty,
                tables=case.tables,
                sql=sql,
                expected_sql=case.expected_sql,
                validity_score=validity_result.score,
                efficiency_score=efficiency_result.score,
                similarity_score=similarity,
                keyword_coverage_score=keyword_coverage,
                combined_score=combined,
                passed=validity_result.passed and combined >= pass_threshold,
                used_prediction=used_prediction,
                metadata=case.metadata,
                details={
                    "validity": validity_result.details,
                    "efficiency": efficiency_result.details,
                },
            )
        )
    return results


def summarize_results(results: list[EvalResult]) -> dict[str, Any]:
    """Build aggregate metrics for a result set."""
    if not results:
        return {
            "case_count": 0,
            "pass_rate": 0.0,
            "avg_validity": 0.0,
            "avg_efficiency": 0.0,
            "avg_similarity": 0.0,
            "avg_keyword_coverage": 0.0,
            "avg_combined": 0.0,
            "prediction_coverage": 0.0,
            "by_difficulty": {},
            "issue_counts": {},
            "weakest_cases": [],
        }

    by_difficulty: dict[str, list[EvalResult]] = {}
    issue_counts: Counter[str] = Counter()
    for result in results:
        by_difficulty.setdefault(result.difficulty, []).append(result)
        for issue in result.details.get("efficiency", {}).get("issues", []):
            issue_counts[issue.get("name", "unknown")] += 1

    weakest_cases = sorted(results, key=lambda r: r.combined_score)[:5]

    return {
        "case_count": len(results),
        "pass_rate": round(sum(r.passed for r in results) / len(results), 4),
        "avg_validity": round(mean(r.validity_score for r in results), 4),
        "avg_efficiency": round(mean(r.efficiency_score for r in results), 4),
        "avg_similarity": round(mean(r.similarity_score for r in results), 4),
        "avg_keyword_coverage": round(mean(r.keyword_coverage_score for r in results), 4),
        "avg_combined": round(mean(r.combined_score for r in results), 4),
        "prediction_coverage": round(sum(r.used_prediction for r in results) / len(results), 4),
        "by_difficulty": {
            difficulty: {
                "case_count": len(items),
                "pass_rate": round(sum(r.passed for r in items) / len(items), 4),
                "avg_combined": round(mean(r.combined_score for r in items), 4),
            }
            for difficulty, items in sorted(by_difficulty.items())
        },
        "issue_counts": dict(sorted(issue_counts.items())),
        "weakest_cases": [
            {
                "question": result.question,
                "difficulty": result.difficulty,
                "combined_score": result.combined_score,
                "passed": result.passed,
            }
            for result in weakest_cases
        ],
    }


def missing_prediction_questions(
    cases: list[EvalCase],
    predictions: dict[str, str] | None,
) -> list[str]:
    """Return dataset questions that were not covered by predictions."""
    if predictions is None:
        return []
    return [case.question for case in cases if case.question not in predictions]


def render_markdown_report(payload: dict[str, Any]) -> str:
    """Render an eval payload into a compact markdown report."""
    summary = payload["summary"]
    lines = [
        f"# Eval Report: {payload['dataset']}",
        "",
        f"- Mode: `{payload['mode']}`",
        f"- Cases: {summary['case_count']}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Average combined score: {summary['avg_combined']:.4f}",
        f"- Average validity: {summary['avg_validity']:.4f}",
        f"- Average efficiency: {summary['avg_efficiency']:.4f}",
        f"- Average SQL similarity: {summary['avg_similarity']:.4f}",
        f"- Prediction coverage: {summary['prediction_coverage']:.2%}",
        "",
        "## By Difficulty",
        "",
    ]
    for difficulty, metrics in summary["by_difficulty"].items():
        lines.append(
            f"- {difficulty}: {metrics['case_count']} cases, "
            f"{metrics['pass_rate']:.2%} pass, avg {metrics['avg_combined']:.4f}"
        )

    if summary["issue_counts"]:
        lines.extend(["", "## Issue Counts", ""])
        for issue, count in summary["issue_counts"].items():
            lines.append(f"- {issue}: {count}")

    if summary["weakest_cases"]:
        lines.extend(["", "## Weakest Cases", ""])
        for case in summary["weakest_cases"]:
            lines.append(
                f"- {case['combined_score']:.4f} "
                f"({'pass' if case['passed'] else 'fail'}): {case['question']}"
            )

    if payload.get("missing_predictions"):
        lines.extend(["", "## Missing Predictions", ""])
        for question in payload["missing_predictions"]:
            lines.append(f"- {question}")

    return "\n".join(lines) + "\n"


def run_local_eval(
    dataset_name: str = "sql_generation",
    predictions_path: Path | None = None,
    pass_threshold: float = 0.75,
    source: str = "local",
    hf_repo: str | None = None,
    hf_preset: str | None = None,
    hf_split: str = "train",
    hf_config: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Run SQL evals and return summary plus per-case results."""
    cases, dataset_info = load_eval_cases(
        source=source,
        dataset_name=dataset_name,
        hf_repo=hf_repo,
        hf_preset=hf_preset,
        hf_split=hf_split,
        hf_config=hf_config,
        limit=limit,
    )
    predictions = load_predictions(predictions_path) if predictions_path else None
    results = evaluate_sql_dataset(cases, predictions, pass_threshold=pass_threshold)
    return {
        "dataset": dataset_info["dataset"],
        "dataset_info": dataset_info,
        "mode": "predictions" if predictions_path else "expected_sql_baseline",
        "pass_threshold": pass_threshold,
        "summary": summarize_results(results),
        "missing_predictions": missing_prediction_questions(cases, predictions),
        "results": [asdict(result) for result in results],
    }


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Run local SQL evals.")
    parser.add_argument("--dataset", default="sql_generation", help="Dataset name in evals/datasets")
    parser.add_argument(
        "--source",
        choices=["local", "huggingface"],
        default="local",
        help="Load bundled local evals or a Hugging Face text-to-SQL benchmark sample.",
    )
    parser.add_argument("--hf-preset", choices=["bird", "bird-chat"], default=None)
    parser.add_argument("--hf-repo", default=None, help="Hugging Face dataset repo, e.g. birdsql/bird23-train-filtered")
    parser.add_argument("--hf-split", default="train", help="Hugging Face split to stream.")
    parser.add_argument("--hf-config", default=None, help="Optional Hugging Face dataset config/subset.")
    parser.add_argument("--limit", type=int, default=50, help="Max external benchmark rows to sample.")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="Optional JSON predictions keyed by question or list of {question, sql} objects.",
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=0.75,
        help="Combined score threshold for passing a case.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional output path.")
    parser.add_argument(
        "--export-dataset",
        type=Path,
        default=None,
        help="Optional path to write normalized EvalCase rows as JSON.",
    )
    args = parser.parse_args()

    payload = run_local_eval(
        args.dataset,
        args.predictions,
        pass_threshold=args.pass_threshold,
        source=args.source,
        hf_repo=args.hf_repo,
        hf_preset=args.hf_preset,
        hf_split=args.hf_split,
        hf_config=args.hf_config,
        limit=args.limit,
    )
    if args.export_dataset:
        exported = [
            {
                "question": item["question"],
                "expected_sql": item["expected_sql"],
                "difficulty": item["difficulty"],
                "tables": item["tables"],
                "metadata": item.get("metadata", {}),
            }
            for item in payload["results"]
        ]
        args.export_dataset.write_text(json.dumps(exported, indent=2))
    output = render_markdown_report(payload) if args.format == "markdown" else json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(output)
    print(output)


if __name__ == "__main__":
    main()
