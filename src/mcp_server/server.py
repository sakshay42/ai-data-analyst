"""MCP server exposing safe AI Data Analyst project tools.

The server intentionally exposes offline/read-only helpers by default. Database
execution remains behind the existing project safety checks and should only be
enabled by hosts that provide the required environment variables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.local_runner import (
    evaluate_sql_dataset,
    load_eval_cases,
    load_dataset,
    render_markdown_report,
    run_local_eval,
    summarize_results,
)
from evals.huggingface_loader import DEFAULT_HF_TEXT2SQL_DATASETS
from evals.progress_tracker import (
    compare_eval_results,
    render_progress_markdown,
    run_progress_demo,
    summarize_progress,
)
from evals.scorers.sql_scorers import SQLEfficiency, SQLValidity
from src.tools.stats_toolkit import StatsToolkit

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_info() -> dict[str, Any]:
    """Return a compact map of the project structure."""
    return {
        "name": "ai-data-analyst",
        "root": str(PROJECT_ROOT),
        "entrypoints": {
            "streamlit": "src/streamlit_app/app.py",
            "local_evals": "evals/local_runner.py",
            "eval_progress": "evals/progress_tracker.py",
            "live_sql_benchmark": "evals/generate_sql_predictions.py",
            "mcp_server": "src/mcp_server/server.py",
        },
        "source_packages": sorted(
            str(path.relative_to(PROJECT_ROOT))
            for path in (PROJECT_ROOT / "src").glob("*/")
            if path.is_dir()
        ),
        "eval_datasets": sorted(
            path.stem for path in (PROJECT_ROOT / "evals" / "datasets").glob("*.json")
        ),
    }


def score_sql(sql: str, tables: list[str] | None = None) -> dict[str, Any]:
    """Score one SQL query for read-only validity and basic efficiency."""
    validity = SQLValidity().score(sql)
    efficiency = SQLEfficiency().score(sql, tables=tables)
    combined = round((validity.score + efficiency.score) / 2.0, 4)
    return {
        "sql": sql,
        "validity": {
            "score": validity.score,
            "passed": validity.passed,
            "details": validity.details,
        },
        "efficiency": {
            "score": efficiency.score,
            "passed": efficiency.passed,
            "details": efficiency.details,
        },
        "combined_score": combined,
        "passed": validity.passed and combined >= 0.7,
    }


def list_eval_cases(dataset: str = "sql_generation") -> list[dict[str, Any]]:
    """List eval cases without exposing expected SQL by default."""
    return [
        {
            "question": case.question,
            "difficulty": case.difficulty,
            "tables": case.tables,
        }
        for case in load_dataset(dataset)
    ]


def list_huggingface_eval_presets() -> dict[str, dict[str, str]]:
    """List supported Hugging Face text-to-SQL benchmark presets."""
    return DEFAULT_HF_TEXT2SQL_DATASETS


def list_huggingface_eval_cases(
    preset: str = "bird",
    limit: int = 10,
    split: str = "train",
) -> list[dict[str, Any]]:
    """Stream and list normalized Hugging Face benchmark cases."""
    cases, _ = load_eval_cases(
        source="huggingface",
        hf_preset=preset,
        hf_split=split,
        limit=limit,
    )
    return [
        {
            "question": case.question,
            "difficulty": case.difficulty,
            "tables": case.tables,
            "metadata": case.metadata,
        }
        for case in cases
    ]


def run_sql_eval(
    dataset: str = "sql_generation",
    format: str = "json",
    execution: bool = False,
) -> dict[str, Any] | str:
    """Run the bundled local SQL eval dataset."""
    payload = run_local_eval(dataset_name=dataset, execution=execution)
    if format == "markdown":
        return render_markdown_report(payload)
    if format != "json":
        raise ValueError("format must be 'json' or 'markdown'.")
    return payload


def run_huggingface_sql_eval(
    preset: str = "bird",
    repo: str | None = None,
    split: str = "train",
    limit: int = 25,
    format: str = "json",
) -> dict[str, Any] | str:
    """Run scorer baseline on a streamed Hugging Face text-to-SQL sample."""
    payload = run_local_eval(
        source="huggingface",
        hf_preset=preset if repo is None else None,
        hf_repo=repo,
        hf_split=split,
        limit=limit,
    )
    if format == "markdown":
        return render_markdown_report(payload)
    if format != "json":
        raise ValueError("format must be 'json' or 'markdown'.")
    return payload


def evaluate_sql_predictions(
    predictions: list[dict[str, str]],
    dataset: str = "sql_generation",
    pass_threshold: float = 0.75,
    execution: bool = False,
) -> dict[str, Any]:
    """Evaluate generated SQL predictions supplied by an MCP client.

    Each prediction item must include `question` and one of `sql`,
    `generated_sql`, or `prediction`.
    """
    prediction_map: dict[str, str] = {}
    for item in predictions:
        question = item.get("question")
        sql = item.get("sql", item.get("generated_sql", item.get("prediction")))
        if not question or sql is None:
            raise ValueError("Each prediction must include question and sql/generated_sql/prediction.")
        prediction_map[str(question)] = str(sql)

    cases = load_dataset(dataset)
    results = evaluate_sql_dataset(
        cases,
        prediction_map,
        pass_threshold=pass_threshold,
        execution=execution,
    )
    missing = [case.question for case in cases if case.question not in prediction_map]
    return {
        "dataset": dataset,
        "mode": "mcp_predictions",
        "pass_threshold": pass_threshold,
        "execution_enabled": execution,
        "summary": summarize_results(results),
        "missing_predictions": missing,
        "results": [
            {
                "question": result.question,
                "difficulty": result.difficulty,
                "tables": result.tables,
                "sql": result.sql,
                "validity_score": result.validity_score,
                "efficiency_score": result.efficiency_score,
                "similarity_score": result.similarity_score,
                "keyword_coverage_score": result.keyword_coverage_score,
                "combined_score": result.combined_score,
                "execution_score": result.execution_score,
                "execution_passed": result.execution_passed,
                "passed": result.passed,
                "details": result.details,
            }
            for result in results
        ],
    }


def evaluate_sql_predictions_report(
    predictions: list[dict[str, str]],
    dataset: str = "sql_generation",
    pass_threshold: float = 0.75,
    execution: bool = False,
) -> str:
    """Evaluate predictions and render a markdown report."""
    return render_markdown_report(
        evaluate_sql_predictions(
            predictions=predictions,
            dataset=dataset,
            pass_threshold=pass_threshold,
            execution=execution,
        )
    )


def compare_sql_prediction_runs(
    previous_predictions: list[dict[str, str]],
    current_predictions: list[dict[str, str]],
    dataset: str = "sql_generation",
    pass_threshold: float = 0.90,
    format: str = "json",
) -> dict[str, Any] | str:
    """Compare two SQL prediction runs and diagnose progress/regressions."""

    def to_prediction_map(items: list[dict[str, str]]) -> dict[str, str]:
        prediction_map: dict[str, str] = {}
        for item in items:
            question = item.get("question")
            sql = item.get("sql", item.get("generated_sql", item.get("prediction")))
            if not question or sql is None:
                raise ValueError("Each prediction must include question and sql/generated_sql/prediction.")
            prediction_map[str(question)] = str(sql)
        return prediction_map

    cases = load_dataset(dataset)
    previous_results = evaluate_sql_dataset(
        cases, to_prediction_map(previous_predictions), pass_threshold=pass_threshold
    )
    current_results = evaluate_sql_dataset(
        cases, to_prediction_map(current_predictions), pass_threshold=pass_threshold
    )
    deltas = compare_eval_results(previous_results, current_results)
    payload = {
        "dataset": dataset,
        "pass_threshold": pass_threshold,
        "summary": summarize_progress(deltas),
        "deltas": [
            {
                "question": delta.question,
                "difficulty": delta.difficulty,
                "previous_score": delta.previous_score,
                "current_score": delta.current_score,
                "score_delta": delta.score_delta,
                "previous_passed": delta.previous_passed,
                "current_passed": delta.current_passed,
                "status": delta.status,
                "previous_issue": delta.previous_issue,
                "current_issue": delta.current_issue,
                "recommendation": delta.recommendation,
            }
            for delta in deltas
        ],
        "previous_predictions_path": "provided_via_mcp",
        "current_predictions_path": "provided_via_mcp",
        "chart_path": "not_generated_for_mcp_inline_comparison",
    }
    if format == "markdown":
        return render_progress_markdown(payload)
    if format != "json":
        raise ValueError("format must be 'json' or 'markdown'.")
    return payload


def run_eval_progress_demo(format: str = "json") -> dict[str, Any] | str:
    """Run the deterministic before/after eval progress demo."""
    payload = run_progress_demo()
    if format == "markdown":
        return render_progress_markdown(payload)
    if format != "json":
        raise ValueError("format must be 'json' or 'markdown'.")
    return payload


def analyze_rows(rows: list[dict[str, Any]], columns: list[str] | None = None) -> dict[str, Any]:
    """Run the project's non-LLM statistical analysis over provided rows."""
    resolved_columns = columns or (list(rows[0].keys()) if rows else [])
    toolkit = StatsToolkit(rows, resolved_columns)
    result = toolkit.full_analysis()
    return {
        "row_count": len(rows),
        "columns": resolved_columns,
        "summary": result.summary,
        "correlations": result.correlations,
        "tests": result.tests,
        "trends": result.trends,
    }


