"""NVIDIA Build LLM client — OpenAI-compatible /chat/completions endpoint.

`build.nvidia.com` exposes Nemotron, Llama, Mistral and others through an
OpenAI-style REST API. We use `httpx` directly rather than the openai SDK
to keep the dependency surface small and the auth surface explicit.

Graceful degrade: if `NVIDIA_API_KEY` is unset, every call raises
`NemotronNotConfigured` and the service layer catches it and routes the
pipeline through the "no analysis" path.
"""

from __future__ import annotations

import json
import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)


class NemotronNotConfigured(RuntimeError):
    """Raised when NVIDIA_API_KEY is missing — caller should degrade."""


class NemotronError(RuntimeError):
    """Generic upstream failure after retries. Includes the response status."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _client_or_raise() -> httpx.Client:
    if not settings.nvidia_api_key:
        raise NemotronNotConfigured("NVIDIA_API_KEY not set")
    return httpx.Client(
        base_url=settings.nvidia_base_url,
        headers={
            "Authorization": f"Bearer {settings.nvidia_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


@retry(
    retry=retry_if_exception_type((httpx.TransportError, NemotronError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def chat_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    response_format_json: bool = False,
) -> dict:
    """Call the upstream chat/completions endpoint and return the parsed JSON body.

    `response_format_json=True` asks the model to emit JSON (some models honor it,
    others ignore it — the caller must still tolerate a non-JSON string).
    """
    body: dict = {
        "model": settings.nvidia_nemotron_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format_json:
        body["response_format"] = {"type": "json_object"}

    with _client_or_raise() as client:
        try:
            response = client.post("/chat/completions", json=body)
        except httpx.TransportError as e:
            logger.warning("NVIDIA transport error: %s", e)
            raise
        if response.status_code >= 500:
            raise NemotronError(
                f"upstream {response.status_code}: {response.text[:200]}",
                status=response.status_code,
            )
        if response.status_code == 429:
            raise NemotronError("rate limited (429)", status=429)
        if response.status_code >= 400:
            # 4xx other than 429 are not retried — bail loudly.
            raise NemotronError(
                f"upstream {response.status_code}: {response.text[:200]}",
                status=response.status_code,
            )
        return response.json()


def extract_text(completion: dict) -> str:
    """Pull the assistant message text from a chat-completion response."""
    choices = completion.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


def extract_usage(completion: dict) -> dict[str, int]:
    """Pull the token-usage block, defaulting to zeros."""
    usage = completion.get("usage") or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", 0)),
        "completion_tokens": int(usage.get("completion_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
    }


def parse_json_or_none(text: str) -> dict | list | None:
    """Tolerant JSON parser — strips ```json fences before parsing."""
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        # Strip a leading fence + optional language tag, and the trailing fence.
        candidate = candidate.strip("`")
        if "\n" in candidate:
            candidate = candidate.split("\n", 1)[1]
        if candidate.endswith("```"):
            candidate = candidate[:-3]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None
