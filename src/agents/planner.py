"""Planner agent: decomposes user question into an analysis plan."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from src.graph.state import AnalysisPlan, AnalystState

PLANNER_SYSTEM_PROMPT = """You are a data analysis planner. Given a user's business question and a database schema, create a structured analysis plan.

Your plan should include:
1. The original question restated clearly
2. Sub-questions that need to be answered via SQL
3. Which tables are required
4. The type of analysis (trend, comparison, distribution, ranking, aggregation)
5. Suggested visualizations (bar, line, pie, scatter, histogram)

Be specific about what SQL queries are needed and what analysis to perform."""


def create_planner_node(llm: ChatOpenAI):
    """Create a planner node function bound to an LLM."""

    def planner_node(state: AnalystState, config: RunnableConfig | None = None) -> dict[str, Any]:
        """Decompose the user question into an analysis plan."""
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Database Schema:\n{state.schema_summary}\n\n"
                f"User Question: {state.question}"
            ),
        ]
        structured_llm = llm.with_structured_output(AnalysisPlan)
        plan = structured_llm.invoke(messages, config=config)
        return {"plan": plan}

    return planner_node
