"""Local Ollama provider â€” retained as the baseline/fallback model."""

from __future__ import annotations

import time
from typing import Any

import httpx

from ..config import ProviderConfig, require_local_http
from .base import ChatMessage, EmbeddingResult, LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, config: ProviderConfig) -> None:
        require_local_http(config.base_url)
        super().__init__(max_concurrency=config.max_concurrency)
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            trust_env=False,
            timeout=httpx.Timeout(config.request_timeout_s),
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload = {
            "model": self.config.chat_model,
            "messages": [m.as_dict() for m in messages],
            "stream": False,
            "options": {
                "num_predict": max_tokens or self.config.max_tokens,
                "temperature": self.config.temperature
                if temperature is None
                else temperature,
            },
        }
        if response_format and response_format.get("type") == "json_object":
            payload["format"] = "json"
        elif response_format and response_format.get("type") == "json_schema":
            payload["format"] = response_format["json_schema"]["schema"]
        started = time.monotonic()
        async with self.semaphore:
            try:
                response = await self._client.post("/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
            except Exception:
                await self.usage.record_failure()
                raise
        latency = time.monotonic() - started

        result = LLMResponse(
            content=str((data.get("message") or {}).get("content") or ""),
            model=str(data.get("model") or self.config.chat_model),
            provider=self.name,
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
            finish_reason=str(data.get("done_reason") or ""),
            latency_s=round(latency, 3),
        )
        await self.usage.record_chat(result)
        return result

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[], model=self.config.embedding_model, provider=self.name
            )
        async with self.semaphore:
            response = await self._client.post(
                "/api/embed",
                json={"model": self.config.embedding_model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
        result = EmbeddingResult(
            vectors=[[float(v) for v in row] for row in data["embeddings"]],
            model=str(data.get("model") or self.config.embedding_model),
            provider=self.name,
        )
        await self.usage.record_embedding(result)
        return result

    async def close(self) -> None:
        await self._client.aclose()
