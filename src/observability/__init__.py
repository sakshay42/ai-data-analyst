"""Observability module: LangSmith, Langfuse, Helicone, Braintrust integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from loguru import logger

from src.config.settings import Settings
from src.observability.callbacks import CompositeCallbackManager
from src.observability.providers import (
    setup_braintrust,
    setup_helicone,
    setup_langfuse,
    setup_langsmith,
)
from src.observability.tracing import trace_node


@dataclass
class ObservabilityManager:
    """Holds all provider state for observability."""

    callbacks: list[BaseCallbackHandler] = field(default_factory=list)
    llm_kwargs: dict[str, Any] = field(default_factory=dict)
    active_providers: list[str] = field(default_factory=list)
    _langfuse_settings: Any = field(default=None, repr=False)


def configure_observability(settings: Settings) -> ObservabilityManager:
    """Initialize all enabled observability providers and return manager."""
    manager = ObservabilityManager()

    # LangSmith (env-var based, no callbacks needed)
    if settings.langsmith.enabled:
        setup_langsmith(settings.langsmith)
        manager.active_providers.append("langsmith")
        logger.info("LangSmith tracing enabled")

    # Langfuse (callback-based)
    if settings.langfuse.enabled:
        handler = setup_langfuse(settings.langfuse)
        if handler:
            manager.callbacks.append(handler)
            manager.active_providers.append("langfuse")
            manager._langfuse_settings = settings.langfuse
            logger.info("Langfuse tracing enabled")

    # Helicone (proxy-based)
    if settings.helicone.enabled:
        helicone_kwargs = setup_helicone(settings.helicone)
        manager.llm_kwargs.update(helicone_kwargs)
        manager.active_providers.append("helicone")
        logger.info("Helicone proxy enabled")

    # Braintrust (proxy-based — conflicts with Helicone at runtime)
    if settings.braintrust.enabled:
        if settings.helicone.enabled:
            logger.warning(
                "Both Helicone and Braintrust are enabled. "
                "Helicone wins for runtime proxy; Braintrust available for evals only."
            )
        else:
            bt_kwargs = setup_braintrust(settings.braintrust)
            manager.llm_kwargs.update(bt_kwargs)
            manager.active_providers.append("braintrust")
            logger.info("Braintrust proxy enabled")

    logger.info("Active observability providers: {}", manager.active_providers)
    return manager


def create_llm(settings: Settings, manager: ObservabilityManager, node_name: str = "") -> ChatOpenAI:
    """Create a ChatOpenAI instance with observability baked in."""
    kwargs: dict[str, Any] = {
        "model": settings.llm.model,
        "temperature": settings.llm.temperature,
        "max_tokens": settings.llm.max_tokens,
        "api_key": settings.llm.api_key,
        "request_timeout": settings.llm.request_timeout,
    }
    # Apply proxy kwargs (Helicone or Braintrust)
    kwargs.update(manager.llm_kwargs)

    # Add Helicone session headers if applicable
    if "helicone" in manager.active_providers and node_name:
        headers = kwargs.get("default_headers", {})
        headers["Helicone-Session-Name"] = node_name
        kwargs["default_headers"] = headers

    return ChatOpenAI(**kwargs)


def get_callbacks(manager: ObservabilityManager) -> list[BaseCallbackHandler]:
    """Return list of callback handlers for graph invocation."""
    return list(manager.callbacks)


def create_session_callbacks(
    manager: ObservabilityManager,
    session_id: str,
    user_id: str | None = None,
) -> list[BaseCallbackHandler]:
    """Create per-invocation callbacks with Langfuse session and user tracking.

    Returns a fresh list of callback handlers with session_id/user_id set
    on the Langfuse handler. Non-Langfuse callbacks are included as-is.
    """
    if "langfuse" not in manager.active_providers or manager._langfuse_settings is None:
        return list(manager.callbacks)

    callbacks: list[BaseCallbackHandler] = []
    for cb in manager.callbacks:
        # Replace the Langfuse handler with a session-aware one
        if hasattr(cb, "langfuse"):
            session_handler = setup_langfuse(
                manager._langfuse_settings,
                session_id=session_id,
                user_id=user_id,
            )
            if session_handler:
                callbacks.append(session_handler)
                logger.debug(
                    "Created Langfuse session handler: session_id={}, user_id={}",
                    session_id,
                    user_id,
                )
            else:
                callbacks.append(cb)
        else:
            callbacks.append(cb)
    return callbacks


def flush_callbacks(
    manager: ObservabilityManager,
    session_callbacks: list[BaseCallbackHandler] | None = None,
) -> None:
    """Flush all callback handlers that support it (e.g. Langfuse).

    Args:
        manager: The observability manager with base callbacks.
        session_callbacks: Optional per-invocation session callbacks to flush.
    """
    all_callbacks = list(manager.callbacks)
    if session_callbacks:
        all_callbacks.extend(session_callbacks)

    seen_ids: set[int] = set()
    for cb in all_callbacks:
        cb_id = id(cb)
        if cb_id in seen_ids:
            continue
        seen_ids.add(cb_id)
        langfuse_client = getattr(cb, "langfuse", None)
        if langfuse_client is not None and callable(getattr(langfuse_client, "flush", None)):
            try:
                langfuse_client.flush()
                logger.debug("Flushed Langfuse callback handler")
            except Exception as e:
                logger.warning("Failed to flush Langfuse handler: {}", e)


__all__ = [
    "ObservabilityManager",
    "configure_observability",
    "create_llm",
    "create_session_callbacks",
    "flush_callbacks",
    "get_callbacks",
    "trace_node",
]
