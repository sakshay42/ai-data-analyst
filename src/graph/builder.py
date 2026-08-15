"""Build the LangGraph state machine for the data analyst pipeline."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agents.analyst import analyst_node
from src.agents.planner import create_planner_node
from src.agents.reporter import create_reporter_node
from src.agents.sql_agent import create_sql_agent_node, create_sql_error_handler_node
from src.agents.visualizer import create_visualizer_node
from src.config.settings import Settings
from src.db.connection import DatabasePool
from src.db.introspect import SchemaIntrospector
from src.graph.routing import route_after_sql
from src.graph.state import AnalystState
from src.observability import ObservabilityManager, create_llm
from src.observability.tracing import trace_node


def _create_introspect_node(pool: DatabasePool):
    """Create the schema introspection node."""
    introspector = SchemaIntrospector(pool)

    @trace_node("introspect_schema")
    def introspect_schema_node(state: AnalystState) -> dict[str, Any]:
        """Introspect database schema and add summary to state."""
        summary = introspector.get_schema_summary()
        logger.info("Schema introspected: {} chars", len(summary))
        return {"schema_summary": summary}

    return introspect_schema_node


def build_graph(
    settings: Settings,
    pool: DatabasePool,
    obs_manager: ObservabilityManager | None = None,
) -> StateGraph:
    """Build and compile the full analyst state graph.

    Args:
        settings: Application settings.
        pool: Database connection pool.
        obs_manager: Observability manager (optional).

    Returns:
        Compiled LangGraph StateGraph.
    """
    if obs_manager is None:
        obs_manager = ObservabilityManager()

    # Create LLMs for each agent that needs one
    planner_llm = create_llm(settings, obs_manager, node_name="planner")
    sql_llm = create_llm(settings, obs_manager, node_name="sql_agent")
    viz_llm = create_llm(settings, obs_manager, node_name="visualizer")
    reporter_llm = create_llm(settings, obs_manager, node_name="reporter")

    # Create node functions
    introspect_node = _create_introspect_node(pool)
    planner = trace_node("planner")(create_planner_node(planner_llm))
    sql_agent = trace_node("sql_agent")(create_sql_agent_node(sql_llm, pool))
    sql_error_handler = trace_node("sql_error_handler")(
        create_sql_error_handler_node(sql_llm, pool)
    )
    analyst = trace_node("analyst")(analyst_node)
    visualizer = trace_node("visualizer")(create_visualizer_node(viz_llm, settings.output_dir))
    reporter = trace_node("reporter")(create_reporter_node(reporter_llm))

    # Build graph
    graph = StateGraph(AnalystState)

    # Add nodes
    graph.add_node("introspect_schema", introspect_node)
    graph.add_node("planner", planner)
    graph.add_node("sql_agent", sql_agent)
    graph.add_node("sql_error_handler", sql_error_handler)
    graph.add_node("analyst", analyst)
    graph.add_node("visualizer", visualizer)
    graph.add_node("reporter", reporter)

    # Add edges
    graph.set_entry_point("introspect_schema")
    graph.add_edge("introspect_schema", "planner")
    graph.add_edge("planner", "sql_agent")

    # Conditional routing after SQL
    graph.add_conditional_edges(
        "sql_agent",
        route_after_sql,
        {
            "sql_error_handler": "sql_error_handler",
            "analyst": "analyst",
            "reporter": "reporter",
        },
    )

    # Error handler routes back through same conditional
    graph.add_conditional_edges(
        "sql_error_handler",
        route_after_sql,
        {
            "sql_error_handler": "sql_error_handler",
            "analyst": "analyst",
            "reporter": "reporter",
        },
    )

    # Linear path from analyst → visualizer → reporter → END
    graph.add_edge("analyst", "visualizer")
    graph.add_edge("visualizer", "reporter")
    graph.add_edge("reporter", END)

    logger.info("Graph built with {} nodes", 7)
    return graph.compile()
