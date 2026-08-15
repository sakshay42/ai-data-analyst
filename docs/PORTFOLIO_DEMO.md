# AI Data Analyst Portfolio Demo

This report is generated offline from deterministic ecommerce data. It demonstrates the same
business workflow as the analyst system: question, SQL plan, analysis, chart, and recommendation.

## Executive Summary

- Answered 5 realistic ecommerce business questions.
- Generated reproducible SQL-style analysis outputs and charts without external services.
- Exported per-question result CSVs for auditability.

## Which product categories drive the most revenue and margin?

**Business goal:** Find the categories that deserve merchandising and inventory focus.

**SQL plan:**

```sql
SELECT category, SUM(revenue) AS revenue, SUM(profit) AS profit, SUM(profit) / NULLIF(SUM(revenue), 0) AS margin_rate FROM ecommerce_order_items GROUP BY category ORDER BY revenue DESC;
```

**Rows returned:** 5

**Key findings:**
- Electronics leads revenue with $381,067.
- Electronics has the lowest margin rate at 28.0%.

**Recommendations:**
- Protect inventory and campaign budget for Electronics.
- Review pricing and discounting in Electronics before scaling spend.

**Artifacts:**
- Result CSV: `output/portfolio_demo/revenue_by_category.csv`
- Chart: `output/portfolio_demo/demo_revenue_by_category.png`

## How is revenue trending month over month?

**Business goal:** Identify growth, seasonality, and recent momentum.

**SQL plan:**

```sql
SELECT month, SUM(revenue) AS revenue, COUNT(DISTINCT order_id) AS orders FROM ecommerce_orders GROUP BY month ORDER BY month;
```

**Rows returned:** 12

**Key findings:**
- Revenue moved from $82,221 to $78,381, a -4.7% change.
- Peak month was 2025-04.

**Recommendations:**
- Use peak-month category mix as the default merchandising playbook.
- Investigate dips with order count and category-level drilldowns.

**Artifacts:**
- Result CSV: `output/portfolio_demo/monthly_revenue_trend.csv`
- Chart: `output/portfolio_demo/demo_monthly_revenue_trend.png`

## Which customer segments have the highest value?

**Business goal:** Prioritize retention and acquisition by customer segment.

**SQL plan:**

```sql
SELECT segment, COUNT(DISTINCT customer_id) AS customers, SUM(revenue) AS revenue, AVG(customer_lifetime_value) AS avg_ltv FROM customer_metrics GROUP BY segment ORDER BY revenue DESC;
```

**Rows returned:** 4

**Key findings:**
- Occasional contributes the most revenue at $485,323.
- Average customer value ranges from $1,896 to $2,056.

**Recommendations:**
- Build retention offers for Occasional customers before acquisition spend.
- Use segment-level LTV as a bidding guardrail for paid marketing.

**Artifacts:**
- Result CSV: `output/portfolio_demo/customer_segment_value.csv`
- Chart: `output/portfolio_demo/demo_customer_segment_value.png`

## Are discounts helping revenue or damaging margin?

**Business goal:** Spot discount bands where margin erosion outweighs volume gains.

**SQL plan:**

```sql
SELECT discount_band, SUM(revenue) AS revenue, AVG(margin_rate) AS margin_rate FROM ecommerce_order_items GROUP BY discount_band ORDER BY discount_band;
```

**Rows returned:** 4

**Key findings:**
- The 21%+ discount band has the weakest margin at 18.3%.
- Discounted orders still represent 3026 orders.

**Recommendations:**
- Require margin approval for 21%+ promotions.
- Shift broad discounts toward targeted win-back and inventory-clearance use cases.

**Artifacts:**
- Result CSV: `output/portfolio_demo/discount_margin_risk.csv`
- Chart: `output/portfolio_demo/demo_discount_margin_risk.png`

## How healthy is repeat purchasing by cohort?

**Business goal:** Evaluate whether older customer cohorts continue to reorder.

**SQL plan:**

```sql
SELECT signup_cohort, AVG(order_count) AS avg_orders, AVG(days_since_last_order) AS avg_recency FROM customer_metrics GROUP BY signup_cohort ORDER BY signup_cohort;
```

**Rows returned:** 8

**Key findings:**
- 2024Q3 has the strongest repeat purchase behavior at 6.95 orders/customer.
- Average recency ranges from 49 to 73 days.

**Recommendations:**
- Use cohort-level repeat rate to trigger lifecycle campaigns.
- Create reactivation journeys for cohorts with high recency and low repeat order counts.

**Artifacts:**
- Result CSV: `output/portfolio_demo/repeat_purchase_health.csv`
- Chart: `output/portfolio_demo/demo_repeat_purchase_health.png`
