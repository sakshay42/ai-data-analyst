"""Reporter agent: generates a markdown business report from the full state."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from loguru import logger

from src.graph.state import AnalystState

REPORTER_SYSTEM_PROMPT = """You are a business analyst writing a clear, actionable report. Given analysis results, SQL query, and charts, create a comprehensive markdown report.

Structure your report as:
1. **Executive Summary** - Key findings in 2-3 sentences
2. **Question** - The original business question
3. **Methodology** - How the analysis was performed (SQL query summary, statistical methods)
4. **Key Findings** - Detailed findings with numbers
5. **Visualizations** - Reference generated charts
6. **Recommendations** - Actionable next steps based on findings

Use clear business language. Include specific numbers and percentages. If there were errors or missing data, note them transparently."""


def create_reporter_node(llm: ChatOpenAI):
    """Create a reporter node bound to an LLM."""

    def reporter_node(state: AnalystState, config: RunnableConfig | None = None) -> dict[str, Any]:
        """Generate the final markdown report."""
        # Build context for the LLM
        charts_info = ""
        if state.charts:
            charts_info = "\n".join(
                f"- {c.title} ({c.chart_type}): {c.description} [saved to {c.path}]"
                for c in state.charts
            )
        else:
            charts_info = "No charts were generated."

        errors_info = ""
        if state.errors:
            errors_info = f"\nErrors encountered: {state.errors}"

        messages = [
            SystemMessage(content=REPORTER_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Question: {state.question}\n\n"
                f"SQL Query:\n```sql\n{state.query_result.sql}\n```\n\n"
                f"Query returned {state.query_result.row_count} rows.\n\n"
                f"Analysis Insights:\n{chr(10).join('- ' + i for i in state.analysis.insights)}\n\n"
                f"Summary Statistics:\n{state.analysis.summary_stats}\n\n"
                f"Correlations:\n{state.analysis.correlations}\n\n"
                f"Charts:\n{charts_info}\n"
                f"{errors_info}"
            ),
        ]
        response = llm.invoke(messages, config=config)
        report = response.content
        logger.info("Report generated ({} chars)", len(report))
        return {"report": report}

    return reporter_node