def read_project_file(relative_path: str) -> str:
    """Read a small allow-listed project context file."""
    allowed = {
        "README.md",
        "docs/SYSTEM_ARCHITECTURE.md",
        "conf/config.yaml",
        "pyproject.toml",
    }
    if relative_path not in allowed:
        raise ValueError(f"File is not exposed through MCP: {relative_path}")
    path = (PROJECT_ROOT / relative_path).resolve()
    if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
        raise ValueError("Path escapes project root.")
    return path.read_text()


def create_server():
    """Create and configure the MCP server."""
    try:
        from mcp.server import MCPServer
    except ImportError as exc:
        raise RuntimeError(
            "The MCP SDK is not installed. Run `poetry install` before starting the MCP server."
        ) from exc

    mcp = MCPServer("ai-data-analyst")

    mcp.tool()(project_info)
    mcp.tool()(score_sql)
    mcp.tool()(list_eval_cases)
    mcp.tool()(list_huggingface_eval_presets)
    mcp.tool()(list_huggingface_eval_cases)
    mcp.tool()(run_sql_eval)
    mcp.tool()(run_huggingface_sql_eval)
    mcp.tool()(evaluate_sql_predictions)
    mcp.tool()(evaluate_sql_predictions_report)
    mcp.tool()(compare_sql_prediction_runs)
    mcp.tool()(run_eval_progress_demo)
    mcp.tool()(analyze_rows)

    @mcp.resource("project://{relative_path}")
    def project_file(relative_path: str) -> str:
        """Read allow-listed project documentation/config files."""
        return read_project_file(relative_path)

    @mcp.prompt()
    def sql_review_prompt(question: str, sql: str) -> str:
        """Prompt template for reviewing generated SQL against a question."""
        score = score_sql(sql)
        return (
            "Review this generated PostgreSQL query for safety, schema fit, and analytical usefulness.\n\n"
            f"Question: {question}\n\nSQL:\n{sql}\n\n"
            f"Local scorer result:\n{json.dumps(score, indent=2)}"
        )

    return mcp


def main() -> None:
    """Run the MCP server using the SDK default transport."""
    create_server().run()


if __name__ == "__main__":
    main()
