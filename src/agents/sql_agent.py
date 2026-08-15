"""SQL Agent: generates and executes SQL from the analysis plan."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from loguru import logger

from src.db.connection import DatabasePool
from src.graph.state import AnalystState, QueryResult

SQL_AGENT_SYSTEM_PROMPT = """You are a SQL expert. Given a database schema and an analysis plan, generate a single SQL query that answers the user's question.

Rules:
- Only generate SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
- Use standard PostgreSQL syntax
- Include appropriate JOINs, GROUP BY, ORDER BY as needed
- Use aliases for readability
- Limit results to a reasonable number unless aggregating
- Output ONLY the SQL query, no explanation or markdown formatting"""


def create_sql_agent_node(llm: ChatOpenAI, pool: DatabasePool):
    """Create an SQL agent node bound to an LLM and database pool."""

    def sql_agent_node(state: AnalystState, config: RunnableConfig | None = None) -> dict[str, Any]:
        """Generate SQL from the plan and execute it."""
        plan = state.plan
        messages = [
            SystemMessage(content=SQL_AGENT_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Database Schema:\n{state.schema_summary}\n\n"
                f"Question: {plan.question}\n"
                f"Sub-questions: {plan.sub_questions}\n"
                f"Required tables: {plan.required_tables}\n"
                f"Analysis type: {plan.analysis_type}"
            ),
        ]
        response = llm.invoke(messages, config=config)
        sql = response.content.strip().strip("```sql").strip("```").strip()
        logger.info("Generated SQL: {}", sql[:200])

        # Execute
        try:
            rows, columns = pool.execute_query(sql)
            return {
                "query_result": QueryResult(
                    sql=sql,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                )
            }
        except Exception as e:
            logger.error("SQL execution failed: {}", e)
            return {
                "query_result": QueryResult(sql=sql, error=str(e)),
                "errors": [f"SQL error: {e}"],
            }

    return sql_agent_node


def create_sql_error_handler_node(llm: ChatOpenAI, pool: DatabasePool):
    """Create an error handler that retries SQL generation with error context."""

    def sql_error_handler_node(state: AnalystState, config: RunnableConfig | None = None) -> dict[str, Any]:
        """Retry SQL generation with error feedback."""
        retry_count = state.sql_retry_count + 1
        logger.warning("SQL retry attempt {}/2", retry_count)

        messages = [
            SystemMessage(content=SQL_AGENT_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Database Schema:\n{state.schema_summary}\n\n"
                f"Question: {state.plan.question}\n"
                f"Previous SQL that failed:\n{state.query_result.sql}\n"
                f"Error: {state.query_result.error}\n\n"
                f"Please fix the SQL query. Output ONLY the corrected SQL."
            ),
        ]
        response = llm.invoke(messages, config=config)
        sql = response.content.strip().strip("```sql").strip("```").strip()

        try:
            rows, columns = pool.execute_query(sql)
            return {
                "query_result": QueryResult(
                    sql=sql,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                ),
                "sql_retry_count": retry_count,
            }
        except Exception as e:
            return {
                "query_result": QueryResult(sql=sql, error=str(e)),
                "sql_retry_count": retry_count,
                "errors": [f"SQL retry {retry_count} error: {e}"],
            }

    return sql_error_handler_node
