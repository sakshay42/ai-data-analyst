"""Shared test fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.graph.state import (
    AnalysisPlan,
    AnalysisResult,
    AnalystState,
    ChartArtifact,
    QueryResult,
)


@pytest.fixture
def sample_state() -> AnalystState:
    """A sample AnalystState with populated fields."""
    return AnalystState(
        question="What are the top 5 products by revenue?",
        schema_summary="Table: products (id, name, price)\nTable: orders (id, product_id, quantity)",
        plan=AnalysisPlan(
            question="What are the top 5 products by revenue?",
            sub_questions=["Calculate revenue per product", "Rank by revenue"],
            required_tables=["products", "order_items"],
            analysis_type="ranking",
            suggested_visualizations=["bar"],
        ),
        query_result=QueryResult(
            sql="SELECT p.name, SUM(oi.quantity * oi.unit_price) as revenue FROM products p JOIN order_items oi ON p.id = oi.product_id GROUP BY p.name ORDER BY revenue DESC LIMIT 5",
            columns=["name", "revenue"],
            rows=[
                {"name": "Laptop Pro", "revenue": 150000.0},
                {"name": "Wireless Headphones", "revenue": 89000.0},
                {"name": "Smart Watch", "revenue": 67000.0},
                {"name": "Running Shoes", "revenue": 45000.0},
                {"name": "Coffee Maker", "revenue": 34000.0},
            ],
            row_count=5,
        ),
        analysis=AnalysisResult(
            summary_stats={
                "revenue": {
                    "count": 5.0,
                    "mean": 77000.0,
                    "std": 44721.36,
                    "min": 34000.0,
                    "max": 150000.0,
                }
            },
            insights=["revenue: mean=77000.00, std=44721.36, range=[34000.0, 150000.0]"],
        ),
        charts=[
            ChartArtifact(
                path="output/chart_0_bar.png",
                chart_type="bar",
                title="Top 5 Products by Revenue",
                description="Bar chart of revenue by product name",
            )
        ],
    )


@pytest.fixture
def sample_query_results() -> tuple[list[dict[str, Any]], list[str]]:
    """Sample query result data."""
    columns = ["product_name", "quantity", "revenue", "avg_rating"]
    rows = [
        {"product_name": "A", "quantity": 100, "revenue": 5000.0, "avg_rating": 4.5},
        {"product_name": "B", "quantity": 80, "revenue": 4000.0, "avg_rating": 3.8},
        {"product_name": "C", "quantity": 60, "revenue": 3000.0, "avg_rating": 4.2},
        {"product_name": "D", "quantity": 40, "revenue": 2000.0, "avg_rating": 3.5},
        {"product_name": "E", "quantity": 20, "revenue": 1000.0, "avg_rating": 4.0},
    ]
    return rows, columns


@pytest.fixture
def sample_analysis() -> AnalysisResult:
    """Sample analysis result."""
    return AnalysisResult(
        summary_stats={
            "revenue": {"count": 5, "mean": 3000.0, "std": 1581.14, "min": 1000.0, "max": 5000.0}
        },
        correlations={"quantity_vs_revenue": 1.0},
        insights=["revenue: mean=3000.00, std=1581.14"],
    )


@pytest.fixture
def mock_llm():
    """A mock ChatOpenAI that returns predictable responses."""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="SELECT 1")
    llm.with_structured_output.return_value = llm
    return llm


@pytest.fixture
def mock_db_pool():
    """A mock DatabasePool."""
    pool = MagicMock()
    pool.execute_query.return_value = (
        [{"id": 1, "name": "Test"}],
        ["id", "name"],
    )
    pool.connection.return_value.__enter__ = MagicMock()
    pool.connection.return_value.__exit__ = MagicMock(return_value=False)
    return pool
