"""Braintrust evaluation script for SQL generation quality.

Runs the SQL generation dataset through validity and efficiency scorers.
Correctness scoring is optional and requires a live database connection.

Usage:
    poetry run python evals/eval_sql_generation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import braintrust

# Ensure the project root is on the path so scorer imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.scorers.sql_scorers import SQLCorrectness, SQLEfficiency, SQLValidity

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "sql_generation.json"


def load_dataset() -> list[dict]:
    """Load the SQL generation evaluation dataset."""
    with open(DATASET_PATH) as f:
        return json.load(f)


def sql_generation_task(input_data: dict) -> dict:
    """Simulate SQL generation by returning the expected SQL.

    In a real evaluation this would call the SQL agent. For offline
    evaluation we use the expected SQL to validate the scorer pipeline.
    Replace this function with actual LLM-generated SQL for live evals.
    """
    return {
        "sql": input_data["expected_sql"],
        "question": input_data["question"],
        "difficulty": input_data["difficulty"],
        "tables": input_data["tables"],
    }


def score_sql_validity(output: dict) -> float:
    """Score SQL validity."""
    scorer = SQLValidity()
    result = scorer.score(output["sql"])
    return result.score


def score_sql_efficiency(output: dict) -> float:
    """Score SQL efficiency."""
    scorer = SQLEfficiency()
    result = scorer.score(output["sql"], tables=output.get("tables"))
    return result.score


def score_sql_difficulty_weighted(output: dict) -> float:
    """Combined score weighted by difficulty.

    Hard queries get a bonus for passing validity + efficiency.
    """
    validity = SQLValidity().score(output["sql"])
    efficiency = SQLEfficiency().score(output["sql"], tables=output.get("tables"))

    base_score = (validity.score + efficiency.score) / 2.0

    difficulty = output.get("difficulty", "easy")
    weight_map = {"easy": 1.0, "medium": 1.1, "hard": 1.2}
    weight = weight_map.get(difficulty, 1.0)

    return min(1.0, round(base_score * weight, 4))


def run_eval():
    """Run the Braintrust evaluation."""
    dataset = load_dataset()

    braintrust.Eval(
        "SQL Generation Quality",
        data=lambda: [
            {
                "input": item,
                "expected": {"sql": item["expected_sql"]},
                "metadata": {
                    "difficulty": item["difficulty"],
                    "tables": item["tables"],
                },
            }
            for item in dataset
        ],
        task=sql_generation_task,
        scores=[
            score_sql_validity,
            score_sql_efficiency,
            score_sql_difficulty_weighted,
        ],
    )


if __name__ == "__main__":
    run_eval()
