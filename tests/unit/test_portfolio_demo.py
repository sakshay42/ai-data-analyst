"""Tests for the offline portfolio demo."""

from pathlib import Path

from src.demo.portfolio_demo import QUESTIONS, generate_ecommerce_data, run_demo


def test_generate_ecommerce_data_shapes():
    data = generate_ecommerce_data(seed=7)
    assert len(data["customers"]) == 500
    assert len(data["products"]) == 200
    assert len(data["orders"]) == 4000
    assert not data["order_items"].empty
    assert {"revenue", "profit", "margin_rate"}.issubset(data["order_items"].columns)


def test_run_demo_creates_report_and_charts(tmp_path: Path):
    result = run_demo(output_dir=str(tmp_path), seed=7)
    assert result["question_count"] == len(QUESTIONS)
    assert result["chart_count"] >= len(QUESTIONS)
    assert Path(result["report_markdown"]).exists()
    assert Path(result["report_html"]).exists()
    assert "AI Data Analyst Portfolio Demo" in Path(result["report_markdown"]).read_text()
