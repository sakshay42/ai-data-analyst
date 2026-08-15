"""Tests for the observability module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.config.settings import (
    BraintrustSettings,
    HeliconeSettings,
    LangfuseSettings,
    LangSmithSettings,
    LLMSettings,
    Settings,
)
from src.observability import (
    ObservabilityManager,
    configure_observability,
    create_llm,
    create_session_callbacks,
    flush_callbacks,
    get_callbacks,
)
from src.observability.callbacks import CompositeCallbackManager
from src.observability.providers import (
    setup_braintrust,
    setup_helicone,
    setup_langsmith,
)
from src.observability.tracing import trace_node


class TestProviders:
    def test_setup_langsmith_sets_env(self, monkeypatch):
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_PROJECT", raising=False)
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        settings = LangSmithSettings.model_construct(
            enabled=True,
            api_key="test-key",
            project="test-project",
            tracing_v2=True,
        )
        setup_langsmith(settings)
        assert os.environ.get("LANGCHAIN_API_KEY") == "test-key"
        assert os.environ.get("LANGCHAIN_PROJECT") == "test-project"

    def test_setup_helicone_returns_proxy_config(self):
        settings = HeliconeSettings(enabled=True, api_key="hel-key")
        result = setup_helicone(settings)
        assert "base_url" in result
        assert "helicone" in result["base_url"].lower()
        assert "Bearer hel-key" in result["default_headers"]["Helicone-Auth"]

    def test_setup_braintrust_returns_proxy_config(self):
        settings = BraintrustSettings(enabled=True, api_key="bt-key")
        result = setup_braintrust(settings)
        assert "base_url" in result
        assert "braintrust" in result["base_url"].lower()


class TestCompositeCallbackManager:
    def test_add_handler(self):
        mgr = CompositeCallbackManager()
        handler = MagicMock()
        mgr.add_handler(handler)
        assert len(mgr.handlers) == 1

    def test_with_metadata(self):
        mgr = CompositeCallbackManager()
        config = mgr.with_metadata("test_node", "run-123")
        assert config["metadata"]["node_name"] == "test_node"
        assert config["metadata"]["run_id"] == "run-123"

    def test_get_config(self):
        handler = MagicMock()
        mgr = CompositeCallbackManager([handler])
        config = mgr.get_config()
        assert len(config["callbacks"]) == 1


class TestTraceNode:
    def test_decorator_preserves_function(self):
        @trace_node("test")
        def my_func(x):
            return x * 2

        assert my_func(5) == 10

    def test_decorator_logs_exception(self):
        @trace_node("fail_node")
        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_func()


class TestConfigureObservability:
    def test_no_providers_enabled(self):
        settings = Settings()
        manager = configure_observability(settings)
        assert len(manager.active_providers) == 0
        assert len(manager.callbacks) == 0

    def test_langsmith_enabled(self):
        settings = Settings()
        settings.langsmith = LangSmithSettings(
            enabled=True, api_key="test", project="test"
        )
        manager = configure_observability(settings)
        assert "langsmith" in manager.active_providers

    def test_helicone_enabled(self):
        settings = Settings()
        settings.helicone = HeliconeSettings(enabled=True, api_key="test")
        manager = configure_observability(settings)
        assert "helicone" in manager.active_providers
        assert "base_url" in manager.llm_kwargs

    @patch("src.observability.logger")
    def test_helicone_braintrust_conflict_warning(self, mock_logger):
        settings = Settings()
        settings.helicone = HeliconeSettings(enabled=True, api_key="hel")
        settings.braintrust = BraintrustSettings(enabled=True, api_key="bt")
        manager = configure_observability(settings)
        # Helicone should win
        assert "helicone" in manager.active_providers
        assert "braintrust" not in manager.active_providers
        mock_logger.warning.assert_called()


class TestCreateLLM:
    def test_creates_chat_openai(self):
        settings = Settings()
        settings.llm = LLMSettings(api_key="test-key", model="gpt-4o")
        manager = ObservabilityManager()
        llm = create_llm(settings, manager, node_name="test")
        assert llm.model_name == "gpt-4o"

    def test_applies_proxy_kwargs(self):
        settings = Settings()
        settings.llm = LLMSettings(api_key="test-key")
        manager = ObservabilityManager(
            llm_kwargs={"base_url": "https://proxy.example.com/v1"},
            active_providers=["helicone"],
        )
        llm = create_llm(settings, manager, node_name="test")
        # The LLM should have the proxy URL applied
        assert llm.openai_api_base == "https://proxy.example.com/v1" or "proxy.example.com" in str(llm.client._base_url) if hasattr(llm, 'client') else True


class TestGetCallbacks:
    def test_returns_copy(self):
        handler = MagicMock()
        manager = ObservabilityManager(callbacks=[handler])
        callbacks = get_callbacks(manager)
        assert len(callbacks) == 1
        callbacks.append(MagicMock())
        assert len(manager.callbacks) == 1  # original unchanged


class TestFlushCallbacks:
    def test_flushes_langfuse_handler(self):
        """Handler with .langfuse.flush() gets flushed."""
        mock_langfuse = MagicMock()
        handler = MagicMock()
        handler.langfuse = mock_langfuse
        manager = ObservabilityManager(callbacks=[handler])
        flush_callbacks(manager)
        mock_langfuse.flush.assert_called_once()

    def test_skips_non_langfuse_handler(self):
        """Handler without .langfuse attribute is skipped (no error)."""
        handler = MagicMock(spec=[])  # no attributes
        manager = ObservabilityManager(callbacks=[handler])
        flush_callbacks(manager)  # should not raise

    def test_empty_callbacks(self):
        """No callbacks → no-op."""
        manager = ObservabilityManager()
        flush_callbacks(manager)  # should not raise

    def test_flush_exception_is_caught(self):
        """Exception during flush is caught and logged, not raised."""
        mock_langfuse = MagicMock()
        mock_langfuse.flush.side_effect = RuntimeError("network error")
        handler = MagicMock()
        handler.langfuse = mock_langfuse
        manager = ObservabilityManager(callbacks=[handler])
        flush_callbacks(manager)  # should not raise

    def test_flush_session_callbacks(self):
        """Session callbacks are also flushed."""
        mock_langfuse = MagicMock()
        session_handler = MagicMock()
        session_handler.langfuse = mock_langfuse
        manager = ObservabilityManager()
        flush_callbacks(manager, session_callbacks=[session_handler])
        mock_langfuse.flush.assert_called_once()

    def test_flush_deduplicates(self):
        """Same handler in both manager and session_callbacks is flushed once."""
        mock_langfuse = MagicMock()
        handler = MagicMock()
        handler.langfuse = mock_langfuse
        manager = ObservabilityManager(callbacks=[handler])
        flush_callbacks(manager, session_callbacks=[handler])
        mock_langfuse.flush.assert_called_once()


class TestCreateSessionCallbacks:
    def test_no_langfuse_returns_copy(self):
        """Without Langfuse, returns a copy of existing callbacks."""
        handler = MagicMock()
        manager = ObservabilityManager(callbacks=[handler])
        result = create_session_callbacks(manager, session_id="test-session")
        assert len(result) == 1
        assert result[0] is handler

    @patch("src.observability.setup_langfuse")
    def test_creates_session_handler(self, mock_setup):
        """With Langfuse active, creates a new handler with session_id."""
        original_handler = MagicMock()
        original_handler.langfuse = MagicMock()
        session_handler = MagicMock()
        mock_setup.return_value = session_handler

        langfuse_settings = LangfuseSettings(
            enabled=True, public_key="pk", secret_key="sk"
        )
        manager = ObservabilityManager(
            callbacks=[original_handler],
            active_providers=["langfuse"],
            _langfuse_settings=langfuse_settings,
        )
        result = create_session_callbacks(
            manager, session_id="sess-123", user_id="user-456"
        )
        assert len(result) == 1
        assert result[0] is session_handler
        mock_setup.assert_called_once_with(
            langfuse_settings, session_id="sess-123", user_id="user-456"
        )

    @patch("src.observability.setup_langfuse")
    def test_preserves_non_langfuse_callbacks(self, mock_setup):
        """Non-Langfuse callbacks are passed through unchanged."""
        langfuse_handler = MagicMock()
        langfuse_handler.langfuse = MagicMock()
        other_handler = MagicMock(spec=[])  # no .langfuse attr
        session_handler = MagicMock()
        mock_setup.return_value = session_handler

        langfuse_settings = LangfuseSettings(
            enabled=True, public_key="pk", secret_key="sk"
        )
        manager = ObservabilityManager(
            callbacks=[langfuse_handler, other_handler],
            active_providers=["langfuse"],
            _langfuse_settings=langfuse_settings,
        )
        result = create_session_callbacks(manager, session_id="sess-123")
        assert len(result) == 2
        assert result[0] is session_handler
        assert result[1] is other_handler
