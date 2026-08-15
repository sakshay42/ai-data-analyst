"""Enhanced Streamlit UI for the AI Data Analyst."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from src.config.settings import Settings
from src.db.connection import DatabasePool
from src.db.introspect import SchemaIntrospector, TableInfo
from src.graph.builder import build_graph
from src.graph.state import (
    AnalysisResult,
    AnalysisPlan,
    AnalystState,
    ChartArtifact,
    QueryResult,
)
from src.observability import configure_observability, create_session_callbacks, flush_callbacks

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

def inject_custom_css() -> None:
    """Inject custom styles for the enhanced UI."""
    st.markdown(
        """
        <style>
        /* ---- Pipeline progress tracker ---- */
        .pipeline-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0;
            margin: 1.5rem 0 2rem 0;
        }
        .pipeline-step {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 90px;
        }
        .pipeline-circle {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: 700;
            color: #fff;
            transition: all 0.3s ease;
        }
        .pipeline-circle.pending { background: #333; border: 2px solid #555; }
        .pipeline-circle.active  {
            background: #1565C0;
            border: 2px solid #4FC3F7;
            box-shadow: 0 0 12px rgba(79,195,247,0.6);
            animation: pulse 1.2s ease-in-out infinite;
        }
        .pipeline-circle.completed { background: #2E7D32; border: 2px solid #66BB6A; }
        .pipeline-circle.error     { background: #C62828; border: 2px solid #EF5350; }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 6px rgba(79,195,247,0.4); }
            50%      { box-shadow: 0 0 18px rgba(79,195,247,0.8); }
        }
        .pipeline-label {
            font-size: 0.7rem;
            margin-top: 6px;
            color: #aaa;
            text-align: center;
        }
        .pipeline-line {
            width: 40px;
            height: 2px;
            background: #444;
            margin-bottom: 20px;
        }
        .pipeline-line.completed { background: #66BB6A; }
        .pipeline-line.active    { background: #4FC3F7; }

        /* ---- Sidebar schema cards ---- */
        .schema-card {
            background: #1a2030;
            border: 1px solid #2a3545;
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 4px;
        }
        .schema-card .col-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 3px 0;
            font-size: 0.82rem;
            border-bottom: 1px solid #1e2838;
        }
        .schema-card .col-row:last-child { border-bottom: none; }
        .schema-card .col-name { color: #e0e0e0; font-family: monospace; }
        .schema-card .col-type { color: #888; font-size: 0.75rem; font-family: monospace; }
        .pk-badge {
            background: #F9A825;
            color: #000;
            padding: 1px 6px;
            border-radius: 4px;
            font-size: 0.65rem;
            font-weight: 700;
            margin-left: 6px;
        }
        .nullable-badge {
            color: #666;
            font-size: 0.65rem;
            margin-left: 4px;
        }

        /* ---- Example question buttons ---- */
        .example-btn {
            display: block;
            width: 100%;
            background: #1a2030;
            border: 1px solid #2a3545;
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 6px;
            color: #ccc;
            font-size: 0.82rem;
            cursor: pointer;
            text-align: left;
            transition: all 0.2s ease;
        }
        .example-btn:hover {
            background: #243040;
            border-color: #4FC3F7;
            color: #fff;
        }

        /* ---- Result cards ---- */
        .result-card {
            background: #161c26;
            border: 1px solid #2a3545;
            border-radius: 10px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }

        /* ---- History items ---- */
        .history-item {
            padding: 6px 10px;
            margin-bottom: 4px;
            border-left: 3px solid #333;
            font-size: 0.8rem;
            color: #aaa;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .history-item:hover {
            border-left-color: #4FC3F7;
            color: #fff;
        }

        /* ---- General ---- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 6px 6px 0 0;
            padding: 8px 20px;
        }
        code { font-family: 'JetBrains Mono', 'Fira Code', monospace; }

        /* Connection badge */
        .conn-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .conn-badge.ok   { background: #1B5E20; color: #A5D6A7; }
        .conn-badge.fail { background: #B71C1C; color: #EF9A9A; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_session_state() -> None:
    """Initialize session-state keys."""
    if "analysis_history" not in st.session_state:
        st.session_state.analysis_history = []
    if "current_analysis" not in st.session_state:
        st.session_state.current_analysis = None
    if "current_question" not in st.session_state:
        st.session_state.current_question = ""
    if "schema_cache" not in st.session_state:
        st.session_state.schema_cache = None
    if "langfuse_session_id" not in st.session_state:
        import uuid

        st.session_state.langfuse_session_id = f"streamlit-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Pipeline initialization (cached)
# ---------------------------------------------------------------------------

@st.cache_resource
def init_pipeline():
    """Initialize settings, DB pool, observability, and graph."""
    settings = Settings()
    pool = DatabasePool(settings.database)
    pool.open()
    obs_manager = configure_observability(settings)
    graph = build_graph(settings, pool, obs_manager)
    introspector = SchemaIntrospector(pool)
    return settings, pool, obs_manager, graph, introspector


@st.cache_data(ttl=300)
def load_schema(_introspector: SchemaIntrospector) -> list[TableInfo]:
    """Load database schema with 5-minute cache."""
    return _introspector.get_tables()


# ---------------------------------------------------------------------------
# Pipeline progress rendering
# ---------------------------------------------------------------------------

PIPELINE_NODES = [
    ("introspect_schema", "Schema"),
    ("planner", "Plan"),
    ("sql_agent", "SQL"),
    ("analyst", "Stats"),
    ("visualizer", "Charts"),
    ("reporter", "Report"),
]


def render_pipeline_progress(status: dict[str, str]) -> str:
    """Return HTML for the horizontal pipeline progress tracker."""
    html_parts = ['<div class="pipeline-container">']
    for i, (node_id, label) in enumerate(PIPELINE_NODES):
        state = status.get(node_id, "pending")
        html_parts.append(
            f'<div class="pipeline-step">'
            f'  <div class="pipeline-circle {state}">{i + 1}</div>'
            f'  <div class="pipeline-label">{label}</div>'
            f"</div>"
        )
        if i < len(PIPELINE_NODES) - 1:
            line_cls = state if state == "completed" else "pending"
            # Check if next node is active
            next_node = PIPELINE_NODES[i + 1][0]
            next_state = status.get(next_node, "pending")
            if next_state in ("active", "completed"):
                line_cls = "completed"
            elif next_state == "active":
                line_cls = "active"
            html_parts.append(f'<div class="pipeline-line {line_cls}"></div>')
    html_parts.append("</div>")
    return "".join(html_parts)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(
    settings: Settings,
    obs_manager,
    tables: list[TableInfo],
) -> None:
    """Render the full sidebar: schema browser, examples, history, status."""
    with st.sidebar:
        st.markdown("## 📊 AI Data Analyst")
        model_name = settings.llm.model if hasattr(settings.llm, "model") else "gpt-4o"
        st.markdown(
            f'<span style="background:#1565C0;padding:3px 10px;border-radius:12px;'
            f'font-size:0.75rem;color:#fff;">{model_name}</span>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # -- Schema browser --
        st.markdown("### Database Schema")
        if tables:
            for table in tables:
                with st.expander(f"**{table.name}** ({table.row_count_estimate:,} rows)"):
                    for col in table.columns:
                        badges = ""
                        if col.is_primary_key:
                            badges += '<span class="pk-badge">PK</span>'
                        if col.is_nullable:
                            badges += '<span class="nullable-badge">nullable</span>'
                        st.markdown(
                            f'<div class="schema-card"><div class="col-row">'
                            f'<span class="col-name">{col.name}</span>'
                            f'<span class="col-type">{col.data_type}{badges}</span>'
                            f"</div></div>",
                            unsafe_allow_html=True,
                        )
        else:
            st.info("No tables found.")

        st.markdown("---")

        # -- Example questions --
        st.markdown("### Example Questions")
        examples = [
            "Top 10 products by revenue?",
            "Monthly revenue trends",
            "Customer segments by order value",
            "Sales distribution across categories",
            "Average review rating by product category",
        ]
        for q in examples:
            if st.button(q, key=f"ex_{q}", use_container_width=True):
                st.session_state.current_question = q

        st.markdown("---")

        # -- Analysis history --
        st.markdown("### History")
        if st.session_state.analysis_history:
            for i, entry in enumerate(reversed(st.session_state.analysis_history)):
                ts = entry["timestamp"]
                short_q = entry["question"][:50] + ("..." if len(entry["question"]) > 50 else "")
                if st.button(f"{ts}  {short_q}", key=f"hist_{i}", use_container_width=True):
                    st.session_state.current_analysis = entry["result"]
                    st.session_state.current_question = entry["question"]
        else:
            st.caption("No analyses yet.")

        st.markdown("---")

        # -- Connection status --
        st.markdown("### Status")
        st.markdown(
            '<span class="conn-badge ok">DB Connected</span>',
            unsafe_allow_html=True,
        )
        providers = obs_manager.active_providers
        if providers:
            st.caption(f"Observability: {', '.join(providers)}")
        else:
            st.caption("Observability: None")


# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------

def display_results(result: dict) -> None:
    """Render the analysis results across five tabs."""
    tab_report, tab_charts, tab_sql, tab_data, tab_stats = st.tabs(
        ["Report", "Charts", "SQL Query", "Data", "Statistics"]
    )

    # --- Report ---
    with tab_report:
        report: str = result.get("report", "")
        if report:
            st.markdown(report)
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "Download Markdown",
                    data=report,
                    file_name="analysis_report.md",
                    mime="text/markdown",
                )
            with col2:
                html_report = f"<html><body><pre>{report}</pre></body></html>"
                st.download_button(
                    "Download HTML",
                    data=html_report,
                    file_name="analysis_report.html",
                    mime="text/html",
                )
        else:
            st.info("No report generated.")

    # --- Charts ---
    with tab_charts:
        charts: list[ChartArtifact] = result.get("charts", [])
        if charts:
            for chart in charts:
                st.subheader(chart.title or "Chart")
                chart_path = chart.path
                if chart_path and os.path.exists(chart_path):
                    if chart_path.endswith(".html"):
                        with open(chart_path) as f:
                            components.html(f.read(), height=520, scrolling=True)
                    else:
                        st.image(chart_path)
                        with open(chart_path, "rb") as f:
                            st.download_button(
                                f"Download {Path(chart_path).name}",
                                data=f.read(),
                                file_name=Path(chart_path).name,
                                mime="image/png",
                                key=f"dl_chart_{chart_path}",
                            )
                if chart.description:
                    st.caption(chart.description)
        else:
            st.info("No charts were generated.")

    # --- SQL ---
    with tab_sql:
        qr: QueryResult = result.get("query_result", QueryResult())
        if qr.sql:
            st.code(qr.sql, language="sql")
            col1, col2 = st.columns(2)
            col1.metric("Rows returned", qr.row_count)
            col2.metric("Columns", len(qr.columns))
        else:
            st.info("No SQL query was executed.")
        if qr.error:
            st.error(f"SQL Error: {qr.error}")

    # --- Data ---
    with tab_data:
        qr_data: QueryResult = result.get("query_result", QueryResult())
        if qr_data.rows:
            df = pd.DataFrame(qr_data.rows)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                data=csv,
                file_name="query_results.csv",
                mime="text/csv",
            )
        else:
            st.info("No data rows returned.")

    # --- Statistics ---
    with tab_stats:
        analysis: AnalysisResult = result.get("analysis", AnalysisResult())

        if analysis.insights:
            st.markdown("#### Insights")
            for insight in analysis.insights:
                st.markdown(f"- {insight}")

        if analysis.summary_stats:
            st.markdown("#### Summary Statistics")
            try:
                stats_df = pd.DataFrame(analysis.summary_stats)
                st.dataframe(stats_df, use_container_width=True)
            except Exception:
                st.json(analysis.summary_stats)

        if analysis.correlations:
            st.markdown("#### Correlations")
            sorted_corr = sorted(
                analysis.correlations.items(), key=lambda x: abs(x[1]), reverse=True
            )
            corr_df = pd.DataFrame(sorted_corr, columns=["Pair", "Correlation"])
            st.dataframe(corr_df, use_container_width=True)

        if analysis.trends:
            with st.expander("Trends (raw)"):
                st.json(analysis.trends)

        if analysis.tests:
            with st.expander("Statistical Tests (raw)"):
                st.json(analysis.tests)

        if (
            not analysis.insights
            and not analysis.summary_stats
            and not analysis.correlations
        ):
            st.info("No statistical analysis was produced.")

    # --- Analysis Plan (collapsible) ---
    plan: AnalysisPlan = result.get("plan", AnalysisPlan())
    if plan.analysis_type or plan.required_tables or plan.sub_questions:
        with st.expander("Analysis Plan"):
            if plan.analysis_type:
                st.markdown(f"**Type:** {plan.analysis_type}")
            if plan.required_tables:
                st.markdown(f"**Tables:** {', '.join(plan.required_tables)}")
            if plan.sub_questions:
                st.markdown("**Sub-questions:**")
                for sq in plan.sub_questions:
                    st.markdown(f"- {sq}")
            if plan.suggested_visualizations:
                st.markdown(f"**Suggested visualizations:** {', '.join(plan.suggested_visualizations)}")

    # --- Errors ---
    errors: list[str] = result.get("errors", [])
    if errors:
        with st.expander("Errors encountered", expanded=False):
            for err in errors:
                st.warning(err)


# ---------------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------------

def run_analysis(question: str, graph, obs_manager) -> dict | None:
    """Execute the pipeline with streaming progress updates."""
    initial_state = AnalystState(question=question)
    session_id = st.session_state.get("langfuse_session_id", "")
    callbacks = create_session_callbacks(obs_manager, session_id=session_id)
    config = {"callbacks": callbacks} if callbacks else {}

    # Node status tracking
    node_status: dict[str, str] = {n: "pending" for n, _ in PIPELINE_NODES}
    progress_container = st.empty()
    status_text = st.empty()

    # Render initial progress
    progress_container.markdown(
        render_pipeline_progress(node_status), unsafe_allow_html=True
    )

    # Map for error handler → show as sql_agent step
    node_alias = {"sql_error_handler": "sql_agent"}

    final_state: dict = {}
    try:
        for chunk in graph.stream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                display_node = node_alias.get(node_name, node_name)

                # Mark current node completed
                if display_node in node_status:
                    node_status[display_node] = "completed"

                # Mark next node active
                node_list = [n for n, _ in PIPELINE_NODES]
                if display_node in node_list:
                    idx = node_list.index(display_node)
                    if idx + 1 < len(node_list):
                        next_node = node_list[idx + 1]
                        if node_status[next_node] == "pending":
                            node_status[next_node] = "active"

                # Update UI
                status_text.caption(f"Completed: {display_node}")
                progress_container.markdown(
                    render_pipeline_progress(node_status), unsafe_allow_html=True
                )

                if isinstance(node_output, dict):
                    final_state.update(node_output)

        # Mark all as completed
        for n in node_status:
            if node_status[n] != "error":
                node_status[n] = "completed"
        progress_container.markdown(
            render_pipeline_progress(node_status), unsafe_allow_html=True
        )
        status_text.success("Analysis complete!")
        flush_callbacks(obs_manager)

        return final_state

    except Exception as e:
        # Mark current active node as error
        for n in node_status:
            if node_status[n] == "active":
                node_status[n] = "error"
        progress_container.markdown(
            render_pipeline_progress(node_status), unsafe_allow_html=True
        )
        status_text.error(f"Analysis failed: {e}")
        st.exception(e)
        flush_callbacks(obs_manager)
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Application entry point."""
    inject_custom_css()
    init_session_state()

    # -- Initialize pipeline --
    try:
        settings, pool, obs_manager, graph, introspector = init_pipeline()
        tables = load_schema(introspector)
    except Exception as e:
        st.error(f"Failed to initialize: {e}")
        st.info("Make sure your .env file is configured and the database is running.")
        st.stop()
        return  # unreachable but keeps linters happy

    # -- Sidebar --
    render_sidebar(settings, obs_manager, tables)

    # -- Main area --
    st.markdown("# AI Data Analyst")
    st.markdown(
        "Ask business questions in plain language and get data-driven answers "
        "with SQL, charts, and statistical analysis."
    )

    # -- Question input --
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        question = st.text_area(
            "Your business question:",
            value=st.session_state.current_question,
            placeholder="e.g., What are the top 5 products by revenue in the last quarter?",
            height=80,
            label_visibility="collapsed",
        )
    with col_btn:
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

    # -- Run analysis --
    if analyze_clicked and question.strip():
        st.session_state.current_question = question.strip()
        result = run_analysis(question.strip(), graph, obs_manager)
        if result is not None:
            st.session_state.current_analysis = result
            st.session_state.analysis_history.append(
                {
                    "question": question.strip(),
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "result": result,
                }
            )

    # -- Display current results --
    if st.session_state.current_analysis:
        st.markdown("---")
        display_results(st.session_state.current_analysis)


if __name__ == "__main__":
    main()
else:
    main()
