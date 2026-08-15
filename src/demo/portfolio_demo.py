"""Offline portfolio demo that showcases the analyst workflow.

The production graph needs Postgres and LLM credentials. This module gives the
project a deterministic, resume-friendly demo path that runs locally: synthetic
ecommerce data, realistic business questions, SQL-like analysis, charts, and
exported markdown/HTML reports.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.tools.chart_builder import ChartBuilder


@dataclass(frozen=True)
class DemoQuestion:
    """A portfolio demo question with expected analytical intent."""

    question_id: str
    question: str
    business_goal: str
    sql: str


@dataclass(frozen=True)
class DemoAnswer:
    """Result of one offline demo analysis."""

    question_id: str
    question: str
    business_goal: str
    sql: str
    row_count: int
    findings: list[str]
    recommendations: list[str]
    charts: list[dict[str, str]]
    output_csv: str


QUESTIONS: tuple[DemoQuestion, ...] = (
    DemoQuestion(
        question_id="revenue_by_category",
        question="Which product categories drive the most revenue and margin?",
        business_goal="Find the categories that deserve merchandising and inventory focus.",
        sql=(
            "SELECT category, SUM(revenue) AS revenue, SUM(profit) AS profit, "
            "SUM(profit) / NULLIF(SUM(revenue), 0) AS margin_rate "
            "FROM ecommerce_order_items GROUP BY category ORDER BY revenue DESC;"
        ),
    ),
    DemoQuestion(
        question_id="monthly_revenue_trend",
        question="How is revenue trending month over month?",
        business_goal="Identify growth, seasonality, and recent momentum.",
        sql=(
            "SELECT month, SUM(revenue) AS revenue, COUNT(DISTINCT order_id) AS orders "
            "FROM ecommerce_orders GROUP BY month ORDER BY month;"
        ),
    ),
    DemoQuestion(
        question_id="customer_segment_value",
        question="Which customer segments have the highest value?",
        business_goal="Prioritize retention and acquisition by customer segment.",
        sql=(
            "SELECT segment, COUNT(DISTINCT customer_id) AS customers, "
            "SUM(revenue) AS revenue, AVG(customer_lifetime_value) AS avg_ltv "
            "FROM customer_metrics GROUP BY segment ORDER BY revenue DESC;"
        ),
    ),
    DemoQuestion(
        question_id="discount_margin_risk",
        question="Are discounts helping revenue or damaging margin?",
        business_goal="Spot discount bands where margin erosion outweighs volume gains.",
        sql=(
            "SELECT discount_band, SUM(revenue) AS revenue, AVG(margin_rate) AS margin_rate "
            "FROM ecommerce_order_items GROUP BY discount_band ORDER BY discount_band;"
        ),
    ),
    DemoQuestion(
        question_id="repeat_purchase_health",
        question="How healthy is repeat purchasing by cohort?",
        business_goal="Evaluate whether older customer cohorts continue to reorder.",
        sql=(
            "SELECT signup_cohort, AVG(order_count) AS avg_orders, "
            "AVG(days_since_last_order) AS avg_recency FROM customer_metrics "
            "GROUP BY signup_cohort ORDER BY signup_cohort;"
        ),
    ),
)


def generate_ecommerce_data(seed: int = 42) -> dict[str, pd.DataFrame]:
    """Create deterministic ecommerce data with realistic relationships."""
    rng = np.random.default_rng(seed)
    customers = pd.DataFrame(
        {
            "customer_id": np.arange(1, 501),
            "segment": rng.choice(
                ["Enterprise", "Loyal", "Occasional", "At Risk"],
                size=500,
                p=[0.08, 0.27, 0.48, 0.17],
            ),
            "state": rng.choice(["CA", "TX", "NY", "FL", "IL", "WA", "MA"], size=500),
            "signup_date": pd.Timestamp("2023-01-01")
            + pd.to_timedelta(rng.integers(0, 720, size=500), unit="D"),
        }
    )

    categories = {
        "Electronics": (145.0, 0.32),
        "Clothing": (58.0, 0.48),
        "Home": (76.0, 0.41),
        "Books": (28.0, 0.55),
        "Sports": (64.0, 0.38),
    }
    products: list[dict[str, Any]] = []
    for category, (base_price, margin) in categories.items():
        for idx in range(1, 41):
            unit_price = max(8.0, rng.normal(base_price, base_price * 0.25))
            products.append(
                {
                    "product_id": len(products) + 1,
                    "product_name": f"{category} SKU {idx:02d}",
                    "category": category,
                    "unit_price": round(unit_price, 2),
                    "cost_price": round(unit_price * (1 - margin), 2),
                }
            )
    products_df = pd.DataFrame(products)

    orders = pd.DataFrame(
        {
            "order_id": np.arange(1, 4001),
            "customer_id": rng.integers(1, 501, size=4000),
            "order_date": pd.Timestamp("2025-01-01")
            + pd.to_timedelta(rng.integers(0, 365, size=4000), unit="D"),
            "status": rng.choice(
                ["completed", "shipped", "cancelled", "refunded"],
                size=4000,
                p=[0.78, 0.12, 0.06, 0.04],
            ),
        }
    )

    item_count = 9500
    order_items = pd.DataFrame(
        {
            "order_id": rng.choice(orders["order_id"], size=item_count),
            "product_id": rng.choice(products_df["product_id"], size=item_count),
            "quantity": rng.choice([1, 2, 3, 4], size=item_count, p=[0.58, 0.25, 0.12, 0.05]),
            "discount_pct": rng.choice(
                [0, 5, 10, 15, 20, 30],
                size=item_count,
                p=[0.55, 0.16, 0.12, 0.08, 0.06, 0.03],
            ),
        }
    )
    order_items = order_items.merge(products_df, on="product_id", how="left")
    order_items = order_items.merge(orders[["order_id", "order_date", "customer_id", "status"]], on="order_id")
    order_items = order_items[order_items["status"].isin(["completed", "shipped"])].copy()
    order_items["net_unit_price"] = order_items["unit_price"] * (1 - order_items["discount_pct"] / 100)
    order_items["revenue"] = order_items["quantity"] * order_items["net_unit_price"]
    order_items["profit"] = order_items["quantity"] * (order_items["net_unit_price"] - order_items["cost_price"])
    order_items["margin_rate"] = order_items["profit"] / order_items["revenue"]
    order_items["month"] = order_items["order_date"].dt.to_period("M").astype(str)
    order_items["discount_band"] = pd.cut(
        order_items["discount_pct"],
        bins=[-1, 0, 10, 20, 100],
        labels=["0%", "1-10%", "11-20%", "21%+"],
    ).astype(str)

    return {
        "customers": customers,
        "products": products_df,
        "orders": orders,
        "order_items": order_items,
    }


def _currency(value: float) -> str:
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _save_result(df: pd.DataFrame, output_dir: Path, question_id: str) -> str:
    path = output_dir / f"{question_id}.csv"
    df.to_csv(path, index=False)
    return str(path)


def analyze_question(
    question: DemoQuestion,
    data: dict[str, pd.DataFrame],
    output_dir: Path,
    chart_builder: ChartBuilder,
) -> DemoAnswer:
    """Run one deterministic demo analysis and generate chart artifacts."""
    items = data["order_items"]
    customers = data["customers"]
    charts = []

    if question.question_id == "revenue_by_category":
        result = (
            items.groupby("category", as_index=False)
            .agg(revenue=("revenue", "sum"), profit=("profit", "sum"))
            .sort_values("revenue", ascending=False)
        )
        result["margin_rate"] = result["profit"] / result["revenue"]
        top = result.iloc[0]
        low_margin = result.sort_values("margin_rate").iloc[0]
        artifact = chart_builder.bar_chart(
            result,
            x="category",
            y="revenue",
            title="Revenue by Product Category",
            name="demo_revenue_by_category",
        )
        charts.append(asdict(artifact))
        findings = [
            f"{top.category} leads revenue with {_currency(top.revenue)}.",
            f"{low_margin.category} has the lowest margin rate at {_pct(low_margin.margin_rate)}.",
        ]
        recommendations = [
            f"Protect inventory and campaign budget for {top.category}.",
            f"Review pricing and discounting in {low_margin.category} before scaling spend.",
        ]

    elif question.question_id == "monthly_revenue_trend":
        result = (
            items.groupby("month", as_index=False)
            .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
            .sort_values("month")
        )
        first = result.iloc[0].revenue
        last = result.iloc[-1].revenue
        growth = (last - first) / first
        artifact = chart_builder.line_chart(
            result,
            x="month",
            y="revenue",
            title="Monthly Revenue Trend",
            name="demo_monthly_revenue_trend",
        )
        charts.append(asdict(artifact))
        findings = [
            f"Revenue moved from {_currency(first)} to {_currency(last)}, a {_pct(growth)} change.",
            f"Peak month was {result.loc[result.revenue.idxmax(), 'month']}.",
        ]
        recommendations = [
            "Use peak-month category mix as the default merchandising playbook.",
            "Investigate dips with order count and category-level drilldowns.",
        ]

    elif question.question_id == "customer_segment_value":
        customer_revenue = items.groupby("customer_id", as_index=False).agg(
            revenue=("revenue", "sum"),
            order_count=("order_id", "nunique"),
        )
        metrics = customers.merge(customer_revenue, on="customer_id", how="left").fillna(
            {"revenue": 0, "order_count": 0}
        )
        result = (
            metrics.groupby("segment", as_index=False)
            .agg(customers=("customer_id", "nunique"), revenue=("revenue", "sum"), avg_ltv=("revenue", "mean"))
            .sort_values("revenue", ascending=False)
        )
        top = result.iloc[0]
        artifact = chart_builder.bar_chart(
            result,
            x="segment",
            y="avg_ltv",
            title="Average Customer Value by Segment",
            name="demo_customer_segment_value",
        )
        charts.append(asdict(artifact))
        findings = [
            f"{top.segment} contributes the most revenue at {_currency(top.revenue)}.",
            f"Average customer value ranges from {_currency(result.avg_ltv.min())} to {_currency(result.avg_ltv.max())}.",
        ]
        recommendations = [
            f"Build retention offers for {top.segment} customers before acquisition spend.",
            "Use segment-level LTV as a bidding guardrail for paid marketing.",
        ]

    elif question.question_id == "discount_margin_risk":
        result = (
            items.groupby("discount_band", as_index=False)
            .agg(revenue=("revenue", "sum"), margin_rate=("margin_rate", "mean"), orders=("order_id", "nunique"))
            .sort_values("discount_band")
        )
        risky = result.sort_values("margin_rate").iloc[0]
        artifact = chart_builder.bar_chart(
            result,
            x="discount_band",
            y="margin_rate",
            title="Margin Rate by Discount Band",
            name="demo_discount_margin_risk",
        )
        charts.append(asdict(artifact))
        findings = [
            f"The {risky.discount_band} discount band has the weakest margin at {_pct(risky.margin_rate)}.",
            f"Discounted orders still represent {int(result[result.discount_band != '0%'].orders.sum())} orders.",
        ]
        recommendations = [
            f"Require margin approval for {risky.discount_band} promotions.",
            "Shift broad discounts toward targeted win-back and inventory-clearance use cases.",
        ]

    elif question.question_id == "repeat_purchase_health":
        customer_orders = items.groupby("customer_id", as_index=False).agg(
            order_count=("order_id", "nunique"),
            last_order=("order_date", "max"),
            revenue=("revenue", "sum"),
        )
        metrics = customers.merge(customer_orders, on="customer_id", how="left")
        metrics["order_count"] = metrics["order_count"].fillna(0)
        metrics["days_since_last_order"] = (
            pd.Timestamp("2025-12-31") - metrics["last_order"]
        ).dt.days.fillna(365)
        metrics["signup_cohort"] = metrics["signup_date"].dt.to_period("Q").astype(str)
        result = (
            metrics.groupby("signup_cohort", as_index=False)
            .agg(avg_orders=("order_count", "mean"), avg_recency=("days_since_last_order", "mean"))
            .sort_values("signup_cohort")
        )
        best = result.sort_values("avg_orders", ascending=False).iloc[0]
        artifact = chart_builder.line_chart(
            result,
            x="signup_cohort",
            y="avg_orders",
            title="Average Repeat Orders by Signup Cohort",
            name="demo_repeat_purchase_health",
        )
        charts.append(asdict(artifact))
        findings = [
            f"{best.signup_cohort} has the strongest repeat purchase behavior at {best.avg_orders:.2f} orders/customer.",
            f"Average recency ranges from {result.avg_recency.min():.0f} to {result.avg_recency.max():.0f} days.",
        ]
        recommendations = [
            "Use cohort-level repeat rate to trigger lifecycle campaigns.",
            "Create reactivation journeys for cohorts with high recency and low repeat order counts.",
        ]

    else:
        raise ValueError(f"Unknown demo question: {question.question_id}")

    csv_path = _save_result(result, output_dir, question.question_id)
    return DemoAnswer(
        question_id=question.question_id,
        question=question.question,
        business_goal=question.business_goal,
        sql=question.sql,
        row_count=len(result),
        findings=findings,
        recommendations=recommendations,
        charts=charts,
        output_csv=csv_path,
    )


def render_markdown(answers: list[DemoAnswer], output_dir: Path) -> str:
    """Render a portfolio-ready markdown report."""
    lines = [
        "# AI Data Analyst Portfolio Demo",
        "",
        "This report is generated offline from deterministic ecommerce data. It demonstrates the same",
        "business workflow as the analyst system: question, SQL plan, analysis, chart, and recommendation.",
        "",
        "## Executive Summary",
        "",
        f"- Answered {len(answers)} realistic ecommerce business questions.",
        "- Generated reproducible SQL-style analysis outputs and charts without external services.",
        "- Exported per-question result CSVs for auditability.",
        "",
    ]

    for answer in answers:
        lines.extend(
            [
                f"## {answer.question}",
                "",
                f"**Business goal:** {answer.business_goal}",
                "",
                "**SQL plan:**",
                "",
                "```sql",
                answer.sql,
                "```",
                "",
                f"**Rows returned:** {answer.row_count}",
                "",
                "**Key findings:**",
            ]
        )
        lines.extend(f"- {finding}" for finding in answer.findings)
        lines.extend(["", "**Recommendations:**"])
        lines.extend(f"- {recommendation}" for recommendation in answer.recommendations)
        lines.extend(["", "**Artifacts:**", f"- Result CSV: `{answer.output_csv}`"])
        for chart in answer.charts:
            lines.append(f"- Chart: `{chart['path']}`")
        lines.append("")

    report = "\n".join(lines)
    (output_dir / "portfolio_demo_report.md").write_text(report)
    (output_dir / "portfolio_demo_report.html").write_text(render_html(answers))
    return report


def render_html(answers: list[DemoAnswer]) -> str:
    """Render a polished standalone HTML report with embedded chart images."""
    cards = []
    for answer in answers:
        findings = "\n".join(f"<li>{finding}</li>" for finding in answer.findings)
        recommendations = "\n".join(f"<li>{recommendation}</li>" for recommendation in answer.recommendations)
        charts = "\n".join(
            f"<figure><img src='{Path(chart['path']).name}' alt='{chart['title']}' />"
            f"<figcaption>{chart['title']}</figcaption></figure>"
            for chart in answer.charts
            if chart["path"].endswith(".png")
        )
        cards.append(
            f"""
            <section class="question">
              <div class="question-copy">
                <p class="eyebrow">{answer.business_goal}</p>
                <h2>{answer.question}</h2>
                <p class="metric">{answer.row_count} result rows</p>
                <h3>Key Findings</h3>
                <ul>{findings}</ul>
                <h3>Recommendations</h3>
                <ul>{recommendations}</ul>
                <details>
                  <summary>SQL plan</summary>
                  <pre><code>{answer.sql}</code></pre>
                </details>
              </div>
              <div class="chart-stack">{charts}</div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Data Analyst Portfolio Demo</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6c7b;
      --line: #d8dee8;
      --panel: #ffffff;
      --band: #f5f7fb;
      --accent: #0f766e;
    }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--band);
      line-height: 1.5;
    }}
    header {{
      padding: 48px min(7vw, 88px) 28px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    header h1 {{
      margin: 0 0 12px;
      font-size: clamp(32px, 5vw, 56px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    header p {{
      max-width: 900px;
      margin: 0;
      color: var(--muted);
      font-size: 18px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      padding: 20px min(7vw, 88px);
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    .summary div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--panel);
    }}
    .summary strong {{
      display: block;
      font-size: 24px;
    }}
    main {{
      padding: 24px min(7vw, 88px) 64px;
    }}
    .question {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
      gap: 24px;
      align-items: start;
      padding: 24px 0;
      border-bottom: 1px solid var(--line);
    }}
    .eyebrow {{
      color: var(--accent);
      font-weight: 700;
      margin: 0 0 8px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 26px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 20px 0 8px;
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
    }}
    .metric {{
      display: inline-block;
      margin: 0;
      padding: 6px 10px;
      border-radius: 999px;
      background: #e6f4f1;
      color: #075e56;
      font-weight: 700;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    figure {{
      margin: 0 0 14px;
      padding: 10px;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    img {{
      max-width: 100%;
      height: auto;
      display: block;
    }}
    figcaption {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 8px;
    }}
    details {{
      margin-top: 18px;
    }}
    pre {{
      overflow-x: auto;
      padding: 12px;
      border-radius: 8px;
      background: #101828;
      color: #eef2ff;
      font-size: 13px;
    }}
    @media (max-width: 860px) {{
      .question {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AI Data Analyst Portfolio Demo</h1>
    <p>Offline, reproducible showcase of an analytics workflow: business question, SQL plan, computed analysis, chart, and recommendation.</p>
  </header>
  <section class="summary">
    <div><strong>{len(answers)}</strong>Business questions</div>
    <div><strong>{sum(len(answer.charts) for answer in answers)}</strong>Generated charts</div>
    <div><strong>{sum(answer.row_count for answer in answers)}</strong>Result rows summarized</div>
  </section>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""


def run_demo(output_dir: str = "output/portfolio_demo", seed: int = 42) -> dict[str, Any]:
    """Run the full offline portfolio demo."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    data = generate_ecommerce_data(seed=seed)
    chart_builder = ChartBuilder(str(output_path))
    answers = [analyze_question(question, data, output_path, chart_builder) for question in QUESTIONS]
    report = render_markdown(answers, output_path)
    return {
        "output_dir": str(output_path),
        "report_markdown": str(output_path / "portfolio_demo_report.md"),
        "report_html": str(output_path / "portfolio_demo_report.html"),
        "question_count": len(answers),
        "chart_count": sum(len(answer.charts) for answer in answers),
        "answers": [asdict(answer) for answer in answers],
        "report_preview": report[:1000],
    }


def main() -> None:
    """CLI entrypoint for the portfolio demo."""
    parser = argparse.ArgumentParser(description="Run the offline AI Data Analyst portfolio demo.")
    parser.add_argument("--output-dir", default="output/portfolio_demo")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = run_demo(output_dir=args.output_dir, seed=args.seed)
    print(f"Generated portfolio demo in {result['output_dir']}")
    print(f"Report: {result['report_markdown']}")
    print(f"Charts: {result['chart_count']}")


if __name__ == "__main__":
    main()
