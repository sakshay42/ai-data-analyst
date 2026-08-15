"""Generate live SQL predictions and score them with the eval pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.local_runner import EvalCase, load_eval_cases, render_markdown_report, run_local_eval


LOCAL_EVAL_SCHEMA_CONTEXT = """PostgreSQL ecommerce schema for the bundled SQL evals:

customers(id, name, email)
products(id, name, category, price)
orders(id, customer_id, order_date, total_amount)
order_items(id, order_id, product_id, quantity, unit_price)
reviews(id, product_id, rating)

Relationships:
- orders.customer_id -> customers.id
- order_items.order_id -> orders.id
- order_items.product_id -> products.id
- reviews.product_id -> products.id
"""

SYSTEM_PROMPT = """You generate PostgreSQL for benchmark evaluation.

Rules:
- Return exactly one read-only SELECT query.
- Do not include markdown fences, comments, prose, or explanations.
- Use explicit JOIN syntax.
- Prefer explicit columns over SELECT * unless the question asks for all fields.
- Include WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, CTEs, or window functions when required.
- Use PostgreSQL syntax."""


class ChatModel(Protocol):
    """Minimal interface used by the live benchmark generator."""

    def invoke(self, messages: list[Any]) -> Any:
        """Return a chat response with a content attribute or string body."""


def schema_context_for_case(case: EvalCase, source: str = "local") -> str:
    """Build schema context for local or external benchmark cases."""
    if source == "local":
        return LOCAL_EVAL_SCHEMA_CONTEXT

    metadata = case.metadata or {}
    context_parts = []
    for key in ("schema", "context", "evidence"):
        value = metadata.get(key)
        if value:
            context_parts.append(f"{key}: {value}")
    if case.tables:
        context_parts.append(f"tables: {', '.join(case.tables)}")
    return "\n".join(context_parts) or "No schema text was provided. Infer conservatively from the question and table names."


def clean_sql_response(content: Any) -> str:
    """Normalize a model response into a bare SQL string."""
    if isinstance(content, list):
        text = "\n".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in content)
    else:
        text = str(content)
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("sql"):
            text = text[3:].strip()
    return text.rstrip(";").strip() + ";"


def generate_sql_for_case(case: EvalCase, llm: ChatModel, source: str = "local") -> str:
    """Generate one SQL prediction for an eval case."""
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Schema/context:\n{schema_context_for_case(case, source=source)}\n\n"
                f"Question:\n{case.question}\n\n"
                "SQL:"
            )
        ),
    ]
    response = llm.invoke(messages)
    return clean_sql_response(getattr(response, "content", response))


def generate_predictions(
    cases: list[EvalCase],
    llm: ChatModel,
    source: str = "local",
) -> list[dict[str, str]]:
    """Generate SQL predictions for a list of eval cases."""
    predictions = []
    for case in cases:
        predictions.append(
            {
                "question": case.question,
                "sql": generate_sql_for_case(case, llm=llm, source=source),
            }
        )
    return predictions


def create_openai_llm(model: str, temperature: float = 0.0) -> ChatOpenAI:
    """Create a ChatOpenAI client, failing clearly when the key is missing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Set it locally in your shell; do not commit it."
        )
    return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)


def run_live_sql_benchmark(
    dataset_name: str = "sql_generation",
    source: str = "local",
    hf_preset: str | None = None,
    hf_repo: str | None = None,
    hf_split: str = "train",
    hf_config: str | None = None,
    limit: int = 16,
    model: str = "gpt-4o-mini",
    output_dir: str = "output/live_sql_benchmark",
    pass_threshold: float = 0.75,
    llm: ChatModel | None = None,
) -> dict[str, Any]:
    """Generate live predictions, score them, and write artifacts."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    cases, dataset_info = load_eval_cases(
        source=source,
        dataset_name=dataset_name,
        hf_repo=hf_repo,
        hf_preset=hf_preset,
        hf_split=hf_split,
        hf_config=hf_config,
        limit=limit,
    )
    model_client = llm or create_openai_llm(model=model, temperature=0.0)
    predictions = generate_predictions(cases, llm=model_client, source=source)
    predictions_path = output_path / "predictions.json"
    predictions_path.write_text(json.dumps(predictions, indent=2))

    payload = run_local_eval(
        dataset_name=dataset_name,
        predictions_path=predictions_path,
        pass_threshold=pass_threshold,
        source=source,
        hf_repo=hf_repo,
        hf_preset=hf_preset,
        hf_split=hf_split,
        hf_config=hf_config,
        limit=limit,
    )
    payload["model"] = model
    payload["predictions_path"] = str(predictions_path)
    payload["dataset_info"] = dataset_info

    report_path = output_path / "live_sql_benchmark_report.md"
    report_path.write_text(render_markdown_report(payload))
    payload_path = output_path / "live_sql_benchmark_payload.json"
    payload_path.write_text(json.dumps(payload, indent=2))
    payload["report_path"] = str(report_path)
    payload["payload_path"] = str(payload_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate live SQL predictions and score them.")
    parser.add_argument("--dataset", default="sql_generation")
    parser.add_argument("--source", choices=["local", "huggingface"], default="local")
    parser.add_argument("--hf-preset", choices=["bird", "bird-chat"], default=None)
    parser.add_argument("--hf-repo", default=None)
    parser.add_argument("--hf-split", default="train")
    parser.add_argument("--hf-config", default=None)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--output-dir", default="output/live_sql_benchmark")
    parser.add_argument("--pass-threshold", type=float, default=0.75)
    args = parser.parse_args()

    try:
        payload = run_live_sql_benchmark(
            dataset_name=args.dataset,
            source=args.source,
            hf_preset=args.hf_preset,
            hf_repo=args.hf_repo,
            hf_split=args.hf_split,
            hf_config=args.hf_config,
            limit=args.limit,
            model=args.model,
            output_dir=args.output_dir,
            pass_threshold=args.pass_threshold,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    summary = payload["summary"]
    print(f"Generated live SQL benchmark report: {payload['report_path']}")
    print(f"Predictions: {payload['predictions_path']}")
    print(f"Pass rate: {summary['pass_rate']:.2%}")
    print(f"Average combined score: {summary['avg_combined']:.4f}")


if __name__ == "__main__":
    main()
