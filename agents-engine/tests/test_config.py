"""
Tests for Settings and Gemini Configuration.
"""

import os
from runtime.config import Settings
from runtime.llm import GeminiClientWrapper


def test_config_defaults():
    settings = Settings()
    assert settings.gemini_model == "gemini-2.0-flash"
    assert settings.environment == "development"
    assert settings.event_bus_max_queue_size == 10000


def test_gemini_client_missing_key_raises_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client_wrapper = GeminiClientWrapper(api_key=None)

    caught = False
    try:
        client_wrapper.get_client()
    except ValueError as exc:
        caught = True
        assert "GEMINI_API_KEY is not set" in str(exc)
    assert caught is True
