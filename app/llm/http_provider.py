import os

import requests
from dotenv import load_dotenv

from app.llm.base import LLMProvider


load_dotenv()


class HTTPModelProvider(LLMProvider):

    def __init__(self):
        self.api_url = os.getenv("LLM_API_URL")
        self.api_key = os.getenv("LLM_API_KEY")

        if not self.api_url:
            raise ValueError("LLM_API_URL is missing")

        if not self.api_key:
            raise ValueError("LLM_API_KEY is missing")

    def generate(self, prompt: str) -> str:

        response = requests.post(
            f"{self.api_url}/generate",
            headers={
                "x-api-key": self.api_key
            },
            json={
                "prompt": prompt
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return data["response"]