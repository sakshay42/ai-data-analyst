"""Visualizer agent: generates charts from analysis and query results."""

from __future__ import annotations

from typing import Any

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field

from src.graph.state import AnalystState
from src.graph.state import ChartArtifact as ChartArtifactState
from src.tools.chart_builder import ChartBuilder

VIZ_SYSTEM_PROMPT = """You are a data visualization expert. Given analysis results and a data schema, recommend the best chart(s) to visualize the findings.

For each chart, specify:
- chart_type: one of "bar", "line", "pie", "scatter", "histogram"
- x_column: column name for x-axis
- y_column: column name for y-axis
- title: descriptive chart title

Return a list of 1-3 chart specifications. Choose charts that best communicate the key findings."""


class ChartSpec(BaseModel):
    chart_type: str
    x_column: str
    y_column: str
    title: str


class ChartSpecs(BaseModel):
    charts: list[ChartSpec] = Field(default_factory=list)


def create_visualizer_node(llm: ChatOpenAI, output_dir: str = "output"):
    """Create a visualizer node bound to an LLM."""
    builder = ChartBuilder(output_dir=output_dir)

    def visualizer_node(state: AnalystState, config: RunnableConfig | None = None) -> dict[str, Any]:
        """Generate visualizations based on analysis results."""
        qr = state.query_result
        if qr.error or not qr.rows:
            logger.warning("No data for visualization")
            return {"charts": []}

        df = pd.DataFrame(qr.rows, columns=qr.columns)

        # Ask LLM for chart recommendations
        messages = [
            SystemMessage(content=VIZ_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Question: {state.question}\n"
                f"Columns: {qr.columns}\n"
                f"Row count: {qr.row_count}\n"
                f"Sample data (first 3 rows): {qr.rows[:3]}\n"
                f"Analysis insights: {state.analysis.insights}\n"
                f"Suggested visualizations from plan: {state.plan.suggested_visualizations}"
            ),
        ]

        structured_llm = llm.with_structured_output(ChartSpecs)
        specs = structured_llm.invoke(messages, config=config)

        charts: list[ChartArtifactState] = []
        for i, spec in enumerate(specs.charts):
            try:
                # Validate columns exist
                if spec.x_column not in df.columns or spec.y_column not in df.columns:
                    logger.warning(
                        "Skipping chart: columns {} or {} not in data",
                        spec.x_column,
                        spec.y_column,
                    )
                    continue

                name = f"chart_{i}_{spec.chart_type}"
                chart_methods = {
                    "bar": builder.bar_chart,
                    "line": builder.line_chart,
                    "scatter": builder.scatter_plot,
                    "histogram": lambda df, x, y, title, name: builder.histogram(
                        df, x, title=title, name=name
                    ),
                    "pie": lambda df, x, y, title, name: builder.pie_chart(
                        df, x, y, title=title, name=name
                    ),
                }
                method = chart_methods.get(spec.chart_type)
                if method:
                    artifact = method(
                        df=df,
                        x=spec.x_column,
                        y=spec.y_column,
                        title=spec.title,
                        name=name,
                    )
                    charts.append(
                        ChartArtifactState(
                            path=artifact.path,
                            chart_type=artifact.chart_type,
                            title=artifact.title,
                            description=artifact.description,
                        )
                    )
            except Exception as e:
                logger.error("Failed to create chart {}: {}", i, e)

        logger.info("Generated {} charts", len(charts))
        return {"charts": charts}

    return visualizer_node
