
import os

from dotenv import load_dotenv
from google import genai

from app.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    """Gemini implementation of our LLM provider interface."""

    def __init__(self, model_name: str | None = None):
        load_dotenv()

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing from the environment."
            )

        self.model_name = (
            model_name
            or os.getenv(
                "GEMINI_MODEL",
                "gemini-3.5-flash-lite",
            )
        )

        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt: str) -> str:
        """Generate text using the Gemini API."""

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned no text response."
            )

        return response.text.strip()
