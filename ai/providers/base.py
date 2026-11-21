"""Provider-neutral types and interface for LLM inference."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatMessage:
    role: str  # system | user | assistant
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider: str
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    finish_reason: str = ""
    latency_s: float = 0.0
    attempts: int = 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    provider: str
    prompt_tokens: int = 0


@dataclass
class UsageStats:
    """Bounded in-memory accounting so experiments can measure allowance use."""

    requests: int = 0
    failed_requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    embedding_tokens: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def record_chat(self, response: LLMResponse) -> None:
        async with self.lock:
            self.requests += 1
            self.prompt_tokens += response.prompt_tokens
            self.completion_tokens += response.completion_tokens
            self.reasoning_tokens += response.reasoning_tokens

    async def record_failure(self) -> None:
        async with self.lock:
            self.failed_requests += 1

    async def record_embedding(self, result: EmbeddingResult) -> None:
        async with self.lock:
            self.embedding_tokens += result.prompt_tokens

    def snapshot(self) -> dict[str, int]:
        return {
            "requests": self.requests,
            "failed_requests": self.failed_requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "embedding_tokens": self.embedding_tokens,
        }


class RateLimiter:
    """Async sliding-window limiter (e.g. 20 requests per 60 seconds).

    ``max_calls <= 0`` disables limiting, which keeps local Ollama and unit
    tests unaffected.
    """

    def __init__(self, max_calls: int, period_s: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period_s = period_s
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self.max_calls <= 0:
            return
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period_s:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                wait = self.period_s - (now - self._calls[0]) + 0.01
            await asyncio.sleep(max(wait, 0.0))


class LLMProvider(ABC):
    """Minimal inference interface used by all KAYAN agents."""

    name: str

    def __init__(
        self, *, max_concurrency: int, requests_per_minute: int = 0
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.rate_limiter = RateLimiter(requests_per_minute)
        self.usage = UsageStats()

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        ...

    async def close(self) -> None:
        return None
