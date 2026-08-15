"""Node-level tracing decorator for LangGraph nodes."""

from __future__ import annotations

import functools
import time
from typing import Any, Callable

from loguru import logger


def trace_node(node_name: str) -> Callable:
    """Decorator that logs timing and metrics for a graph node.

    Usage:
        @trace_node("planner")
        def planner_node(state, config):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("[{}] Starting node execution", node_name)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info("[{}] Completed in {:.2f}s", node_name, elapsed)
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error("[{}] Failed after {:.2f}s: {}", node_name, elapsed, e)
                raise

        return wrapper

    return decorator
