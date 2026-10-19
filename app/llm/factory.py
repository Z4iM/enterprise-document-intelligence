
import os

from dotenv import load_dotenv

from app.llm.base import LLMProvider


def get_llm_provider() -> LLMProvider:
    """Select the configured LLM provider."""

    load_dotenv()

    provider_name = os.getenv(
        "LLM_PROVIDER",
        "http",
    ).strip().lower()

    if provider_name == "gemini":
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider()

    if provider_name in {"http", "qwen"}:
        from app.llm.http_provider import HTTPModelProvider

        return HTTPModelProvider()

    raise ValueError(
        f"Unsupported LLM provider: {provider_name}"
    )
