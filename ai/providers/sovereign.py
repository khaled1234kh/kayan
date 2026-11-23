"""SovereignEG transport for offline experiments and bounded Reporting."""

from __future__ import annotations

import asyncio
import math
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from ..config import ProviderConfig
from .base import ChatMessage, EmbeddingResult, LLMProvider, LLMResponse


def _retry_delay(value: str | None, attempt: int) -> float:
    if value is not None:
        try:
            delay = float(value)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = math.nan
        if math.isfinite(delay):
            return max(0, delay)
    return min(2 ** attempt, 8) + random.uniform(0, 0.2)


class _SovereignTransport(LLMProvider):
    name = "sovereigneg"

    def __init__(self, config: ProviderConfig, *, transport=None, api_key=None) -> None:
        if config.base_url.rstrip("/") != "https://backend.sovereigneg.com/v1":
            raise ValueError("SovereignEG destination is not approved")
        super().__init__(
            max_concurrency=config.max_concurrency,
            requests_per_minute=config.requests_per_minute,
        )
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            trust_env=False,
            transport=transport,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
            timeout=httpx.Timeout(config.request_timeout_s),
            limits=httpx.Limits(
                max_connections=config.max_concurrency,
                max_keepalive_connections=config.max_concurrency,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()


class SovereignEGProvider(_SovereignTransport):
    def __init__(self, config: ProviderConfig, *, transport: httpx.MockTransport | None = None) -> None:
        if config.base_url.rstrip("/") != "https://backend.sovereigneg.com/v1":
            raise ValueError("SovereignEG destination is not approved")
        if not isinstance(transport, httpx.MockTransport):
            raise PermissionError("SovereignEG is paused during offline evidence evaluation")
        super().__init__(config, transport=transport)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = max(1, self.config.max_retries)
        for attempt in range(attempts):
            await self.rate_limiter.acquire()
            try:
                response = await self._client.post(path, json=payload)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                error = "connection failed"
                delay = min(2 ** attempt, 8) + random.uniform(0, 0.2)
            except httpx.HTTPError:
                raise RuntimeError("SovereignEG request outcome is unknown") from None
            else:
                if response.is_success:
                    return response.json()
                error = f"HTTP {response.status_code}"
                if response.status_code != 429:
                    raise RuntimeError(f"SovereignEG request rejected: {error}")
                delay = _retry_delay(response.headers.get("Retry-After"), attempt)
            if attempt + 1 == attempts or delay > 30:
                raise RuntimeError(f"SovereignEG request unavailable: {error}")
            await asyncio.sleep(delay)
        raise AssertionError("Provider retry loop did not terminate")

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.config.chat_model,
            "messages": [m.as_dict() for m in messages],
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": self.config.temperature
            if temperature is None
            else temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        started = time.monotonic()
        async with self.semaphore:
            try:
                data = await self._post("/chat/completions", payload)
            except Exception:
                await self.usage.record_failure()
                raise
        latency = time.monotonic() - started

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}

        response = LLMResponse(
            content=str(message.get("content") or ""),
            reasoning=str(message.get("reasoning_content") or ""),
            model=str(data.get("model") or self.config.chat_model),
            provider=self.name,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            reasoning_tokens=int(details.get("reasoning_tokens") or 0),
            finish_reason=str(choice.get("finish_reason") or ""),
            latency_s=round(latency, 3),
        )
        await self.usage.record_chat(response)
        return response

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], model=self.config.embedding_model, provider=self.name)
        if not self.config.embedding_model:
            raise RuntimeError("No embedding model configured for SovereignEG")

        payload = {"model": self.config.embedding_model, "input": texts}
        async with self.semaphore:
            try:
                data = await self._post("/embeddings", payload)
            except Exception:
                await self.usage.record_failure()
                raise

        rows = sorted(data.get("data") or [], key=lambda row: row.get("index", 0))
        vectors = [[float(v) for v in row["embedding"]] for row in rows]
        if len(vectors) != len(texts):
            raise RuntimeError("SovereignEG returned an unexpected embedding count")

        result = EmbeddingResult(
            vectors=vectors,
            model=str(data.get("model") or self.config.embedding_model),
            provider=self.name,
            prompt_tokens=int((data.get("usage") or {}).get("prompt_tokens") or 0),
        )
        await self.usage.record_embedding(result)
        return result

