"""Provider registry with explicit primary/fallback selection."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..config import AIConfig
from .base import ChatMessage, EmbeddingResult, LLMProvider, LLMResponse
from .ollama import OllamaProvider

log = logging.getLogger(__name__)

_FACTORIES = {
    "ollama": OllamaProvider,
}


class ProviderRegistry:
    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self._instances: dict[str, LLMProvider] = {}
        self._lock = asyncio.Lock()

    async def get(self, name: str | None = None) -> LLMProvider:
        key = name or self.config.provider
        if key == "sovereigneg":
            raise PermissionError("SovereignEG is paused during offline evidence evaluation")
        if key in self._instances:
            return self._instances[key]
        async with self._lock:
            if key in self._instances:
                return self._instances[key]
            if key not in self.config.providers:
                raise KeyError(f"Unknown provider: {key}")
            factory = _FACTORIES.get(key)
            if factory is None:
                raise KeyError(f"No implementation for provider: {key}")
            instance = factory(self.config.providers[key])
            self._instances[key] = instance
            return instance

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        provider: str | None = None,
        use_fallback: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call the primary provider, falling back only on infrastructure errors."""
        primary_name = provider or self.config.provider
        primary = await self.get(primary_name)
        try:
            return await primary.chat(messages, **kwargs)
        except Exception as exc:
            fallback_name = self.config.fallback_provider
            if not use_fallback or not fallback_name or fallback_name == primary_name:
                raise
            log.warning(
                "Provider '%s' failed (%s); trying fallback '%s'",
                primary_name,
                type(exc).__name__,
                fallback_name,
            )
            fallback = await self.get(fallback_name)
            return await fallback.chat(messages, **kwargs)

    async def embed(self, texts: list[str], *, provider: str | None = None) -> EmbeddingResult:
        return await (await self.get(provider)).embed(texts)

    async def usage(self) -> dict[str, dict[str, int]]:
        return {name: p.usage.snapshot() for name, p in self._instances.items()}

    async def close(self) -> None:
        for provider in self._instances.values():
            await provider.close()
        self._instances.clear()


def build_registry(config: AIConfig) -> ProviderRegistry:
    return ProviderRegistry(config)
