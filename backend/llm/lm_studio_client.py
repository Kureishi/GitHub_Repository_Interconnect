"""
LM Studio client — async streaming wrapper for the OpenAI-compatible local API.
LM Studio exposes: POST /v1/chat/completions (with stream=True support)
                   GET  /v1/models
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_LM_STUDIO_URL = "http://localhost:1234"
DEFAULT_TIMEOUT = 120.0  # LLMs can be slow locally


class LMStudioClient:
    def __init__(self, base_url: str = DEFAULT_LM_STUDIO_URL):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._client.aclose()

    async def aclose(self):
        await self._client.aclose()

    # -------------------------------------------------------------------------
    # Health check / model listing
    # -------------------------------------------------------------------------

    async def list_models(self) -> list[dict]:
        """Return list of loaded models from LM Studio."""
        try:
            resp = await self._client.get(
                f"{self.base_url}/v1/models",
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            raise ConnectionError(
                f"Cannot reach LM Studio at {self.base_url}. "
                f"Make sure LM Studio is running and the server is started. ({e})"
            )

    async def health_check(self) -> dict:
        """Check connectivity and return available models."""
        models = await self.list_models()
        return {
            "ok": True,
            "base_url": self.base_url,
            "models": [m.get("id", m.get("name", "unknown")) for m in models],
        }

    # -------------------------------------------------------------------------
    # Streaming chat completion
    # -------------------------------------------------------------------------

    async def stream_chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion from LM Studio.
        Yields text content deltas as they arrive.
        If model is None, uses the first available loaded model.
        """
        if model is None:
            models = await self.list_models()
            if not models:
                raise RuntimeError("No models loaded in LM Studio. Please load a model first.")
            model = models[0].get("id", models[0].get("name", "local-model"))

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def complete_chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """
        Non-streaming chat completion — collects and returns the full response text.
        """
        chunks: list[str] = []
        async for chunk in self.stream_chat(messages, model, temperature, max_tokens):
            chunks.append(chunk)
        return "".join(chunks)
