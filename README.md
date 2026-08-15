# 📊 AI Data Analyst

**Plain-Language Business Questions → SQL → Statistical Analysis → Visual Reports**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-purple.svg)](https://github.com/langchain-ai/langgraph)
[![OpenAI](https://img.shields.io/badge/LLM-GPT--4o-green.svg)](https://openai.com/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-blue.svg)](https://www.postgresql.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-ff4b4b.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

AI Data Analyst is a production-grade, end-to-end analytics pipeline that transforms plain-language business questions into comprehensive visual reports. You ask *"What are the top 5 products by revenue?"* and the system introspects your database schema, decomposes the question into an analysis plan, generates and executes safe SQL, runs statistical analysis, produces charts, and delivers a structured markdown report — all orchestrated by a LangGraph DAG state machine with typed Pydantic state contracts.

The pipeline supports 4 observability providers (LangSmith, Langfuse, Helicone, Braintrust) that can be enabled independently via environment toggles. SQL execution is locked down with keyword blocklists, read-only transactions, statement timeouts, and row limits. An offline evaluation framework powered by Braintrust scores SQL validity, statistical accuracy, and report quality across 37 curated test cases with 7 custom scorers.

---

## Architecture

### High-Level Pipeline

```mermaid
graph LR
    Q["Business Question"] --> SI["Schema<br/>Introspection"]
    SI --> PL["Planner<br/>GPT-4o"]
    PL --> SQL["SQL Agent<br/>GPT-4o"]
    SQL --> R{"Route"}
    R -->|success| AN["Analyst<br/>pandas + scipy"]
    R -->|error & retries < 2| EH["Error Handler<br/>GPT-4o"]
    R -->|error & retries ≥ 2| RP2["Reporter<br/>(partial)"]
    R -->|empty results| RP3["Reporter<br/>(partial)"]
    EH --> SQL
    AN --> VZ["Visualizer<br/>GPT-4o + matplotlib"]
    VZ --> RP["Reporter<br/>GPT-4o"]
    RP --> OUT["Markdown Report<br/>+ Charts"]

    style Q fill:#e3f2fd
    style AN fill:#e8f5e9
    style RP fill:#fff8e1
    style OUT fill:#f3e5f5
```

### Pipeline Components

| Stage | Component | Model / Tool | LLM? | Purpose |
|-------|-----------|-------------|------|---------|
| **1. Introspect** | `SchemaIntrospector` | `information_schema` + `pg_catalog` | No | Build text summary of all tables, columns, types, PKs, and row counts |
| **2. Plan** | `planner` | GPT-4o (structured output) | Yes | Decompose question into sub-questions, required tables, analysis type, visualizations |
| **3. SQL** | `sql_agent` | GPT-4o → `psycopg3` | Yes | Generate safe SELECT query, strip markdown, execute against PostgreSQL |
| **4. Analyse** | `analyst` | `StatsToolkit` (pandas, scipy) | No | Descriptive stats, correlations, t-tests, trend analysis, group comparisons |
| **5. Visualize** | `visualizer` | GPT-4o → `ChartBuilder` | Yes | LLM recommends 1–3 chart types, ChartBuilder renders PNG/HTML |
| **6. Report** | `reporter` | GPT-4o | Yes | Generate structured markdown: Executive Summary → Findings → Recommendations |

---

## How the Pipeline Works

### Stage 1: Schema Introspection

Before any LLM call, the pipeline reads the live database schema to give the planner and SQL agent accurate context. The `SchemaIntrospector` queries `information_schema.columns` and `pg_catalog` to discover every table, column type, nullability, default value, primary key, and estimated row count.

**Output** — a text summary injected into every downstream prompt:

```
Table: customers (~500 rows)
  customer_id     INTEGER   PK
  first_name      VARCHAR
  last_name       VARCHAR
  email           VARCHAR   UNIQUE
  city            VARCHAR
  state           VARCHAR
  signup_date     DATE
  is_active       BOOLEAN

Table: products (~200 rows)
  product_id      INTEGER   PK
  product_name    VARCHAR
  category        VARCHAR
  subcategory     VARCHAR
  unit_price      NUMERIC
  cost_price      NUMERIC
  stock_qty       INTEGER
  is_available    BOOLEAN
...
```

**Key methods:**
- `get_tables(schema="public")` — Returns `list[TableInfo]` with columns and PK info
- `get_schema_summary(schema="public")` — Formatted text summary for LLM context
- `get_sample_values(table, column, limit=10)` — Distinct sample values for a column

---

### Stage 2: Planner

The planner uses GPT-4o with **structured output** to decompose the user's question into an `AnalysisPlan` Pydantic model. This ensures downstream stages know exactly which tables to query, what type of analysis to run, and which charts to produce.

**System prompt:**

```
You are a data analysis planner. Given a user's business question and a database schema,
create a structured analysis plan.

Your plan should include:
1. The original question restated clearly
2. Sub-questions that need to be answered via SQL
3. Which tables are required
4. The type of analysis (trend, comparison, distribution, ranking, aggregation)
5. Suggested visualizations (bar, line, pie, scatter, histogram)

Be specific about what SQL queries are needed and what analysis to perform.
```

**Structured output — `AnalysisPlan`:**

| Field | Type | Description |
|-------|------|-------------|
| `question` | `str` | Original question restated |
| `sub_questions` | `list[str]` | Decomposed sub-questions for SQL |
| `required_tables` | `list[str]` | Tables needed (e.g., `["orders", "order_items", "products"]`) |
| `analysis_type` | `str` | One of: `"trend"`, `"comparison"`, `"distribution"`, `"ranking"`, `"aggregation"` |
| `suggested_visualizations` | `list[str]` | Chart types (e.g., `["bar", "pie"]`) |

---

### Stage 3: SQL Agent

The SQL agent generates a single PostgreSQL query from the analysis plan and schema summary, then executes it through the connection pool with full safety enforcement.

**System prompt:**

```
You are a SQL expert. Given a database schema and an analysis plan, generate a single SQL
query that answers the user's question.

Rules:
- Only generate SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
- Use standard PostgreSQL syntax
- Include appropriate JOINs, GROUP BY, ORDER BY as needed
- Use aliases for readability
- Limit results to a reasonable number unless aggregating
- Output ONLY the SQL query, no explanation or markdown formatting
```

**Safety pipeline:**

1. **Keyword blocklist** — Rejects queries containing: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT` (case-insensitive token matching)
2. **Whitelist** — Only `SELECT` and `WITH` (CTE) statements pass
3. **Markdown stripping** — Removes ` ```sql ` fences and backtick wrapping
4. **Read-only session** — `SET default_transaction_read_only = ON`
5. **Statement timeout** — `SET statement_timeout = '30s'` (configurable)
6. **Max row limit** — 10,000 rows (configurable via `DB_MAX_ROWS`)

**Error handling & retry:**

```mermaid
graph TD
    SQL["SQL Agent<br/>generates & executes"] --> CHECK{{"Error?"}}
    CHECK -->|No error| DATA["QueryResult<br/>columns + rows"]
    DATA --> EMPTY{{"row_count == 0?"}}
    EMPTY -->|Yes| PARTIAL["Reporter<br/>(partial report)"]
    EMPTY -->|No| ANALYST["Analyst"]
    CHECK -->|Error| RETRY{{"retry_count < 2?"}}
    RETRY -->|Yes| HANDLER["Error Handler<br/>+ error feedback"]
    HANDLER --> SQL
    RETRY -->|No| PARTIAL

    style SQL fill:#e3f2fd
    style ANALYST fill:#e8f5e9
    style PARTIAL fill:#fff3e0
```

The error handler feeds the original SQL, the error message, and the schema back to GPT-4o with instructions to fix the query. Maximum 2 retries before producing a partial report.

---

### Stage 4: Analyst

The analyst node requires **no LLM** — it runs pure Python statistical analysis using `StatsToolkit` on the query results DataFrame.

**StatsToolkit methods:**

| Method | What It Computes | Library |
|--------|-----------------|---------|
| `descriptive_stats(columns)` | Mean, std, min, max, median, skewness, kurtosis | pandas + scipy |
| `correlation_matrix(columns)` | Pearson pairwise correlations | pandas |
| `t_test(col_a, col_b)` | Welch's independent two-sample t-test (t-stat, p-value) | scipy.stats |
| `trend_analysis(date_col, value_col)` | Linear regression slope, R², p-value, direction | scipy.stats |
| `group_comparison(group_col, value_col)` | One-way ANOVA F-statistic and p-value per group | scipy.stats |
| `full_analysis()` | Runs all applicable methods, returns `StatsResult` | All above |

**Output — `AnalysisResult`:**

```python
AnalysisResult(
    summary_stats={"revenue": {"mean": 150.32, "std": 89.41, "min": 5.99, ...}},
    correlations={"unit_price_vs_quantity": -0.23},
    tests=[{"test": "anova", "f_stat": 12.34, "p_value": 0.001}],
    trends={"monthly_revenue": {"slope": 245.6, "r_squared": 0.87, "direction": "increasing"}},
    insights=["Revenue shows a significant upward trend (R²=0.87, p<0.001)", ...]
)
```

---

### Stage 5: Visualizer

The visualizer uses GPT-4o to recommend 1–3 charts based on the analysis results and data schema, then `ChartBuilder` renders them.

**System prompt:**

```
You are a data visualization expert. Given analysis results and a data schema,
recommend the best chart(s) to visualize the findings.

For each chart, specify:
- chart_type: one of "bar", "line", "pie", "scatter", "histogram"
- x_column: column name for x-axis
- y_column: column name for y-axis
- title: descriptive chart title

Return a list of 1-3 chart specifications. Choose charts that best communicate
the key findings.
```

**Supported chart types:**

| Chart Type | Method | Renderer | Output |
|------------|--------|----------|--------|
| `bar` | `bar_chart(df, x, y, title, name)` | seaborn | PNG |
| `line` | `line_chart(df, x, y, title, name)` | seaborn (with markers) | PNG |
| `pie` | `pie_chart(df, labels, values, title, name)` | matplotlib | PNG |
| `scatter` | `scatter_plot(df, x, y, title, name, hue)` | seaborn | PNG |
| `histogram` | `histogram(df, column, title, name, bins=30)` | seaborn (with KDE) | PNG |
| `plotly_interactive` | `plotly_interactive(df, type, x, y, title, name)` | plotly | HTML |

**Theme:** seaborn `whitegrid` with `husl` color palette. Column existence is validated against the DataFrame before rendering — invalid columns are skipped gracefully.

---

### Stage 6: Reporter

The reporter synthesizes all upstream outputs — the original question, SQL query, statistics, insights, and chart artifacts — into a structured markdown report.

**System prompt:**

```
You are a business analyst writing a clear, actionable report. Given analysis results,
SQL query, and charts, create a comprehensive markdown report.

Structure your report as:
1. **Executive Summary** - Key findings in 2-3 sentences
2. **Question** - The original business question
3. **Methodology** - How the analysis was performed (SQL query summary, statistical methods)
4. **Key Findings** - Detailed findings with numbers
5. **Visualizations** - Reference generated charts
6. **Recommendations** - Actionable next steps based on findings

Use clear business language. Include specific numbers and percentages. If there were
errors or missing data, note them transparently.
```

The reporter handles **partial reports** gracefully — if the SQL agent failed after 2 retries or returned empty results, the reporter acknowledges the limitation and reports what it can.

---

## State Schema

All data flows through a single Pydantic state object (`AnalystState`) that is passed between LangGraph nodes. Each node reads what it needs and writes its outputs back.

### `AnalystState` Fields

| Field | Type | Set By | Description |
|-------|------|--------|-------------|
| `question` | `str` | Input | Original user question |
| `schema_summary` | `str` | Introspector | Text summary of database schema |
| `plan` | `AnalysisPlan` | Planner | Structured analysis plan |
| `query_result` | `QueryResult` | SQL Agent | Query output (columns, rows, error) |
| `sql_retry_count` | `int` | Error Handler | Number of SQL retries (max 2) |
| `analysis` | `AnalysisResult` | Analyst | Statistical analysis output |
| `charts` | `list[ChartArtifact]` | Visualizer | Generated chart files |
| `report` | `str` | Reporter | Final markdown report |
| `errors` | `Annotated[list[str], operator.add]` | Any node | Accumulated errors (reducer) |

### Sub-Models

**`QueryResult`:**
| Field | Type | Description |
|-------|------|-------------|
| `sql` | `str` | Generated SQL query |
| `columns` | `list[str]` | Column names from result set |
| `rows` | `list[dict[str, Any]]` | Data rows as dictionaries |
| `row_count` | `int` | Number of returned rows |
| `error` | `str` | Error message (empty on success) |

**`ChartArtifact`:**
| Field | Type | Description |
|-------|------|-------------|
| `path` | `str` | File path to rendered chart |
| `chart_type` | `str` | `"bar"`, `"line"`, `"pie"`, `"scatter"`, `"histogram"`, `"plotly_*"` |
| `title` | `str` | Chart title |
| `description` | `str` | What the chart shows |

---

## Observability Architecture

AI Data Analyst supports 4 observability providers that can be enabled independently. Each uses a different integration mechanism to avoid conflicts.

### Provider Integration

| Provider | Mechanism | Purpose | Conflicts |
|----------|-----------|---------|-----------|
| **LangSmith** | Environment variables | Auto-traces all LangChain/LangGraph calls | None |
| **Langfuse** | Callback handler | Open-source tracing with timeline view | None |
| **Helicone** | Proxy `base_url` | Cost tracking, latency dashboards | Braintrust (shares proxy slot) |
| **Braintrust** | Proxy `base_url` + eval scripts | Offline evaluation framework | Helicone (shares proxy slot) |

### Proxy Conflict Resolution

Helicone and Braintrust both override the OpenAI `base_url` to route traffic through their proxies. Since only one proxy can be active at a time:

- **At runtime:** Helicone wins — it provides real-time cost and latency tracking
- **For offline evals:** Braintrust is used — evaluation scripts set the Braintrust proxy explicitly

### Configuration

```bash
# .env — toggle each provider independently
LANGSMITH_ENABLED=false
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=ai-data-analyst

LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

HELICONE_ENABLED=false
HELICONE_API_KEY=sk-helicone-...

BRAINTRUST_ENABLED=false
BRAINTRUST_API_KEY=bt-...
```

### Integration Points

- **`ObservabilityManager`** — Central class that holds active callbacks, proxy kwargs, and provider list
- **`configure_observability(settings)`** — Initializes all enabled providers at startup
- **`create_llm(settings, manager, node_name)`** — Factory that creates `ChatOpenAI` with correct proxy and callbacks
- **`@trace_node(node_name)`** — Decorator applied to each agent node for timing and exception logging
- **`CompositeCallbackManager`** — Aggregates multiple callback handlers with `add_handler()`, `with_metadata()`, `get_config()`

---

## SQL Safety Features

All SQL execution passes through multiple safety layers before reaching the database.

### Keyword Blocklist

| Blocked Keyword | Risk |
|----------------|------|
| `INSERT` | Data modification |
| `UPDATE` | Data modification |
| `DELETE` | Data deletion |
| `DROP` | Schema destruction |
| `ALTER` | Schema modification |
| `CREATE` | Schema modification |
| `TRUNCATE` | Data deletion |
| `GRANT` | Privilege escalation |

### Additional Safeguards

| Safeguard | Implementation | Default |
|-----------|---------------|---------|
| **Read-only transactions** | `SET default_transaction_read_only = ON` on each connection | Always on |
| **Statement timeout** | `SET statement_timeout = '30s'` | 30 seconds |
| **Max row limit** | Query results capped at N rows | 10,000 |
| **Connection pool** | `psycopg_pool.ConnectionPool` with min/max bounds | 2–10 connections |
| **Whitelist** | Only `SELECT` and `WITH` (CTE) statements allowed | Always on |
| **Markdown stripping** | Removes ` ```sql ` fences and backtick wrapping before execution | Always on |

---

## Seed Database

The project includes a complete e-commerce seed database with 5 tables and ~22,700 rows of realistic data.

### Tables

| Table | Rows | Description |
|-------|------|-------------|
| `customers` | ~500 | Customer profiles with demographics and signup dates |
| `products` | ~200 | Product catalog across 5 categories |
| `orders` | ~5,000 | Orders with status tracking and shipping costs |
| `order_items` | ~15,000 | Line items (~3 per order) with quantities and discounts |
| `reviews` | ~2,000 | Product reviews with 1–5 ratings and text |

### Schema Details

**`customers`** (~500 rows)
| Column | Type | Notes |
|--------|------|-------|
| `customer_id` | INTEGER | PK |
| `first_name` | VARCHAR | |
| `last_name` | VARCHAR | |
| `email` | VARCHAR | UNIQUE |
| `city` | VARCHAR | |
| `state` | VARCHAR | Indexed |
| `signup_date` | DATE | Indexed |
| `is_active` | BOOLEAN | |

**`products`** (~200 rows)
| Column | Type | Notes |
|--------|------|-------|
| `product_id` | INTEGER | PK |
| `product_name` | VARCHAR | |
| `category` | VARCHAR | Indexed — Electronics (50), Clothing (50), Home & Garden (40), Books (30), Sports (30) |
| `subcategory` | VARCHAR | |
| `unit_price` | NUMERIC | |
| `cost_price` | NUMERIC | |
| `stock_qty` | INTEGER | |
| `is_available` | BOOLEAN | |

**`orders`** (~5,000 rows)
| Column | Type | Notes |
|--------|------|-------|
| `order_id` | INTEGER | PK |
| `customer_id` | INTEGER | FK → customers |
| `order_date` | DATE | Indexed — range: 2024-01 to 2025-12 |
| `status` | VARCHAR | Indexed — pending, processing, shipped, completed, cancelled, refunded |
| `shipping_cost` | NUMERIC | |
| `total_amount` | NUMERIC | |

**`order_items`** (~15,000 rows)
| Column | Type | Notes |
|--------|------|-------|
| `item_id` | INTEGER | PK |
| `order_id` | INTEGER | FK → orders, indexed |
| `product_id` | INTEGER | FK → products, indexed |
| `quantity` | INTEGER | |
| `unit_price` | NUMERIC | |
| `discount_pct` | NUMERIC | |

**`reviews`** (~2,000 rows)
| Column | Type | Notes |
|--------|------|-------|
| `review_id` | INTEGER | PK |
| `product_id` | INTEGER | FK → products, indexed |
| `customer_id` | INTEGER | FK → customers, indexed |
| `rating` | INTEGER | 1–5, indexed |
| `review_title` | VARCHAR | |
| `review_text` | TEXT | |
| `review_date` | DATE | Indexed |
| `verified` | BOOLEAN | |

---

## Evaluation Framework

AI Data Analyst includes an offline evaluation framework powered by Braintrust with 7 custom scorers across 3 evaluation dimensions.

```mermaid
graph TD
    subgraph "Datasets"
        D1["sql_generation.json<br/>16 test cases"]
        D2["analysis_quality.json<br/>11 test cases"]
        D3["report_quality.json<br/>10 test cases"]
    end

    subgraph "Scorers"
        S1["SQLValidity"]
        S2["SQLCorrectness"]
        S3["SQLEfficiency"]
        S4["StatisticalAccuracy"]
        S5["InsightRelevance"]
        S6["Completeness"]
        S7["Clarity"]
    end

    D1 --> S1 & S2 & S3
    D2 --> S4 & S5
    D3 --> S6 & S7

    S1 & S2 & S3 & S4 & S5 & S6 & S7 --> BT["Braintrust<br/>Dashboard"]

    style D1 fill:#e3f2fd
    style D2 fill:#e8f5e9
    style D3 fill:#fff8e1
    style BT fill:#f3e5f5
```

### Scorers

| Scorer | Dimension | What It Measures | Score Range | Key Logic |
|--------|-----------|-----------------|-------------|-----------|
| **SQLValidity** | SQL | Syntax validity via `sqlparse`; blocks forbidden keywords | 0.0–1.0 | Allowed: `SELECT`, `WITH`. Forbidden: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT` |
| **SQLCorrectness** | SQL | Row count and content matching against expected output | 0.0–1.0 | Compares actual vs expected row counts and key values |
| **SQLEfficiency** | SQL | Anti-pattern detection | 0.0–1.0 | Penalizes: `SELECT *`, Cartesian joins, `SELECT DISTINCT *` on large tables |
| **StatisticalAccuracy** | Analysis | Computed stats vs expected values | 0.0–1.0 | Tolerance: 5% relative, 0.5 absolute. Checks mean, std, min, max, median, count, trend direction |
| **InsightRelevance** | Analysis | Keyword coverage in generated insights | 0.0–1.0 | 60% keyword coverage threshold to pass |
| **Completeness** | Report | Required sections present in markdown | 0.0–1.0 | Supports markdown headings, bold headings, plain text detection. 80% threshold |
| **Clarity** | Report | Readability heuristics | 0.0–1.0 | Checks formatting (headings, bullets), sentence length (10–25 words ideal), specificity (numbers present), absence of vague phrases. 60% threshold |

### Datasets

| Dataset | Test Cases | Difficulty | Description |
|---------|-----------|------------|-------------|
| `sql_generation.json` | 16 | 5 easy, 5 medium, 6 hard | Question → expected SQL pairs with difficulty-weighted scoring |
| `analysis_quality.json` | 11 | — | Analysis inputs with expected statistical outputs |
| `report_quality.json` | 10 | — | Report inputs with expected sections and keywords |

### Running Evaluations

```bash
# SQL generation evaluation
poetry run python evals/eval_sql_generation.py

# Analysis quality evaluation
poetry run python evals/eval_analysis.py

# Report quality evaluation
poetry run python evals/eval_report.py
```

Results are uploaded to the Braintrust dashboard for visualization and comparison across runs.

---

## End-to-End Example

Here is a complete trace showing what happens at each pipeline stage for a single question.

### Question

> *"What are the top 5 products by revenue?"*

### Stage 1 — Schema Introspection

```
Introspected 5 tables: customers (500 rows), products (200 rows), orders (5000 rows),
order_items (15000 rows), reviews (2000 rows)
```

### Stage 2 — Planner Output

```json
{
  "question": "What are the top 5 products by revenue?",
  "sub_questions": [
    "Calculate total revenue per product by joining order_items with products",
    "Rank products by total revenue descending and take the top 5"
  ],
  "required_tables": ["products", "order_items"],
  "analysis_type": "ranking",
  "suggested_visualizations": ["bar"]
}
```

### Stage 3 — Generated SQL

```sql
SELECT
    p.product_name,
    p.category,
    SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100)) AS total_revenue,
    SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.product_name, p.category
ORDER BY total_revenue DESC
LIMIT 5;
```

**Result:** 5 rows returned

| product_name | category | total_revenue | units_sold |
|-------------|----------|--------------|------------|
| Ultra HD Monitor | Electronics | 45,230.50 | 312 |
| Wireless Headphones | Electronics | 38,912.00 | 487 |
| Running Shoes Pro | Sports | 32,445.75 | 421 |
| Smart Watch X1 | Electronics | 28,890.20 | 198 |
| Winter Jacket | Clothing | 25,120.80 | 356 |

### Stage 4 — Statistical Analysis

```
Summary Statistics (total_revenue):
  mean:     34,119.85
  std:       8,052.31
  min:      25,120.80
  max:      45,230.50
  median:   32,445.75

Insights:
  - Top product revenue (Ultra HD Monitor: $45,230.50) is 1.8x the 5th-ranked product
  - Electronics dominates with 3 of top 5 positions (60%)
  - Revenue range spans $20,109.70 across top 5 products
```

### Stage 5 — Visualization

LLM recommends a horizontal bar chart. ChartBuilder produces:

```
ChartArtifact(
    path="output/top_5_products_revenue.png",
    chart_type="bar",
    title="Top 5 Products by Revenue",
    description="Horizontal bar chart showing revenue ranking with category color coding"
)
```

### Stage 6 — Report Excerpt

> ## Executive Summary
>
> Electronics products dominate revenue, capturing 3 of the top 5 spots. The Ultra HD Monitor leads at $45,230.50, nearly double the 5th-ranked product. Total revenue across the top 5 is $170,599.25.
>
> ## Key Findings
>
> 1. **Ultra HD Monitor** leads with $45,230.50 in revenue (312 units)
> 2. **Wireless Headphones** rank second at $38,912.00 but lead in unit volume (487 units)
> 3. **Electronics** accounts for 66% of top-5 revenue ($113,032.70)
> 4. **Running Shoes Pro** is the only Sports product in top 5, suggesting a niche high-performer
>
> ## Recommendations
>
> - Increase inventory and marketing budget for Ultra HD Monitor and Wireless Headphones
> - Investigate why Sports has only one product in top 5 — potential growth opportunity
> - Consider bundling top Electronics products for cross-sell promotions

---

## Streamlit UI

The Streamlit dashboard provides a 4-tab interface for interactive analysis.

### Tab 1: Report
Full markdown rendering of the generated business report with an executive summary, methodology, findings, and recommendations. Includes a download button to save the report as `.md`.

### Tab 2: Charts
Gallery of generated charts (PNG images and Plotly HTML interactives) with captions describing what each visualization shows.

### Tab 3: SQL Query
The generated SQL query displayed in a syntax-highlighted code block, along with the row count, execution status, and any error messages from failed attempts.

### Tab 4: Raw Analysis
Expandable view of raw statistical output — the insights list, summary statistics JSON, correlations, and statistical test results from the Analyst stage.

**Sidebar:** Database connection status indicator and list of active observability providers.

### Dashboard Screenshots

![Report Tab](docs/images/report-tab.png)

![Charts Tab](docs/images/charts-tab.png)

![SQL Query Tab](docs/images/sql-query-tab.png)

![Raw Analysis Tab](docs/images/raw-analysis-tab.png)

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL running locally
- [Poetry](https://python-poetry.org/docs/#installation) installed

### Setup

```bash
# 1. Install dependencies
cd 10-ai-data-analyst
poetry install

# 2. Create and seed the database
psql -U postgres -c "CREATE DATABASE ecommerce;"
psql -U postgres -d ecommerce -f data/seed/ecommerce_seed.sql

# 3. Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key and database URL
```

### Run

```bash
# Unit tests (no DB or API keys needed)
poetry run pytest tests/unit/ -v

# CLI analysis
poetry run python examples/simple_analysis.py --question "Top 5 products by revenue?"

# Interactive multi-question session
poetry run python examples/interactive_session.py

# Streamlit dashboard
poetry run streamlit run src/streamlit_app/app.py

# Evaluations (requires API keys + Braintrust)
poetry run python evals/eval_sql_generation.py
poetry run python evals/eval_analysis.py
poetry run python evals/eval_report.py
```

---

## Configuration

### Settings Hierarchy

All settings are managed through Pydantic Settings with environment variable overrides.

```
┌─────────────────────────────────────────────┐
│                 .env file                    │
├──────────────┬──────────────────────────────┤
│  Database    │  LLM                         │
│  DB_*        │  OPENAI_*                    │
├──────────────┼──────────────────────────────┤
│  LangSmith   │  Langfuse                   │
│  LANGSMITH_* │  LANGFUSE_*                 │
│  LANGCHAIN_* │                             │
├──────────────┼──────────────────────────────┤
│  Helicone    │  Braintrust                 │
│  HELICONE_*  │  BRAINTRUST_*              │
└──────────────┴──────────────────────────────┘
```

### Environment Variables

```bash
# Core
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecommerce
DB_POOL_MIN=2
DB_POOL_MAX=10
DB_STATEMENT_TIMEOUT=30s
DB_MAX_ROWS=10000

# Observability (each independently toggled)
LANGSMITH_ENABLED=false
LANGFUSE_ENABLED=false
HELICONE_ENABLED=false
BRAINTRUST_ENABLED=false
```

### YAML Configs

Additional configuration is available in `conf/`:

```yaml
# conf/config.yaml — defaults
defaults:
  - database: dev
  - llm: openai

# conf/database/dev.yaml
url: postgresql://postgres:postgres@localhost:5432/ecommerce
pool_min: 2
pool_max: 10

# conf/llm/openai.yaml
model: gpt-4o
temperature: 0
max_tokens: 4096
```

---

## Project Structure

```
10-ai-data-analyst/
├── src/
│   ├── agents/                    # LangGraph node functions
│   │   ├── planner.py            # create_planner_node(llm) — analysis plan via structured output
│   │   ├── sql_agent.py          # create_sql_agent_node(llm, pool) + error handler with retry
│   │   ├── analyst.py            # analyst_node(state) — StatsToolkit, no LLM needed
│   │   ├── visualizer.py         # create_visualizer_node(llm, output_dir) — LLM chart recommendations
│   │   └── reporter.py           # create_reporter_node(llm) — markdown report generation
│   ├── graph/                     # LangGraph assembly
│   │   ├── builder.py            # build_graph() — 7 nodes, conditional routing
│   │   ├── routing.py            # route_after_sql() — error/empty/success branching
│   │   └── state.py              # AnalystState, AnalysisPlan, QueryResult, AnalysisResult, ChartArtifact
│   ├── tools/                     # Reusable tool modules
│   │   ├── db_query.py           # SQL safety validation + read-only execution
│   │   ├── schema_inspector.py   # Schema introspection tool (summary + sample values)
│   │   ├── stats_toolkit.py      # StatsToolkit — 6 statistical methods
│   │   └── chart_builder.py      # ChartBuilder — 6 chart types (seaborn, matplotlib, plotly)
│   ├── db/                        # Database layer
│   │   ├── connection.py         # DatabasePool — psycopg3 connection pool with read-only enforcement
│   │   └── introspect.py         # SchemaIntrospector — ColumnInfo, TableInfo dataclasses
│   ├── config/
│   │   └── settings.py           # Pydantic Settings — DatabaseSettings, LLMSettings, observability
│   ├── observability/             # 4-provider observability system
│   │   ├── __init__.py           # ObservabilityManager, configure_observability(), create_llm()
│   │   ├── providers.py          # setup_langsmith(), setup_langfuse(), setup_helicone(), setup_braintrust()
│   │   ├── callbacks.py          # CompositeCallbackManager — aggregates handlers
│   │   └── tracing.py            # @trace_node() decorator — timing + exception logging
│   └── streamlit_app/
│       └── app.py                # 4-tab Streamlit UI (Report, Charts, SQL, Raw Analysis)
├── conf/                          # YAML configuration
│   ├── config.yaml               # Defaults (database: dev, llm: openai)
│   ├── database/
│   │   ├── dev.yaml              # Development database settings
│   │   └── prod.yaml             # Production database settings
│   └── llm/
│       ├── openai.yaml           # GPT-4o configuration
│       └── azure_openai.yaml     # Azure OpenAI configuration
├── data/
│   └── seed/
│       └── ecommerce_seed.sql    # 5 tables, ~22,700 rows of e-commerce data
├── evals/                         # Braintrust evaluation framework
│   ├── datasets/
│   │   ├── sql_generation.json   # 16 SQL test cases (5 easy, 5 medium, 6 hard)
│   │   ├── analysis_quality.json # 11 analysis test cases
│   │   └── report_quality.json   # 10 report test cases
│   ├── scorers/
│   │   ├── sql_scorers.py        # SQLValidity, SQLCorrectness, SQLEfficiency
│   │   ├── analysis_scorers.py   # StatisticalAccuracy, InsightRelevance
│   │   └── report_scorers.py     # Completeness, Clarity
│   ├── eval_sql_generation.py    # SQL evaluation runner
│   ├── eval_analysis.py          # Analysis evaluation runner
│   └── eval_report.py            # Report evaluation runner
├── examples/
│   ├── simple_analysis.py        # CLI with --question flag
│   └── interactive_session.py    # Multi-question interactive session
├── tests/
│   ├── conftest.py               # Shared fixtures (sample_state, mock_llm, mock_db_pool)
│   ├── unit/                     # 58 unit tests across 9 modules
│   │   ├── test_state.py         # 12 tests — Pydantic model validation
│   │   ├── test_observability.py # 15 tests — provider setup, callbacks, tracing
│   │   ├── test_db_query.py      # 8 tests — SQL safety, blocklist, execution
│   │   ├── test_routing.py       # 5 tests — conditional routing logic
│   │   ├── test_sql_agent.py     # 5 tests — SQL generation and error handling
│   │   ├── test_analyst.py       # 4 tests — StatsToolkit analysis
│   │   ├── test_planner.py       # 3 tests — structured output planning
│   │   ├── test_reporter.py      # 3 tests — markdown report generation
│   │   └── test_visualizer.py    # 3 tests — chart recommendation and rendering
│   └── integration/
│       └── test_graph_e2e.py     # 2 end-to-end pipeline tests
├── .env.example                   # Environment variable template
├── pyproject.toml                 # Poetry dependencies and project config
└── README.md                      # This file
```

---

## Testing

Tests cover pipeline stages, state validation, routing logic, observability, local evals, and MCP helpers.

| Module | Tests | What It Covers |
|--------|-------|---------------|
| `test_observability.py` | 15 | Provider setup, callback aggregation, tracing decorator |
| `test_state.py` | 12 | Pydantic model validation, defaults, reducers |
| `test_db_query.py` | 8 | SQL safety blocklist, whitelist, read-only execution |
| `test_routing.py` | 5 | Conditional routing: error → retry, empty → reporter, success → analyst |
| `test_sql_agent.py` | 5 | SQL generation, markdown stripping, error handler retry |
| `test_analyst.py` | 4 | StatsToolkit methods, full_analysis output |
| `test_planner.py` | 3 | Structured output parsing, analysis plan validation |
| `test_reporter.py` | 3 | Report structure, partial report handling |
| `test_visualizer.py` | 3 | Chart recommendation, column validation, rendering |
| `test_local_evals.py` | 4 | Offline SQL eval loading, scoring, and summaries |
| `test_mcp_server.py` | 5 | MCP helper functions, SQL scoring, file allow-listing |
| `test_graph_e2e.py` | 2 | Full pipeline integration (success path + error path) |

```bash
# Run all unit tests
poetry run pytest tests/unit/ -v

# With coverage
poetry run pytest tests/unit/ --cov=src

# Specific module
poetry run pytest tests/unit/test_routing.py -v

# Integration tests (requires DB + API keys)
poetry run pytest tests/integration/ -v
```

---

## Local Evals and MCP

Run offline SQL scorer checks without API keys or a live database:

```bash
poetry run ai-data-analyst-evals
```

Produce a compact markdown report:

```bash
poetry run ai-data-analyst-evals --format markdown
```

Run a small streamed Hugging Face BIRD-style text-to-SQL benchmark sample:

```bash
poetry run ai-data-analyst-evals --source huggingface --hf-preset bird --limit 25 --format markdown
```

Export a normalized Hugging Face sample into this project's eval JSON shape:

```bash
poetry run ai-data-analyst-evals \
  --source huggingface \
  --hf-preset bird \
  --limit 50 \
  --export-dataset evals/datasets/bird_lite_sample.json
```

Score model-generated SQL by passing a JSON predictions file keyed by question:

```bash
poetry run ai-data-analyst-evals --predictions predictions.json --output output/eval_results.json
```

Start the project MCP server for compatible AI hosts:

```bash
poetry run ai-data-analyst-mcp
```

See `docs/MCP.md` for the exposed MCP tools and resources.

---

## Portfolio Demo

Generate a complete offline business-analysis showcase without OpenAI keys or a
live database:

```bash
poetry run ai-data-analyst-demo
```

The demo creates deterministic ecommerce data, answers five realistic business
questions, writes result CSVs, generates charts, and exports:

```text
output/portfolio_demo/portfolio_demo_report.md
output/portfolio_demo/portfolio_demo_report.html
```

This is the fastest path for reviewers to see the project’s end-to-end analytics
workflow: business question → SQL plan → computed analysis → chart → recommendation.

---

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Orchestration | LangGraph | ^0.4.0 |
| LLM Framework | LangChain | ^0.3.0 |
| LLM | OpenAI GPT-4o | langchain-openai ^0.3.0 |
| Database | PostgreSQL (psycopg3) | psycopg ^3.2.0 |
| Data Analysis | pandas | ^2.2.0 |
| Statistics | scipy | ^1.12.0 |
| Numerical | numpy | ^1.26.0 |
| Static Charts | matplotlib + seaborn | ^3.8.0 / ^0.13.0 |
| Interactive Charts | plotly | ^5.19.0 |
| Config | Pydantic Settings | ^2.2.0 |
| UI | Streamlit | ^1.32.0 |
| Logging | loguru | ^0.7.2 |
| Tracing | LangSmith | ^0.3.0 |
| Tracing | Langfuse | ^2.0.0 |
| Cost Tracking | Helicone | Proxy (no SDK) |
| Evaluation | Braintrust + autoevals | >=0.0.100 / >=0.0.60 |
| MCP | Official MCP Python SDK | >=2.0,<3.0 |
| Code Formatting | black | ^24.1.0 |
| Linting | ruff | ^0.1.14 |
| Type Checking | mypy | ^1.8.0 |
| Testing | pytest | ^8.0.0 |

---

## Author

**Zubair Ashfaque** — [@zubairashfaque](https://github.com/zubairashfaque)

Portfolio: [zubairashfaque.github.io](https://zubairashfaque.github.io/)
