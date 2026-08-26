"""
Gemini Client & Google ADK Integration for AEGIS Ω.
Ensures secure, dynamic initialization of Gemini LLM instances without hardcoding secrets.
"""

import os
import logging
from typing import Any, Optional
from .config import get_settings

logger = logging.getLogger(__name__)


class GeminiClientWrapper:
    """
    Wrapper for Google GenAI / Gemini API client.
    Enforces security by retrieving keys exclusively from environment/settings.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self._api_key = api_key or (settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None)
        self.model_name = model or settings.gemini_model
        self._client: Optional[Any] = None

    @property
    def is_configured(self) -> bool:
        """Check if GEMINI_API_KEY is available."""
        return bool(self._api_key)

    def get_client(self) -> Any:
        """
        Initialize and return the Google GenAI client.
        Raises ValueError if GEMINI_API_KEY is not configured.
        """
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please provide it via the GEMINI_API_KEY "
                "environment variable or .env file. Never hardcode API keys in code."
            )

        if self._client is None:
            import importlib
            try:
                # Attempt initialization using modern google.genai SDK
                genai = importlib.import_module("google.genai")
                self._client = genai.Client(api_key=self._api_key)
                logger.info(f"Initialized Google GenAI client for model: {self.model_name}")
            except (ImportError, ModuleNotFoundError):
                # Fallback to google.generativeai if google-genai is not installed
                try:
                    gai = importlib.import_module("google.generativeai")
                    gai.configure(api_key=self._api_key)
                    self._client = gai
                    logger.info(f"Initialized Google GenerativeAI fallback for model: {self.model_name}")
                except (ImportError, ModuleNotFoundError):
                    raise ImportError(
                        "Neither 'google-genai' nor 'google-generativeai' package is installed. "
                        "Please run `pip install -r requirements.txt`."
                    )

        return self._client


_gemini_wrapper_singleton: Optional[GeminiClientWrapper] = None


def get_gemini_client() -> GeminiClientWrapper:
    """Retrieve singleton instance of the Gemini client wrapper."""
    global _gemini_wrapper_singleton
    if _gemini_wrapper_singleton is None:
        _gemini_wrapper_singleton = GeminiClientWrapper()
    return _gemini_wrapper_singleton
