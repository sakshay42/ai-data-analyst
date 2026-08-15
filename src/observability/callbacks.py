"""Composite callback manager merging enabled providers."""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


class CompositeCallbackManager:
    """Aggregates multiple callback handlers for LangGraph config propagation."""

    def __init__(self, handlers: list[BaseCallbackHandler] | None = None) -> None:
        self._handlers: list[BaseCallbackHandler] = handlers or []

    def add_handler(self, handler: BaseCallbackHandler) -> None:
        self._handlers.append(handler)

    @property
    def handlers(self) -> list[BaseCallbackHandler]:
        return list(self._handlers)

    def with_metadata(self, node_name: str, run_id: str = "") -> dict[str, Any]:
        """Return LangGraph config dict with callbacks and metadata."""
        metadata: dict[str, Any] = {"node_name": node_name}
        if run_id:
            metadata["run_id"] = run_id
        return {
            "callbacks": self._handlers,
            "metadata": metadata,
        }

    def get_config(self) -> dict[str, Any]:
        """Return config dict suitable for graph.invoke(..., config=...)."""
        return {"callbacks": self._handlers}
