"""Optional chatbot backed by any OpenAI-compatible chat completions API.

Configured with LLM_API_KEY (or the legacy PERPLEXITY_API_KEY), LLM_BASE_URL and
LLM_MODEL. When no key is set the chat endpoint reports that it is not configured.
"""

from __future__ import annotations

from typing import Any

import requests

SYSTEM_PROMPT = "You are a concise assistant for small-scale farmers. Answer practically and briefly."


class ChatNotConfigured(RuntimeError):
    pass


class ChatError(RuntimeError):
    pass


class ChatClient:
    def __init__(self, api_key: str | None, base_url: str, model: str, timeout: float = 20.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def ask(self, message: str) -> str:
        if not self.configured:
            raise ChatNotConfigured("chatbot is not configured")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "max_tokens": 500,
            "temperature": 0.2,
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ChatError(f"chat provider error: {exc.__class__.__name__}") from exc
