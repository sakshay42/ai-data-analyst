"""Simple CLI analysis example."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from loguru import logger

from src.config.settings import Settings
from src.db.connection import DatabasePool
from src.graph.builder import build_graph
from src.graph.state import AnalystState
from src.observability import configure_observability, create_session_callbacks, flush_callbacks, get_callbacks


def main():
    parser = argparse.ArgumentParser(description="AI Data Analyst - Simple Analysis")
    parser.add_argument("--question", "-q", required=True, help="Business question to analyze")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory for charts")
    parser.add_argument("--session-id", "-s", default=None, help="Langfuse session ID (auto-generated if omitted)")
    parser.add_argument("--user-id", "-u", default=None, help="Langfuse user ID for tracking")
    args = parser.parse_args()

    settings = Settings()
    settings.output_dir = args.output_dir

    logger.info("Initializing pipeline...")
    pool = DatabasePool(settings.database)
    pool.open()

    obs_manager = configure_observability(settings)
    graph = build_graph(settings, pool, obs_manager)

    logger.info("Running analysis for: {}", args.question)
    initial_state = AnalystState(question=args.question)

    session_id = args.session_id or f"cli-{uuid.uuid4().hex[:12]}"
    callbacks = create_session_callbacks(obs_manager, session_id=session_id, user_id=args.user_id)
    config = {"callbacks": callbacks} if callbacks else {}
    logger.info("Langfuse session_id={}, user_id={}", session_id, args.user_id)

    result = graph.invoke(initial_state, config=config)
    flush_callbacks(obs_manager)

    # Print report
    print("\n" + "=" * 80)
    print("ANALYSIS REPORT")
    print("=" * 80)
    print(result.get("report", "No report generated."))

    # List charts
    charts = result.get("charts", [])
    if charts:
        print("\nGenerated Charts:")
        for c in charts:
            title = c.title if hasattr(c, 'title') else c.get('title', 'Chart')
            path = c.path if hasattr(c, 'path') else c.get('path', '')
            print(f"  - {title}: {path}")

    # Show errors
    errors = result.get("errors", [])
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")

    pool.close()


if __name__ == "__main__":
    main()
