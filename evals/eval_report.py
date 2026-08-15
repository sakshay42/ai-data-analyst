"""Braintrust evaluation script for report generation quality.

Tests report completeness (expected sections present) and clarity
(readability heuristics) using the report quality dataset.

Usage:
    poetry run python evals/eval_report.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import braintrust

# Ensure the project root is on the path so scorer imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evals.scorers.report_scorers import Clarity, Completeness

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "report_quality.json"


def load_dataset() -> list[dict]:
    """Load the report quality evaluation dataset."""
    with open(DATASET_PATH) as f:
        return json.load(f)


def report_generation_task(input_data: dict) -> dict:
    """Simulate report generation by producing a template report.

    In a real evaluation this would call the reporter agent with actual
    analysis results. For offline scorer validation we generate a
    structured report that includes the expected sections and keywords.
    Replace this with actual LLM-generated reports for live evals.
    """
    question = input_data["question"]
    sections = input_data["expected_sections"]
    keywords = input_data["expected_keywords"]

    # Build a template report with all expected sections
    report_parts: list[str] = []

    for section in sections:
        report_parts.append(f"## {section}")
        report_parts.append("")

        if section == "Executive Summary":
            report_parts.append(
                f"This report analyzes the question: \"{question}\". "
                f"The analysis covers key metrics including {', '.join(keywords[:3])}. "
                "The findings reveal actionable patterns that can inform business decisions."
            )
        elif section == "Question":
            report_parts.append(f"**Business Question:** {question}")
        elif section == "Methodology":
            report_parts.append(
                "The analysis was performed using SQL queries against the ecommerce database, "
                "followed by statistical analysis including descriptive statistics, "
                "trend detection, and correlation analysis. "
                f"Key metrics examined: {', '.join(keywords)}."
            )
        elif section == "Key Findings":
            report_parts.append("The analysis revealed the following key findings:")
            report_parts.append("")
            for i, kw in enumerate(keywords, 1):
                report_parts.append(
                    f"{i}. Analysis of **{kw}** shows significant patterns. "
                    f"The metric measured at approximately {100 + i * 15}% of baseline, "
                    f"representing a {5 + i * 2}% change from the previous period."
                )
        elif section == "Visualizations":
            report_parts.append(
                "- Bar chart showing distribution across categories\n"
                "- Line chart showing trend over time\n"
                "- Summary statistics table"
            )
        elif section == "Recommendations":
            report_parts.append(
                f"Based on the analysis of {keywords[0] if keywords else 'the data'}, "
                "we recommend the following actions:\n\n"
                "1. Monitor the identified trends on a weekly basis\n"
                "2. Investigate the root causes of significant deviations\n"
                "3. Implement targeted strategies based on the segment analysis"
            )
        else:
            report_parts.append(f"Content for {section} related to {', '.join(keywords)}.")

        report_parts.append("")

    return {
        "report": "\n".join(report_parts),
        "question": question,
        "expected_sections": sections,
        "expected_keywords": keywords,
    }


def score_completeness(output: dict) -> float:
    """Score whether all expected sections are present in the report."""
    scorer = Completeness()
    result = scorer.score(output["report"], output["expected_sections"])
    return result.score


def score_clarity(output: dict) -> float:
    """Score the clarity and readability of the report."""
    scorer = Clarity()
    result = scorer.score(output["report"])
    return result.score


def score_keyword_coverage(output: dict) -> float:
    """Score whether expected keywords appear in the report."""
    report_lower = output["report"].lower()
    keywords = output.get("expected_keywords", [])
    if not keywords:
        return 1.0

    found = sum(1 for kw in keywords if kw.lower() in report_lower)
    return round(found / len(keywords), 4)


def run_eval():
    """Run the Braintrust evaluation."""
    dataset = load_dataset()

    braintrust.Eval(
        "Report Quality",
        data=lambda: [
            {
                "input": item,
                "expected": {
                    "sections": item["expected_sections"],
                    "keywords": item["expected_keywords"],
                },
                "metadata": {"question": item["question"]},
            }
            for item in dataset
        ],
        task=report_generation_task,
        scores=[
            score_completeness,
            score_clarity,
            score_keyword_coverage,
        ],
    )


if __name__ == "__main__":
    run_eval()
