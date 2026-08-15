"""Per-provider setup for observability integrations."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from loguru import logger

from src.config.settings import (
    BraintrustSettings,
    HeliconeSettings,
    LangfuseSettings,
    LangSmithSettings,
)


def setup_langsmith(settings: LangSmithSettings) -> None:
    """Configure LangSmith via environment variables."""
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.tracing_v2).lower()
    os.environ["LANGCHAIN_API_KEY"] = settings.api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.project


def setup_langfuse(
    settings: LangfuseSettings,
    session_id: str | None = None,
    user_id: str | None = None,
) -> BaseCallbackHandler | None:
    """Create and return a Langfuse callback handler.

    Args:
        settings: Langfuse connection settings.
        session_id: Optional session ID for grouping traces into a session.
        user_id: Optional user ID for per-user tracking and cost attribution.
    """
    try:
        from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

        kwargs: dict[str, Any] = {
            "public_key": settings.public_key,
            "secret_key": settings.secret_key,
            "host": settings.host,
        }
        if session_id:
            kwargs["session_id"] = session_id
        if user_id:
            kwargs["user_id"] = user_id

        handler = LangfuseCallbackHandler(**kwargs)
        return handler
    except ImportError:
        logger.warning("langfuse package not installed — skipping Langfuse setup")
        return None
    except Exception as e:
        logger.error("Failed to initialize Langfuse: {}", e)
        return None


def setup_helicone(settings: HeliconeSettings) -> dict[str, Any]:
    """Return ChatOpenAI kwargs for Helicone proxy."""
    return {
        "base_url": "https://oai.helicone.ai/v1",
        "default_headers": {
            "Helicone-Auth": f"Bearer {settings.api_key}",
        },
    }


def setup_braintrust(settings: BraintrustSettings) -> dict[str, Any]:
    """Return ChatOpenAI kwargs for Braintrust proxy."""
    return {
        "base_url": "https://api.braintrust.dev/v1/proxy",
        "default_headers": {
            "Authorization": f"Bearer {settings.api_key}",
        },
    }
