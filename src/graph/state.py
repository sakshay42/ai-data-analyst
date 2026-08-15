"""Pydantic state models for the LangGraph pipeline."""

from __future__ import annotations

import operator
from typing import Annotated, Any

from pydantic import BaseModel, Field


class AnalysisPlan(BaseModel):
    """Decomposed analysis plan from the planner agent."""

    question: str = ""
    sub_questions: list[str] = Field(default_factory=list)
    required_tables: list[str] = Field(default_factory=list)
    analysis_type: str = ""  # e.g. "trend", "comparison", "distribution", "ranking"
    suggested_visualizations: list[str] = Field(default_factory=list)


class QueryResult(BaseModel):
    """Result from SQL execution."""

    sql: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    error: str = ""


class AnalysisResult(BaseModel):
    """Statistical analysis output."""

    summary_stats: dict[str, Any] = Field(default_factory=dict)
    correlations: dict[str, float] = Field(default_factory=dict)
    tests: list[dict[str, Any]] = Field(default_factory=list)
    trends: dict[str, Any] = Field(default_factory=dict)
    insights: list[str] = Field(default_factory=list)


class ChartArtifact(BaseModel):
    """Reference to a generated chart file."""

    path: str = ""
    chart_type: str = ""
    title: str = ""
    description: str = ""


class AnalystState(BaseModel):
    """Main state flowing through the LangGraph pipeline."""

    # Input
    question: str = ""
    schema_summary: str = ""

    # Planner output
    plan: AnalysisPlan = Field(default_factory=AnalysisPlan)

    # SQL Agent output
    query_result: QueryResult = Field(default_factory=QueryResult)
    sql_retry_count: int = 0

    # Analyst output
    analysis: AnalysisResult = Field(default_factory=AnalysisResult)

    # Visualizer output
    charts: list[ChartArtifact] = Field(default_factory=list)

    # Reporter output
    report: str = ""

    # Error tracking (uses operator.add reducer pattern for LangGraph)
    errors: Annotated[list[str], operator.add] = Field(default_factory=list)
