"""Interactive multi-question REPL session."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from loguru import logger

from src.config.settings import Settings
from src.db.connection import DatabasePool
from src.graph.builder import build_graph
from src.graph.state import AnalystState
from src.observability import configure_observability, create_session_callbacks, flush_callbacks


def main():
    settings = Settings()
    pool = DatabasePool(settings.database)
    pool.open()
    obs_manager = configure_observability(settings)
    graph = build_graph(settings, pool, obs_manager)

    # Single session ID for the entire interactive conversation
    session_id = f"repl-{uuid.uuid4().hex[:12]}"
    callbacks = create_session_callbacks(obs_manager, session_id=session_id)
    config = {"callbacks": callbacks} if callbacks else {}

    print("AI Data Analyst - Interactive Session")
    print(f"Session ID: {session_id}")
    print("Type 'quit' or 'exit' to end the session.\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if question.lower() in ("quit", "exit", "q"):
            break

        if not question:
            continue

        logger.info("Analyzing: {}", question)
        initial_state = AnalystState(question=question)
        result = graph.invoke(initial_state, config=config)
        flush_callbacks(obs_manager)

        print("\n" + "-" * 60)
        print(result.get("report", "No report generated."))
        print("-" * 60 + "\n")

    flush_callbacks(obs_manager)
    pool.close()
    print("Session ended.")


if __name__ == "__main__":
    main()
