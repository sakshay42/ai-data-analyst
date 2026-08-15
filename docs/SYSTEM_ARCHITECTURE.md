# AI Data Analyst — System Architecture

> Comprehensive documentation of every component, agent, tool, state model,
> and data flow in the AI Data Analyst pipeline.

---

## Table of Contents

1. [System Overview & Entry Points](#1-system-overview--entry-points)
2. [Settings & Environment Variables](#2-settings--environment-variables)
3. [Database Layer](#3-database-layer)
4. [State Models](#4-state-models)
5. [Graph Builder (build_graph)](#5-graph-builder-build_graph)
6. [Agent Nodes (Detailed)](#6-agent-nodes-detailed)
7. [Routing Logic](#7-routing-logic)
8. [Tools & Utilities](#8-tools--utilities)
9. [Observability System](#9-observability-system)
10. [Callback Lifecycle Flow](#10-callback-lifecycle-flow)
11. [Complete File Map](#11-complete-file-map)
12. [Dependency & Prerequisites Chain](#12-dependency--prerequisites-chain)

---

## 1. System Overview & Entry Points

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI DATA ANALYST SYSTEM                          │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      ENTRY POINTS                                │  │
│  │                                                                  │  │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │  │
│  │  │ simple_      │  │ interactive_     │  │ streamlit_app/   │  │  │
│  │  │ analysis.py  │  │ session.py       │  │ app.py           │  │  │
│  │  │ (CLI)        │  │ (REPL)           │  │ (Web UI)         │  │  │
│  │  └──────┬───────┘  └────────┬─────────┘  └────────┬─────────┘  │  │
│  └─────────┼───────────────────┼──────────────────────┼────────────┘  │
│            │                   │                      │               │
│            ▼                   ▼                      ▼               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   INITIALIZATION PIPELINE                        │  │
│  │                                                                  │  │
│  │  Settings ──► DatabasePool ──► configure_observability           │  │
│  │                                        │                         │  │
│  │                                        ▼                         │  │
│  │                                  build_graph()                   │  │
│  │                                        │                         │  │
│  │                                        ▼                         │  │
│  │                              Compiled StateGraph                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│            │                   │                      │               │
│            ▼                   ▼                      ▼               │
│     graph.invoke()      graph.invoke()        graph.stream()         │
│     (single run)        (per question)        (real-time UI)         │
│            │                   │                      │               │
│            ▼                   ▼                      ▼               │
│     flush_callbacks()   flush_callbacks()     flush_callbacks()       │
│     (after run)         (after each Q)        (after each run)       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Entry Point Details

| Entry Point | File | Lines | Invocation | Output |
|---|---|---|---|---|
| **CLI** | `examples/simple_analysis.py` | 76 | `graph.invoke(state, config)` | Prints report + chart paths |
| **REPL** | `examples/interactive_session.py` | 62 | `graph.invoke(state, config)` per question | Prints report per question |
| **Web UI** | `src/streamlit_app/app.py` | 672 | `graph.stream(state, config, stream_mode="updates")` | Live progress + tabbed results |

### Initialization Sequence (All Entry Points)

```
1. settings = get_settings()              # Load from .env via Pydantic
       │
2.     ├──► pool = get_pool(settings.database)
       │         └──► pool.open()          # Create psycopg3 ConnectionPool
       │
3.     ├──► obs_manager = configure_observability(settings)
       │         ├──► setup_langsmith()     # If enabled: set env vars
       │         ├──► setup_langfuse()      # If enabled: create callback
       │         ├──► setup_helicone()      # If enabled: proxy config
       │         └──► setup_braintrust()    # If enabled: proxy config
       │
4.     └──► graph = build_graph(settings, pool, obs_manager)
                  ├──► Create 4 LLMs (planner, sql, viz, reporter)
                  ├──► Create 7 node functions
                  ├──► Wire edges (linear + conditional)
                  └──► Compile StateGraph
```

---

## 2. Settings & Environment Variables

### Complete Settings Tree

```
Settings                              (src/config/settings.py:63-79)
│
├── app_name: str = "ai-data-analyst"
├── log_level: str = "INFO"
├── output_dir: str = "output"
│
├── database: DatabaseSettings        (lines 11-18, env_prefix="DB_")
│   ├── url: str                      ── DB_URL ──────────────► "postgresql://postgres:postgres@localhost:5432/ecommerce"
│   ├── pool_min: int                 ── DB_POOL_MIN ─────────► 2
│   ├── pool_max: int                 ── DB_POOL_MAX ─────────► 10
│   ├── statement_timeout: str        ── DB_STATEMENT_TIMEOUT ► "30s"
│   └── max_rows: int                 ── DB_MAX_ROWS ─────────► 10,000
│
├── llm: LLMSettings                  (lines 21-28, env_prefix="OPENAI_")
│   ├── api_key: str                  ── OPENAI_API_KEY ──────► (required, no default)
│   ├── model: str                    ── OPENAI_MODEL ────────► "gpt-4o"
│   ├── temperature: float            ── OPENAI_TEMPERATURE ──► 0.0
│   ├── max_tokens: int               ── OPENAI_MAX_TOKENS ──► 4096
│   └── request_timeout: int          ── OPENAI_REQUEST_TIMEOUT► 60
│
├── langsmith: LangSmithSettings      (lines 31-37, env_prefix="LANGSMITH_")
│   ├── enabled: bool                 ── LANGSMITH_ENABLED ───► False
│   ├── api_key: str                  ── LANGSMITH_API_KEY ───► (optional)
│   ├── project: str                  ── LANGSMITH_PROJECT ───► "ai-data-analyst"
│   └── tracing_v2: bool             ── LANGSMITH_TRACING_V2 ► True
│
├── langfuse: LangfuseSettings        (lines 40-46, env_prefix="LANGFUSE_")
│   ├── enabled: bool                 ── LANGFUSE_ENABLED ────► False
│   ├── public_key: str               ── LANGFUSE_PUBLIC_KEY ─► (optional)
│   ├── secret_key: str               ── LANGFUSE_SECRET_KEY ─► (optional)
│   └── host: str                     ── LANGFUSE_HOST ───────► "https://cloud.langfuse.com"
│
├── helicone: HeliconeSettings        (lines 49-53, env_prefix="HELICONE_")
│   ├── enabled: bool                 ── HELICONE_ENABLED ────► False
│   └── api_key: str                  ── HELICONE_API_KEY ────► (optional)
│
└── braintrust: BraintrustSettings    (lines 56-60, env_prefix="BRAINTRUST_")
    ├── enabled: bool                 ── BRAINTRUST_ENABLED ──► False
    └── api_key: str                  ── BRAINTRUST_API_KEY ──► (optional)
```

### .env File Mapping

```
# ─── Required ────────────────────────────────────────────────────
OPENAI_API_KEY=sk-proj-...             # LLMSettings.api_key

# ─── Database (all have defaults) ────────────────────────────────
DB_URL=postgresql://user:pass@host:5432/db
DB_POOL_MIN=2
DB_POOL_MAX=10
DB_STATEMENT_TIMEOUT=30s
DB_MAX_ROWS=10000

# ─── LLM Tuning (all have defaults) ─────────────────────────────
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.0
OPENAI_MAX_TOKENS=4096
OPENAI_REQUEST_TIMEOUT=60

# ─── Observability (all optional, disabled by default) ──────────
LANGSMITH_ENABLED=true
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=ai-data-analyst

LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

HELICONE_ENABLED=true
HELICONE_API_KEY=sk-helicone-...

BRAINTRUST_ENABLED=true
BRAINTRUST_API_KEY=sk-braintrust-...
```

---

## 3. Database Layer

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       DATABASE LAYER                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  DatabasePool            (src/db/connection.py:14-84)    │  │
│  │                                                          │  │
│  │  __init__(settings: DatabaseSettings)                    │  │
│  │      └── Stores settings, pool=None                      │  │
│  │                                                          │  │
│  │  open() → None                                           │  │
│  │      └── Creates psycopg3 ConnectionPool                 │  │
│  │          ├── conninfo = settings.url                      │  │
│  │          ├── min_size = settings.pool_min (default: 2)    │  │
│  │          ├── max_size = settings.pool_max (default: 10)   │  │
│  │          └── kwargs = {"autocommit": True}                │  │
│  │                                                          │  │
│  │  close() → None                                          │  │
│  │      └── pool.close() if pool exists                      │  │
│  │                                                          │  │
│  │  connection() → ContextManager[Connection]               │  │
│  │      └── Yields connection with:                          │  │
│  │          ├── SET statement_timeout = '{timeout}'           │  │
│  │          └── SET default_transaction_read_only = ON       │  │
│  │                                                          │  │
│  │  execute_query(sql, params?, max_rows?) → (rows, cols)   │  │
│  │      ├── Uses self.connection() context                   │  │
│  │      ├── cursor.execute(sql, params)                      │  │
│  │      ├── Fetches up to max_rows (default: settings)       │  │
│  │      └── Returns (list[dict], list[str])                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Singleton: get_pool(settings) → DatabasePool  (lines 77-83)  │
│      └── Module-level _pool caching                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SchemaIntrospector      (src/db/introspect.py:28-128)   │  │
│  │                                                          │  │
│  │  __init__(pool: DatabasePool)                            │  │
│  │                                                          │  │
│  │  get_tables(schema="public") → list[TableInfo]           │  │
│  │      ├── Query: information_schema.tables                 │  │
│  │      ├── Query: information_schema.columns                │  │
│  │      ├── Query: pg_index + pg_class (primary keys)        │  │
│  │      ├── Query: pg_class + pg_namespace (row estimates)   │  │
│  │      └── Returns list of TableInfo with ColumnInfo        │  │
│  │                                                          │  │
│  │  get_schema_summary(schema="public") → str               │  │
│  │      └── Formatted text for LLM context window            │  │
│  │                                                          │  │
│  │  get_sample_values(table, column, limit=10) → list[Any]  │  │
│  │      └── SELECT DISTINCT ... LIMIT {limit}                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Classes                                            │  │
│  │                                                          │  │
│  │  ColumnInfo  (introspect.py:11-17)                       │  │
│  │    ├── name: str                                          │  │
│  │    ├── data_type: str                                     │  │
│  │    ├── is_nullable: bool                                  │  │
│  │    ├── column_default: str | None = None                  │  │
│  │    └── is_primary_key: bool = False                       │  │
│  │                                                          │  │
│  │  TableInfo   (introspect.py:20-25)                       │  │
│  │    ├── schema: str                                        │  │
│  │    ├── name: str                                          │  │
│  │    ├── columns: list[ColumnInfo] = []                     │  │
│  │    └── row_count_estimate: int = 0                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Read-Only Enforcement

```
Every connection acquired via pool.connection():

    ┌──────────────────────────────────────────────┐
    │  SET statement_timeout = '30s'               │  ◄── Prevents long queries
    │  SET default_transaction_read_only = ON      │  ◄── Prevents writes
    └──────────────────────────────────────────────┘

    Result: All queries are SELECT-only at the database level.
    Even if SQL injection bypasses application-level validation,
    PostgreSQL will reject INSERT/UPDATE/DELETE/DROP.
```

---

## 4. State Models

### Complete State Model Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         STATE MODELS                                 │
│                     (src/graph/state.py)                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  AnalystState  (TypedDict, lines 50-74)                     │    │
│  │  ═══════════════════════════════════════                     │    │
│  │                                                             │    │
│  │  INPUT FIELDS:                                              │    │
│  │  ├── question: str                  # User's question       │    │
│  │  └── schema_summary: str            # DB schema text        │    │
│  │                                                             │    │
│  │  PIPELINE OUTPUTS:                                          │    │
│  │  ├── plan: AnalysisPlan ────────────────────────────┐       │    │
│  │  ├── query_result: QueryResult ─────────────────┐   │       │    │
│  │  ├── sql_retry_count: int       # 0, 1, or 2   │   │       │    │
│  │  ├── analysis: AnalysisResult ──────────────┐   │   │       │    │
│  │  ├── charts: list[ChartArtifact] ───────┐   │   │   │       │    │
│  │  └── report: str                        │   │   │   │       │    │
│  │                                         │   │   │   │       │    │
│  │  ERROR TRACKING:                        │   │   │   │       │    │
│  │  └── errors: Annotated[list[str],       │   │   │   │       │    │
│  │              operator.add]  # Append-only│   │   │   │       │    │
│  └─────────────────────────────────────────┼───┼───┼───┼───────┘    │
│                                            │   │   │   │            │
│  ┌─────────────────────────────────────┐   │   │   │   │            │
│  │  ChartArtifact (lines 41-47)       │◄──┘   │   │   │            │
│  │  ───────────────────────────────   │       │   │   │            │
│  │  path: str          # File path    │       │   │   │            │
│  │  chart_type: str    # bar/line/... │       │   │   │            │
│  │  title: str                        │       │   │   │            │
│  │  description: str                  │       │   │   │            │
│  └─────────────────────────────────────┘       │   │   │            │
│                                                │   │   │            │
│  ┌─────────────────────────────────────┐       │   │   │            │
│  │  AnalysisResult (lines 31-38)      │◄──────┘   │   │            │
│  │  ───────────────────────────────   │           │   │            │
│  │  summary_stats: dict[str, Any]     │           │   │            │
│  │  correlations: dict[str, float]    │           │   │            │
│  │  tests: list[dict[str, Any]]       │           │   │            │
│  │  trends: dict[str, Any]            │           │   │            │
│  │  insights: list[str]               │           │   │            │
│  └─────────────────────────────────────┘           │   │            │
│                                                    │   │            │
│  ┌─────────────────────────────────────┐           │   │            │
│  │  QueryResult (lines 21-28)         │◄──────────┘   │            │
│  │  ───────────────────────────────   │               │            │
│  │  sql: str           # Executed SQL │               │            │
│  │  columns: list[str] # Col names    │               │            │
│  │  rows: list[dict]   # Result data  │               │            │
│  │  row_count: int                    │               │            │
│  │  error: str         # "" if OK     │               │            │
│  └─────────────────────────────────────┘               │            │
│                                                        │            │
│  ┌─────────────────────────────────────┐               │            │
│  │  AnalysisPlan (lines 11-18)        │◄──────────────┘            │
│  │  ───────────────────────────────   │                            │
│  │  question: str                     │                            │
│  │  sub_questions: list[str]          │                            │
│  │  required_tables: list[str]        │                            │
│  │  analysis_type: str                │                            │
│  │  suggested_visualizations: list[str]│                            │
│  └─────────────────────────────────────┘                            │
│                                                                      │
│  ── LLM Structured Output Models (visualizer.py) ──                 │
│                                                                      │
│  ┌─────────────────────────────────────┐                            │
│  │  ChartSpec (lines 29-33)           │                            │
│  │  ───────────────────────────────   │                            │
│  │  chart_type: str  # bar/line/etc.  │                            │
│  │  x_column: str                     │                            │
│  │  y_column: str                     │    ┌─────────────────┐     │
│  │  title: str                        │◄───│ ChartSpecs      │     │
│  └─────────────────────────────────────┘    │ (lines 36-37)  │     │
│                                             │                 │     │
│                                             │ charts:         │     │
│                                             │  list[ChartSpec]│     │
│                                             └─────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

### State Field Lifecycle

```
Field               Written By            Read By
──────────────────  ────────────────────  ──────────────────────────
question            Entry point (input)   planner, sql_agent, visualizer, reporter
schema_summary      introspect_schema     planner, sql_agent, sql_error_handler
plan                planner               sql_agent, sql_error_handler, visualizer, reporter
query_result        sql_agent /           analyst, visualizer, reporter
                    sql_error_handler
sql_retry_count     sql_error_handler     route_after_sql
analysis            analyst               visualizer, reporter
charts              visualizer            reporter
report              reporter              Entry point (output)
errors              sql_agent /           reporter
                    sql_error_handler
```

---

## 5. Graph Builder (build_graph)

### File: `src/graph/builder.py` (118 lines)

### Signature

```python
def build_graph(
    settings: Settings,
    pool: DatabasePool,
    obs_manager: ObservabilityManager
) -> CompiledStateGraph
```

### LLM Creation (4 Instances)

```
build_graph()
    │
    ├── planner_llm  = create_llm(settings, obs_manager, "planner")
    ├── sql_llm      = create_llm(settings, obs_manager, "sql_agent")
    ├── viz_llm      = create_llm(settings, obs_manager, "visualizer")
    └── reporter_llm = create_llm(settings, obs_manager, "reporter")

    Each create_llm() call:
    ├── Base: model, temperature, max_tokens, api_key, timeout
    ├── + Proxy kwargs (Helicone base_url + headers, OR Braintrust)
    └── + Helicone session headers {"Helicone-Session-Name": node_name}
```

### Node Factory Functions

```
Node Function                          Factory / Source
─────────────────────────────────────  ─────────────────────────────────────
introspect_schema_node                 _create_introspect_node(pool)
planner_node                           create_planner_node(planner_llm)
sql_agent_node                         create_sql_agent_node(sql_llm, pool)
sql_error_handler_node                 create_sql_error_handler_node(sql_llm, pool)
analyst_node                           Direct function (no factory)
visualizer_node                        create_visualizer_node(viz_llm, output_dir)
reporter_node                          create_reporter_node(reporter_llm)
```

### trace_node Decorator

Every node is wrapped with `@trace_node("node_name")`:

```python
@trace_node("planner")
def planner_node(state, config):
    ...

# trace_node logs:
#   [planner] Starting
#   [planner] Completed in 2.34s
#   [planner] Error after 0.12s: ...
```

### Edge Topology

```
                    ┌───────────────────────────────────────────────────┐
                    │              COMPILED STATE GRAPH                 │
                    │                                                   │
                    │   START                                           │
                    │     │                                             │
                    │     ▼                                             │
                    │  ┌──────────────────┐                            │
                    │  │ introspect_schema│  (no LLM)                  │
                    │  └────────┬─────────┘                            │
                    │           │                                       │
                    │           ▼                                       │
                    │  ┌──────────────────┐                            │
                    │  │     planner      │  (LLM: structured output)  │
                    │  └────────┬─────────┘                            │
                    │           │                                       │
                    │           ▼                                       │
                    │  ┌──────────────────┐                            │
                    │  │    sql_agent     │  (LLM + DB execute)        │
                    │  └────────┬─────────┘                            │
                    │           │                                       │
                    │           ▼                                       │
                    │     route_after_sql()   ◄── CONDITIONAL EDGE     │
                    │      ┌────┼────────┐                             │
                    │      │    │        │                              │
                    │  error&  error&   row_count   success            │
                    │  retry   retry    == 0                            │
                    │  < 2     >= 2       │          │                  │
                    │      │    │        │          │                  │
                    │      ▼    │        │          ▼                  │
                    │  ┌────────────┐    │   ┌──────────────┐         │
                    │  │sql_error_  │    │   │   analyst    │ (no LLM)│
                    │  │handler     │    │   └──────┬───────┘         │
                    │  └─────┬──────┘    │          │                  │
                    │        │           │          ▼                  │
                    │        │ (loops    │   ┌──────────────┐         │
                    │        │  back to  │   │  visualizer  │ (LLM)   │
                    │        │ sql_agent)│   └──────┬───────┘         │
                    │        ▼           │          │                  │
                    │   sql_agent ───────┤          │                  │
                    │   (re-enters       │          ▼                  │
                    │    routing)         │   ┌──────────────┐         │
                    │                    └──►│   reporter   │ (LLM)   │
                    │                        └──────┬───────┘         │
                    │                               │                  │
                    │                               ▼                  │
                    │                              END                 │
                    └───────────────────────────────────────────────────┘
```

### Edge Definitions (from build_graph)

```python
# Linear edges
graph.add_edge(START, "introspect_schema")
graph.add_edge("introspect_schema", "planner")
graph.add_edge("planner", "sql_agent")

# Conditional edge after sql_agent
graph.add_conditional_edges("sql_agent", route_after_sql, {
    "sql_error_handler": "sql_error_handler",
    "analyst": "analyst",
    "reporter": "reporter",
})

# Error handler loops back to sql_agent
graph.add_edge("sql_error_handler", "sql_agent")

# Success path continues linearly
graph.add_edge("analyst", "visualizer")
graph.add_edge("visualizer", "reporter")
graph.add_edge("reporter", END)
```

---

## 6. Agent Nodes (Detailed)

### Node 1: introspect_schema

| Attribute | Value |
|---|---|
| **File** | `src/graph/builder.py:24-35` (inline closure) |
| **Factory** | `_create_introspect_node(pool: DatabasePool)` |
| **Signature** | `introspect_schema_node(state: AnalystState) -> dict[str, Any]` |
| **State READS** | Nothing (only needs pool) |
| **State WRITES** | `{"schema_summary": str}` |
| **LLM** | None |
| **Config** | Not accepted |
| **Tools** | `SchemaIntrospector(pool).get_schema_summary()` |
| **System Prompt** | None |
| **Prerequisites** | Database must be accessible |
| **Error Handling** | None (exception propagates) |

```
introspect_schema_node(state)
    │
    ├── introspector = SchemaIntrospector(pool)
    ├── summary = introspector.get_schema_summary()
    │       ├── Queries information_schema.tables
    │       ├── Queries information_schema.columns
    │       ├── Queries pg_index + pg_class (PKs)
    │       └── Formats as human-readable text
    │
    └── return {"schema_summary": summary}
```

---

### Node 2: planner

| Attribute | Value |
|---|---|
| **File** | `src/agents/planner.py:25-41` |
| **Factory** | `create_planner_node(llm: ChatOpenAI)` |
| **Signature** | `planner_node(state: AnalystState, config: RunnableConfig \| None = None) -> dict[str, Any]` |
| **State READS** | `state.schema_summary`, `state.question` |
| **State WRITES** | `{"plan": AnalysisPlan}` |
| **LLM** | `llm.with_structured_output(AnalysisPlan).invoke(messages, config=config)` |
| **Config** | YES — accepts and passes to LLM |
| **Tools** | None (pure LLM) |
| **Prerequisites** | `schema_summary` must be populated |
| **Error Handling** | None (exception propagates) |

**System Prompt** (`PLANNER_SYSTEM_PROMPT`, lines 13-22):
```
You are a data analysis planner. Given a user's business question and a
database schema, create a structured analysis plan.

Your plan should include:
1. The original question restated clearly
2. Sub-questions that need to be answered via SQL
3. Which tables are required
4. The type of analysis (trend, comparison, distribution, ranking, aggregation)
5. Suggested visualizations (bar, line, pie, scatter, histogram)

Be specific about what SQL queries are needed and what analysis to perform.
```

```
planner_node(state, config)
    │
    ├── messages = [
    │       SystemMessage(PLANNER_SYSTEM_PROMPT),
    │       HumanMessage(f"Schema:\n{state.schema_summary}\n\nQuestion: {state.question}")
    │   ]
    │
    ├── plan = llm.with_structured_output(AnalysisPlan).invoke(messages, config=config)
    │
    └── return {"plan": plan}
```

---

### Node 3: sql_agent

| Attribute | Value |
|---|---|
| **File** | `src/agents/sql_agent.py:26-64` |
| **Factory** | `create_sql_agent_node(llm: ChatOpenAI, pool: DatabasePool)` |
| **Signature** | `sql_agent_node(state: AnalystState, config: RunnableConfig \| None = None) -> dict[str, Any]` |
| **State READS** | `state.plan` (question, sub_questions, required_tables, analysis_type), `state.schema_summary` |
| **State WRITES** | `{"query_result": QueryResult}` on success; `{"query_result": QueryResult(error=...), "errors": [...]}` on failure |
| **LLM** | `llm.invoke(messages, config=config)` → raw text (SQL) |
| **Config** | YES — accepts and passes to LLM |
| **Tools** | `pool.execute_query(sql)` |
| **Prerequisites** | `plan` and `schema_summary` must be populated |
| **Error Handling** | Catches `Exception` from `pool.execute_query()`, returns error in QueryResult + appends to errors |

**System Prompt** (`SQL_AGENT_SYSTEM_PROMPT`, lines 15-23):
```
You are a SQL expert. Given a database schema and an analysis plan,
generate a single SQL query that answers the user's question.

Rules:
- Only generate SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
- Use standard PostgreSQL syntax
- Include appropriate JOINs, GROUP BY, ORDER BY as needed
- Use aliases for readability
- Limit results to a reasonable number unless aggregating
- Output ONLY the SQL query, no explanation or markdown formatting
```

```
sql_agent_node(state, config)
    │
    ├── messages = [
    │       SystemMessage(SQL_AGENT_SYSTEM_PROMPT),
    │       HumanMessage(schema + plan details)
    │   ]
    │
    ├── response = llm.invoke(messages, config=config)
    ├── sql = response.content.strip()
    ├── sql = strip markdown fences ("```sql", "```")
    │
    ├── try:
    │   ├── rows, columns = pool.execute_query(sql)
    │   └── return {"query_result": QueryResult(sql, columns, rows, len(rows), "")}
    │
    └── except Exception as e:
        └── return {"query_result": QueryResult(sql=sql, error=str(e)),
                     "errors": [f"SQL execution error: {e}"]}
```

---

### Node 3b: sql_error_handler

| Attribute | Value |
|---|---|
| **File** | `src/agents/sql_agent.py:67-106` |
| **Factory** | `create_sql_error_handler_node(llm: ChatOpenAI, pool: DatabasePool)` |
| **Signature** | `sql_error_handler_node(state: AnalystState, config: RunnableConfig \| None = None) -> dict[str, Any]` |
| **State READS** | `state.schema_summary`, `state.plan.question`, `state.query_result.sql`, `state.query_result.error`, `state.sql_retry_count` |
| **State WRITES** | `{"query_result": QueryResult, "sql_retry_count": int}` (+ `"errors"` on failure) |
| **LLM** | `llm.invoke(messages, config=config)` → raw text (corrected SQL) |
| **Config** | YES — accepts and passes to LLM |
| **Tools** | `pool.execute_query(sql)` |
| **Prerequisites** | `query_result.error` must be non-empty, `sql_retry_count < 2` |
| **Error Handling** | Same as sql_agent — catches Exception, returns error + appends to errors |

**Prompt** (same `SQL_AGENT_SYSTEM_PROMPT` + error context):
```
Previous SQL that failed:
{state.query_result.sql}

Error:
{state.query_result.error}

Please fix the SQL query and try again.
```

```
sql_error_handler_node(state, config)
    │
    ├── retry_count = state.get("sql_retry_count", 0) + 1
    │
    ├── messages = [
    │       SystemMessage(SQL_AGENT_SYSTEM_PROMPT),
    │       HumanMessage(schema + question + failed SQL + error message)
    │   ]
    │
    ├── response = llm.invoke(messages, config=config)
    ├── sql = strip markdown fences from response
    │
    ├── try:
    │   ├── rows, columns = pool.execute_query(sql)
    │   └── return {"query_result": QueryResult(...), "sql_retry_count": retry_count}
    │
    └── except Exception as e:
        └── return {"query_result": QueryResult(error=str(e)),
                     "sql_retry_count": retry_count,
                     "errors": [f"SQL retry error: {e}"]}
```

---

### Node 4: analyst

| Attribute | Value |
|---|---|
| **File** | `src/agents/analyst.py:13-55` |
| **Factory** | None — direct function (not a factory) |
| **Signature** | `analyst_node(state: AnalystState) -> dict[str, Any]` |
| **State READS** | `state.query_result` (rows, columns, error) |
| **State WRITES** | `{"analysis": AnalysisResult}` |
| **LLM** | None (pure computation) |
| **Config** | NOT accepted |
| **Tools** | `StatsToolkit(data=qr.rows, columns=qr.columns).full_analysis()` |
| **System Prompt** | None |
| **Prerequisites** | `query_result` with rows/columns (returns empty insights if error/empty) |
| **Error Handling** | Returns "No data available" insight if error or empty rows |

```
analyst_node(state)
    │
    ├── qr = state["query_result"]
    │
    ├── if qr.error or not qr.rows:
    │   └── return {"analysis": AnalysisResult(insights=["No data available"])}
    │
    ├── toolkit = StatsToolkit(data=qr.rows, columns=qr.columns)
    ├── stats = toolkit.full_analysis()
    │       ├── descriptive_stats() → summary dict
    │       └── correlation_matrix() → correlations dict
    │
    ├── Generate insights:
    │   ├── For each numeric column: "Column X: mean=..., std=..., range=[..., ...]"
    │   └── For each strong correlation (|r| > 0.7): "Strong correlation..."
    │
    └── return {"analysis": AnalysisResult(
            summary_stats=stats.summary,
            correlations=stats.correlations,
            tests=stats.tests,
            trends=stats.trends,
            insights=[...]
        )}
```

---

### Node 5: visualizer

| Attribute | Value |
|---|---|
| **File** | `src/agents/visualizer.py:40-116` |
| **Factory** | `create_visualizer_node(llm: ChatOpenAI, output_dir: str = "output")` |
| **Signature** | `visualizer_node(state: AnalystState, config: RunnableConfig \| None = None) -> dict[str, Any]` |
| **State READS** | `state.question`, `state.query_result` (rows, columns, row_count, error), `state.analysis.insights`, `state.plan.suggested_visualizations` |
| **State WRITES** | `{"charts": list[ChartArtifact]}` |
| **LLM** | `llm.with_structured_output(ChartSpecs).invoke(messages, config=config)` |
| **Config** | YES — accepts and passes to LLM |
| **Tools** | `ChartBuilder(output_dir)` — `bar_chart()`, `line_chart()`, `pie_chart()`, `scatter_plot()`, `histogram()` |
| **Prerequisites** | `query_result` with rows (returns empty if error/no data) |
| **Error Handling** | Validates columns exist in DataFrame; catches per-chart exceptions, logs and skips |

**System Prompt** (`VIZ_SYSTEM_PROMPT`, lines 18-26):
```
You are a data visualization expert. Given analysis results and a data
schema, recommend the best chart(s) to visualize the findings.

For each chart, specify:
- chart_type: one of "bar", "line", "pie", "scatter", "histogram"
- x_column: column name for x-axis
- y_column: column name for y-axis
- title: descriptive chart title

Return a list of 1-3 chart specifications. Choose charts that best
communicate the key findings.
```

**Structured Output Models:**
```python
class ChartSpec(BaseModel):           # visualizer.py:29-33
    chart_type: str                   # "bar" | "line" | "pie" | "scatter" | "histogram"
    x_column: str
    y_column: str
    title: str

class ChartSpecs(BaseModel):          # visualizer.py:36-37
    charts: list[ChartSpec]
```

```
visualizer_node(state, config)
    │
    ├── qr = state["query_result"]
    ├── if qr.error or not qr.rows:
    │   └── return {"charts": []}
    │
    ├── df = pd.DataFrame(qr.rows, columns=qr.columns)
    │
    ├── messages = [
    │       SystemMessage(VIZ_SYSTEM_PROMPT),
    │       HumanMessage(question + columns + row_count + insights + suggestions)
    │   ]
    │
    ├── chart_specs = llm.with_structured_output(ChartSpecs).invoke(messages, config)
    │
    ├── builder = ChartBuilder(output_dir)
    ├── charts = []
    │
    ├── for spec in chart_specs.charts:
    │   ├── Validate columns exist in df
    │   ├── method = getattr(builder, f"{spec.chart_type}_chart", None)
    │   │            or scatter_plot / histogram handler
    │   ├── try:
    │   │   ├── artifact = method(df, spec.x_column, spec.y_column, ...)
    │   │   └── charts.append(artifact)
    │   └── except: log warning, skip chart
    │
    └── return {"charts": charts}
```

---

### Node 6: reporter

| Attribute | Value |
|---|---|
| **File** | `src/agents/reporter.py:27-64` |
| **Factory** | `create_reporter_node(llm: ChatOpenAI)` |
| **Signature** | `reporter_node(state: AnalystState, config: RunnableConfig \| None = None) -> dict[str, Any]` |
| **State READS** | ALL — `question`, `query_result` (sql, row_count), `analysis` (insights, summary_stats, correlations), `charts` (title, chart_type, description, path), `errors` |
| **State WRITES** | `{"report": str}` (markdown report) |
| **LLM** | `llm.invoke(messages, config=config)` → raw text (markdown) |
| **Config** | YES — accepts and passes to LLM |
| **Tools** | None (pure LLM) |
| **Prerequisites** | Works with any state (handles partial/error gracefully) |
| **Error Handling** | None (exception propagates) |

**System Prompt** (`REPORTER_SYSTEM_PROMPT`, lines 14-24):
```
You are a business analyst writing a clear, actionable report. Given
analysis results, SQL query, and charts, create a comprehensive markdown
report.

Structure your report as:
1. **Executive Summary** - Key findings in 2-3 sentences
2. **Question** - The original business question
3. **Methodology** - How the analysis was performed (SQL query summary,
   statistical methods)
4. **Key Findings** - Detailed findings with numbers
5. **Visualizations** - Reference generated charts
6. **Recommendations** - Actionable next steps based on findings

Use clear business language. Include specific numbers and percentages.
If there were errors or missing data, note them transparently.
```

```
reporter_node(state, config)
    │
    ├── Build context string from ALL state:
    │   ├── "Original Question: {state.question}"
    │   ├── "SQL Query:\n```sql\n{query_result.sql}\n```"
    │   ├── "Rows returned: {query_result.row_count}"
    │   ├── "Analysis Insights:\n- {insight1}\n- {insight2}\n..."
    │   ├── "Summary Statistics: {json}"
    │   ├── "Correlations: {json}"
    │   ├── "Charts Generated:\n- {title} ({type}): {description}"
    │   └── "Errors Encountered:\n- {error1}\n- {error2}" (if any)
    │
    ├── messages = [
    │       SystemMessage(REPORTER_SYSTEM_PROMPT),
    │       HumanMessage(context)
    │   ]
    │
    ├── response = llm.invoke(messages, config=config)
    │
    └── return {"report": response.content}
```

---

## 7. Routing Logic

### File: `src/graph/routing.py` (22 lines)

### Constant

```python
MAX_SQL_RETRIES = 2  # line 7
```

### Function: `route_after_sql`

```python
def route_after_sql(state: AnalystState) -> str   # lines 10-22
```

### Decision Tree

```
route_after_sql(state)
    │
    ├── qr = state["query_result"]
    ├── retry_count = state.get("sql_retry_count", 0)
    │
    ├── Does qr.error exist?
    │   │
    │   ├── YES ──► Is retry_count < MAX_SQL_RETRIES (2)?
    │   │           │
    │   │           ├── YES ──► return "sql_error_handler"
    │   │           │           (retry: fix the SQL)
    │   │           │
    │   │           └── NO  ──► return "reporter"
    │   │                       (give up: produce partial report)
    │   │
    │   └── NO  ──► Is qr.row_count == 0?
    │               │
    │               ├── YES ──► return "reporter"
    │               │           (no data: skip analysis, report directly)
    │               │
    │               └── NO  ──► return "analyst"
    │                           (success: proceed to analysis)
```

### All Possible Paths Through the Graph

```
Path 1: HAPPY PATH (most common)
  introspect → planner → sql_agent → analyst → visualizer → reporter → END

Path 2: SQL ERROR, RETRY SUCCEEDS
  introspect → planner → sql_agent → sql_error_handler → sql_agent → analyst → visualizer → reporter → END

Path 3: SQL ERROR, BOTH RETRIES FAIL
  introspect → planner → sql_agent → sql_error_handler → sql_agent → sql_error_handler → sql_agent → reporter → END

Path 4: SQL SUCCEEDS BUT ZERO ROWS
  introspect → planner → sql_agent → reporter → END

Path 5: SQL ERROR ON FIRST RETRY, ZERO ROWS ON SECOND
  introspect → planner → sql_agent → sql_error_handler → sql_agent → reporter → END
```

---

## 8. Tools & Utilities

### StatsToolkit

**File:** `src/tools/stats_toolkit.py` (129 lines)

```
┌──────────────────────────────────────────────────────────────┐
│  StatsToolkit                                                │
│  ─────────────                                               │
│                                                              │
│  Constructor: StatsToolkit(data: list[dict], columns: list[str])
│      └── self._df = pd.DataFrame(data, columns=columns)     │
│                                                              │
│  Properties:                                                 │
│  ├── is_empty: bool  (lines 29-31)                           │
│  │                                                           │
│  Methods:                                                    │
│  ├── descriptive_stats(columns?) → dict   (lines 33-48)     │
│  │   └── pandas describe() + skewness, kurtosis, median     │
│  │                                                           │
│  ├── correlation_matrix(columns?) → dict  (lines 50-57)     │
│  │   └── Pearson correlations on numeric columns             │
│  │                                                           │
│  ├── t_test(col_a, col_b) → dict         (lines 59-71)      │
│  │   └── scipy.stats.ttest_ind (Welch's)                    │
│  │       Returns: {t_statistic, p_value, significant}        │
│  │                                                           │
│  ├── trend_analysis(date_col, val_col) → dict (lines 73-93) │
│  │   └── scipy.stats.linregress                              │
│  │       Returns: {slope, intercept, r_squared, p_value,     │
│  │                 direction}                                │
│  │                                                           │
│  ├── group_comparison(group, val) → dict  (lines 95-114)    │
│  │   └── scipy.stats.f_oneway (ANOVA)                       │
│  │       Returns: {groups: {name: stats}, f_statistic,       │
│  │                 p_value, significant}                     │
│  │                                                           │
│  └── full_analysis() → StatsResult        (lines 116-129)   │
│      ├── Calls descriptive_stats()                           │
│      ├── Calls correlation_matrix()                          │
│      ├── Flattens correlations to pairs                      │
│      └── Returns StatsResult(summary, tests=[], correlations,│
│                               trends={})                    │
│                                                              │
│  Dependencies: pandas, numpy, scipy.stats                    │
└──────────────────────────────────────────────────────────────┘

@dataclass
class StatsResult (lines 13-20):
    summary: dict[str, Any]
    tests: list[dict[str, Any]]
    correlations: dict[str, float]
    trends: dict[str, Any]
```

---

### ChartBuilder

**File:** `src/tools/chart_builder.py` (165 lines)

```
┌──────────────────────────────────────────────────────────────┐
│  ChartBuilder                                                │
│  ────────────                                                │
│                                                              │
│  Constructor: ChartBuilder(output_dir: str = "output")       │
│      ├── Creates output_dir if not exists                    │
│      ├── Sets seaborn theme: "whitegrid"                     │
│      └── Sets palette: "husl"                                │
│                                                              │
│  Private:                                                    │
│  └── _save_path(name, ext) → str  (lines 39-41)             │
│      └── Returns: f"{output_dir}/{name}.{ext}"               │
│                                                              │
│  Methods (all return ChartArtifact):                         │
│  │                                                           │
│  ├── bar_chart(df, x, y, title, name)     (lines 43-63)     │
│  │   └── seaborn.barplot → PNG                               │
│  │                                                           │
│  ├── line_chart(df, x, y, title, name)    (lines 65-83)     │
│  │   └── seaborn.lineplot (with markers) → PNG               │
│  │                                                           │
│  ├── pie_chart(df, labels, values, title, name) (lines 85-102)
│  │   └── matplotlib.pie (with percentages) → PNG             │
│  │                                                           │
│  ├── scatter_plot(df, x, y, title, name, hue?) (lines 104-122)
│  │   └── seaborn.scatterplot (optional hue) → PNG            │
│  │                                                           │
│  ├── histogram(df, column, title, name, bins=30) (lines 124-141)
│  │   └── seaborn.histplot (with KDE overlay) → PNG           │
│  │                                                           │
│  └── plotly_interactive(df, chart_type, x, y, title, name,   │
│                          **kwargs) (lines 143-165)           │
│      └── plotly.express → HTML file                          │
│                                                              │
│  All static methods:                                         │
│  ├── Use matplotlib Agg backend (non-interactive)            │
│  ├── Save to disk (PNG or HTML)                              │
│  ├── Close figure after save (plt.close())                   │
│  └── Return ChartArtifact with path, type, title, description│
│                                                              │
│  Dependencies: matplotlib, seaborn, plotly, pandas           │
└──────────────────────────────────────────────────────────────┘

@dataclass
class ChartArtifact (chart_builder.py:21-28):
    path: str
    chart_type: str
    title: str
    description: str
```

---

### LangChain Tool Wrappers

These are `@tool`-decorated functions for potential agent use (not currently used in the main pipeline but available):

```
┌──────────────────────────────────────────────────────────────┐
│  db_query tool                                               │
│  File: src/tools/db_query.py (51 lines)                      │
│  Factory: create_db_query_tool(pool, max_rows)               │
│                                                              │
│  Validates SQL:                                              │
│  ├── Must start with: SELECT or WITH                         │
│  ├── Forbidden: INSERT, UPDATE, DELETE, DROP,                │
│  │              ALTER, CREATE, TRUNCATE, GRANT               │
│  │                                                           │
│  Executes: pool.execute_query(sql)                           │
│  Returns: {"columns": ..., "rows": ..., "row_count": ...}   │
│       or: {"error": str}                                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  schema_inspector tool                                       │
│  File: src/tools/schema_inspector.py (37 lines)              │
│  Factory: create_schema_inspector_tool(pool)                 │
│                                                              │
│  Actions:                                                    │
│  ├── "summary" → SchemaIntrospector.get_schema_summary()     │
│  └── "sample"  → SchemaIntrospector.get_sample_values()      │
│                                                              │
│  Returns: Formatted text string                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. Observability System

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITY SYSTEM                              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  ObservabilityManager     (src/observability/__init__.py:24-29)  │  │
│  │  ─────────────────────                                           │  │
│  │  callbacks: list[BaseCallbackHandler]   # Langfuse handler(s)    │  │
│  │  llm_kwargs: dict[str, Any]             # Proxy config           │  │
│  │  active_providers: list[str]            # ["langsmith", ...]     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  configure_observability(settings) → ObservabilityManager        │  │
│  │  (lines 32-71)                                                   │  │
│  │                                                                  │  │
│  │  settings.langsmith.enabled?                                     │  │
│  │  ├── YES → setup_langsmith(settings.langsmith)                   │  │
│  │  │         Sets env vars:                                        │  │
│  │  │         ├── LANGCHAIN_TRACING_V2 = "true"                     │  │
│  │  │         ├── LANGCHAIN_API_KEY = api_key                       │  │
│  │  │         └── LANGCHAIN_PROJECT = project                       │  │
│  │  │         Mechanism: LangChain auto-detects env vars            │  │
│  │  └── NO  → skip                                                  │  │
│  │                                                                  │  │
│  │  settings.langfuse.enabled?                                      │  │
│  │  ├── YES → handler = setup_langfuse(settings.langfuse)           │  │
│  │  │         Creates: LangfuseCallbackHandler(                     │  │
│  │  │             public_key, secret_key, host)                     │  │
│  │  │         Adds to: callbacks list                               │  │
│  │  └── NO  → skip                                                  │  │
│  │                                                                  │  │
│  │  settings.helicone.enabled?                                      │  │
│  │  ├── YES → kwargs = setup_helicone(settings.helicone)            │  │
│  │  │         Returns: {                                            │  │
│  │  │             "base_url": "https://oai.helicone.ai/v1",        │  │
│  │  │             "default_headers": {                              │  │
│  │  │                 "Helicone-Auth": "Bearer {api_key}"           │  │
│  │  │             }                                                 │  │
│  │  │         }                                                     │  │
│  │  │         Mechanism: OpenAI proxy                               │  │
│  │  └── NO  → skip                                                  │  │
│  │                                                                  │  │
│  │  settings.braintrust.enabled?                                    │  │
│  │  ├── YES → kwargs = setup_braintrust(settings.braintrust)        │  │
│  │  │         Returns: {                                            │  │
│  │  │             "base_url": "https://api.braintrust.dev/v1/proxy",│  │
│  │  │             "default_headers": {                              │  │
│  │  │                 "Authorization": "Bearer {api_key}"           │  │
│  │  │             }                                                 │  │
│  │  │         }                                                     │  │
│  │  │         Note: Conflicts with Helicone (same base_url slot)    │  │
│  │  └── NO  → skip                                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  create_llm(settings, manager, node_name) → ChatOpenAI           │  │
│  │  (lines 74-92)                                                   │  │
│  │                                                                  │  │
│  │  ChatOpenAI(                                                     │  │
│  │      model = settings.llm.model,          # "gpt-4o"            │  │
│  │      temperature = settings.llm.temperature, # 0.0              │  │
│  │      max_tokens = settings.llm.max_tokens,   # 4096             │  │
│  │      api_key = settings.llm.api_key,                             │  │
│  │      request_timeout = settings.llm.request_timeout, # 60       │  │
│  │      **manager.llm_kwargs,                # Proxy config         │  │
│  │      default_headers = {                  # Per-node tracking    │  │
│  │          **existing_headers,                                     │  │
│  │          "Helicone-Session-Name": node_name                      │  │
│  │      }                                                           │  │
│  │  )                                                               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Helper Functions                                                │  │
│  │                                                                  │  │
│  │  get_callbacks(manager) → list        (lines 95-97)              │  │
│  │      └── Returns COPY of manager.callbacks (list(...))           │  │
│  │                                                                  │  │
│  │  flush_callbacks(manager) → None      (lines 100-109)            │  │
│  │      └── For each callback in manager.callbacks:                 │  │
│  │          if hasattr(cb, "langfuse"):                             │  │
│  │              cb.langfuse.flush()       # Duck-typing             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  trace_node(node_name) → decorator    (src/observability/        │  │
│  │  (tracing.py:12-38)                    tracing.py)               │  │
│  │                                                                  │  │
│  │  @trace_node("planner")                                          │  │
│  │  def planner_node(state, config):                                │  │
│  │      ...                                                         │  │
│  │                                                                  │  │
│  │  Behavior:                                                       │  │
│  │  ├── Logs: "[planner] Starting"           (loguru.info)          │  │
│  │  ├── Starts: time.perf_counter()                                 │  │
│  │  ├── Calls: wrapped function                                     │  │
│  │  ├── On success: "[planner] Completed in 2.34s"                  │  │
│  │  └── On error:   "[planner] Error after 0.12s: ..."              │  │
│  │                   (re-raises exception)                          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  CompositeCallbackManager (src/observability/callbacks.py:10-35) │  │
│  │                                                                  │  │
│  │  __init__(handlers: list[BaseCallbackHandler])                   │  │
│  │  add_handler(handler) → None                                     │  │
│  │  handlers → list[BaseCallbackHandler]    (property)              │  │
│  │  with_metadata(node_name, run_id) → dict (RunnableConfig)        │  │
│  │  get_config() → dict                     (RunnableConfig)        │  │
│  │                                                                  │  │
│  │  Note: Available but not used by main entry points               │  │
│  │        (they use get_callbacks() + direct config instead)        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Provider Comparison

```
Provider      Mechanism         Setup Location         Conflict
──────────    ──────────────    ──────────────────     ────────────
LangSmith     Env vars          Auto-detected by       None
                                LangChain SDK
Langfuse      Callback handler  Passed via config      None
                                {"callbacks": [...]}
Helicone      OpenAI proxy      base_url + headers     Braintrust
                                on ChatOpenAI          (same slot)
Braintrust    OpenAI proxy      base_url + headers     Helicone
                                on ChatOpenAI          (same slot)
```

---

## 10. Callback Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CALLBACK LIFECYCLE FLOW                           │
│                                                                     │
│  1. CREATION                                                        │
│  ────────────                                                       │
│  configure_observability(settings)                                  │
│      ├── LangfuseCallbackHandler() ──► manager.callbacks            │
│      └── Proxy kwargs ──► manager.llm_kwargs                        │
│                                                                     │
│  2. INJECTION                                                       │
│  ───────────                                                        │
│  callbacks = get_callbacks(manager)    # Returns copy of list       │
│  config = {"callbacks": callbacks}     # RunnableConfig dict        │
│                                                                     │
│  3. PROPAGATION                                                     │
│  ──────────────                                                     │
│  graph.invoke(initial_state, config=config)                         │
│      │                                                              │
│      ├── Node receives config parameter                             │
│      │   (only nodes that accept `config` argument)                 │
│      │                                                              │
│      └── Node passes config to LLM:                                 │
│          llm.invoke(messages, config=config)                        │
│              └── LangChain extracts callbacks from config            │
│                                                                     │
│  4. EVENT CAPTURE                                                   │
│  ────────────────                                                   │
│  LangChain SDK automatically fires callback events:                 │
│      ├── on_llm_start(prompt, ...)                                  │
│      ├── on_llm_end(response, ...)                                  │
│      ├── on_llm_error(error, ...)                                   │
│      ├── on_chain_start(...)                                        │
│      └── on_chain_end(...)                                          │
│                                                                     │
│  Meanwhile, trace_node decorator logs independently:                │
│      ├── loguru.info("[node] Starting")                             │
│      └── loguru.info("[node] Completed in Xs")                      │
│                                                                     │
│  5. FLUSH                                                           │
│  ────────                                                           │
│  flush_callbacks(manager)                                           │
│      └── For Langfuse: cb.langfuse.flush()                          │
│          (ensures all events are sent before process exits)          │
│                                                                     │
│  Called by entry points AFTER graph execution completes              │
└─────────────────────────────────────────────────────────────────────┘
```

### Config Propagation Per Node

```
Node                  Accepts Config?   Passes to LLM?
────────────────────  ────────────────  ──────────────
introspect_schema     NO                N/A (no LLM)
planner               YES               YES
sql_agent             YES               YES
sql_error_handler     YES               YES
analyst               NO                N/A (no LLM)
visualizer            YES               YES
reporter              YES               YES
```

---

## 11. Complete File Map

```
10-ai-data-analyst/
│
├── docs/
│   └── SYSTEM_ARCHITECTURE.md           # This file
│
├── examples/
│   ├── simple_analysis.py          (76 lines)  # CLI entry point
│   └── interactive_session.py      (62 lines)  # REPL entry point
│
├── src/
│   ├── __init__.py                 (1 line)    # Package marker
│   │
│   ├── agents/
│   │   ├── __init__.py             (16 lines)  # Re-exports all agent factories
│   │   ├── planner.py              (41 lines)  # Analysis planner (LLM, structured output)
│   │   ├── sql_agent.py            (106 lines) # SQL generation + error handler (LLM + DB)
│   │   ├── analyst.py              (55 lines)  # Statistical analysis (no LLM)
│   │   ├── visualizer.py           (116 lines) # Chart recommendations + generation (LLM)
│   │   └── reporter.py             (64 lines)  # Markdown report generation (LLM)
│   │
│   ├── config/
│   │   ├── __init__.py             (5 lines)   # Re-exports Settings, get_settings
│   │   └── settings.py             (85 lines)  # Pydantic Settings classes (6 nested)
│   │
│   ├── db/
│   │   ├── __init__.py             (6 lines)   # Re-exports pool + introspector
│   │   ├── connection.py           (83 lines)  # psycopg3 pool, read-only enforcement
│   │   └── introspect.py           (128 lines) # Schema introspection (tables, columns, PKs)
│   │
│   ├── graph/
│   │   ├── __init__.py             (6 lines)   # Re-exports build_graph, state models
│   │   ├── builder.py              (118 lines) # Graph assembly: nodes, edges, LLMs
│   │   ├── routing.py              (22 lines)  # Conditional routing after SQL
│   │   └── state.py                (74 lines)  # Pydantic state models (5 models)
│   │
│   ├── observability/
│   │   ├── __init__.py             (119 lines) # Manager, configure, create_llm, flush
│   │   ├── callbacks.py            (35 lines)  # CompositeCallbackManager
│   │   ├── providers.py            (62 lines)  # LangSmith, Langfuse, Helicone, Braintrust
│   │   └── tracing.py              (38 lines)  # trace_node decorator (loguru + timing)
│   │
│   ├── tools/
│   │   ├── __init__.py             (8 lines)   # Re-exports tools
│   │   ├── chart_builder.py        (165 lines) # ChartBuilder (5 chart types + plotly)
│   │   ├── stats_toolkit.py        (129 lines) # StatsToolkit (6 analysis methods)
│   │   ├── db_query.py             (51 lines)  # LangChain @tool for SQL queries
│   │   └── schema_inspector.py     (37 lines)  # LangChain @tool for schema inspection
│   │
│   └── streamlit_app/
│       ├── __init__.py             (0 lines)   # Package marker
│       └── app.py                  (672 lines) # Full Streamlit web UI
│
├── tests/
│   ├── conftest.py                 (112 lines) # Shared fixtures
│   ├── unit/
│   │   ├── test_analyst.py         (61 lines)
│   │   ├── test_db_query.py        (54 lines)
│   │   ├── test_observability.py   (191 lines)
│   │   ├── test_planner.py         (53 lines)
│   │   ├── test_reporter.py        (60 lines)
│   │   ├── test_routing.py         (51 lines)
│   │   ├── test_sql_agent.py       (84 lines)
│   │   ├── test_state.py           (105 lines)
│   │   └── test_visualizer.py      (81 lines)
│   └── integration/
│       └── test_graph_e2e.py       (110 lines)
│
├── pyproject.toml                              # Poetry dependencies
├── .env                                        # Environment variables (not committed)
└── .env.example                                # Template for .env
```

---

## 12. Dependency & Prerequisites Chain

### Initialization Order

```
┌─────────────────────────────────────────────────────────────────┐
│                  INITIALIZATION ORDER                           │
│                                                                 │
│  Level 0: No Dependencies                                      │
│  ─────────────────────────                                      │
│  ├── Settings / get_settings()     ◄── reads .env file          │
│  └── StatsResult (dataclass)                                    │
│                                                                 │
│  Level 1: Depends on Settings                                   │
│  ─────────────────────────────                                  │
│  ├── DatabasePool(settings.database)                            │
│  │       └── .open() must be called                             │
│  └── ObservabilityManager                                       │
│          └── configure_observability(settings)                  │
│                                                                 │
│  Level 2: Depends on Level 1                                    │
│  ─────────────────────────────                                  │
│  ├── SchemaIntrospector(pool)                                   │
│  ├── create_llm(settings, obs_manager, node_name)               │
│  └── ChartBuilder(output_dir)                                   │
│                                                                 │
│  Level 3: Depends on Level 2                                    │
│  ─────────────────────────────                                  │
│  └── build_graph(settings, pool, obs_manager)                   │
│          ├── Creates 4 LLM instances                            │
│          ├── Creates 7 node functions                           │
│          └── Returns compiled StateGraph                        │
│                                                                 │
│  Level 4: Depends on Level 3 (Runtime)                          │
│  ──────────────────────────────────────                          │
│  └── graph.invoke(state, config)  or  graph.stream(...)         │
│          ├── Requires: {"question": str} in state               │
│          └── Requires: {"callbacks": [...]} in config           │
│                                                                 │
│  Level 5: Post-Execution                                        │
│  ────────────────────────                                       │
│  └── flush_callbacks(obs_manager)                               │
└─────────────────────────────────────────────────────────────────┘
```

### Component Dependency Graph

```
                    .env file
                        │
                        ▼
                ┌───────────────┐
                │   Settings    │
                └───────┬───────┘
                        │
           ┌────────────┼────────────────┐
           │            │                │
           ▼            ▼                ▼
    ┌────────────┐ ┌──────────┐  ┌──────────────────┐
    │DatabasePool│ │Observ.   │  │   ChartBuilder   │
    │            │ │Manager   │  │  (output_dir)    │
    └──────┬─────┘ └────┬─────┘  └────────┬─────────┘
           │            │                 │
    ┌──────┴─────┐      │                 │
    │            │      │                 │
    ▼            ▼      ▼                 │
┌────────┐ ┌────────────────┐             │
│Schema  │ │  create_llm()  │             │
│Intro-  │ │  (x4 nodes)   │             │
│spector │ └───────┬────────┘             │
└────┬───┘         │                      │
     │             │                      │
     └──────┬──────┴──────────────────────┘
            │
            ▼
    ┌───────────────┐
    │  build_graph  │
    │               │
    │  7 Nodes:     │
    │  ├ introspect │ ◄── SchemaIntrospector
    │  ├ planner    │ ◄── LLM (structured output)
    │  ├ sql_agent  │ ◄── LLM + DatabasePool
    │  ├ sql_error  │ ◄── LLM + DatabasePool
    │  ├ analyst    │ ◄── StatsToolkit
    │  ├ visualizer │ ◄── LLM + ChartBuilder
    │  └ reporter   │ ◄── LLM
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ Compiled      │
    │ StateGraph    │──────► graph.invoke() / graph.stream()
    └───────────────┘
```

### Runtime Data Flow (End-to-End)

```
User Question: "What are the top 5 products by revenue?"
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  introspect_schema                                                  │
│  IN:  (nothing from state)                                          │
│  DO:  SchemaIntrospector → queries information_schema                │
│  OUT: schema_summary = "Table: products (id PK, name, price...)"   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  planner                                                            │
│  IN:  schema_summary + question                                     │
│  DO:  LLM → structured output (AnalysisPlan)                        │
│  OUT: plan = {                                                      │
│           question: "Top 5 products by revenue",                    │
│           sub_questions: ["Total revenue per product"],              │
│           required_tables: ["products", "order_items"],              │
│           analysis_type: "ranking",                                  │
│           suggested_visualizations: ["bar"]                          │
│       }                                                             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  sql_agent                                                          │
│  IN:  schema_summary + plan                                         │
│  DO:  LLM → SQL text → pool.execute_query()                         │
│  OUT: query_result = {                                              │
│           sql: "SELECT p.name, SUM(oi.quantity * oi.price)...",     │
│           columns: ["name", "revenue"],                              │
│           rows: [{name: "Widget A", revenue: 50000}, ...],          │
│           row_count: 5,                                              │
│           error: ""                                                  │
│       }                                                             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                          route_after_sql()
                          error=""  → "analyst"
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  analyst                                                            │
│  IN:  query_result (rows + columns)                                 │
│  DO:  StatsToolkit → descriptive_stats + correlations                │
│  OUT: analysis = {                                                  │
│           summary_stats: {revenue: {mean: 30000, std: 12000, ...}}, │
│           correlations: {},                                          │
│           insights: ["Revenue: mean=30000, std=12000, range=..."]   │
│       }                                                             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  visualizer                                                         │
│  IN:  question + query_result + analysis.insights + plan.suggestions│
│  DO:  LLM → ChartSpecs → ChartBuilder.bar_chart()                   │
│  OUT: charts = [{                                                   │
│           path: "output/top_products.png",                          │
│           chart_type: "bar",                                         │
│           title: "Top 5 Products by Revenue",                        │
│           description: "Bar chart showing..."                        │
│       }]                                                            │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  reporter                                                           │
│  IN:  ALL state fields                                              │
│  DO:  LLM → markdown report                                         │
│  OUT: report = "# Executive Summary\n\nThe top 5 products..."       │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
                          Final State returned
                          to entry point
```

---

## Appendix: Quick Reference

### All System Prompts Summary

| Node | Prompt Constant | Role | Output Format |
|---|---|---|---|
| planner | `PLANNER_SYSTEM_PROMPT` | Data analysis planner | Structured: `AnalysisPlan` |
| sql_agent | `SQL_AGENT_SYSTEM_PROMPT` | SQL expert | Raw text: SQL query |
| sql_error_handler | `SQL_AGENT_SYSTEM_PROMPT` + error context | SQL expert (retry) | Raw text: SQL query |
| visualizer | `VIZ_SYSTEM_PROMPT` | Visualization expert | Structured: `ChartSpecs` |
| reporter | `REPORTER_SYSTEM_PROMPT` | Business analyst | Raw text: Markdown |

### LLM Usage Summary

| Node | Uses LLM | Structured Output | Model |
|---|---|---|---|
| introspect_schema | No | N/A | N/A |
| planner | Yes | `AnalysisPlan` | gpt-4o (configurable) |
| sql_agent | Yes | No (raw text) | gpt-4o (configurable) |
| sql_error_handler | Yes | No (raw text) | gpt-4o (configurable) |
| analyst | No | N/A | N/A |
| visualizer | Yes | `ChartSpecs` | gpt-4o (configurable) |
| reporter | Yes | No (raw text) | gpt-4o (configurable) |

### External Dependencies

| Package | Used By | Purpose |
|---|---|---|
| langchain-openai | All LLM nodes | ChatOpenAI interface |
| langgraph | graph/builder.py | StateGraph compilation |
| psycopg[pool] | db/connection.py | PostgreSQL connection pool |
| pandas | stats_toolkit, chart_builder, analyst, visualizer | DataFrames |
| numpy | stats_toolkit | Numeric operations |
| scipy | stats_toolkit | t-test, ANOVA, regression |
| matplotlib | chart_builder | Static chart rendering |
| seaborn | chart_builder | Statistical visualizations |
| plotly | chart_builder | Interactive charts |
| pydantic-settings | config/settings.py | Env-based configuration |
| loguru | observability/tracing.py | Structured logging |
| streamlit | streamlit_app/app.py | Web UI framework |
