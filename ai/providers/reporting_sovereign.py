"""SovereignEG transport restricted to the retrospective Reporting caller."""

import time
from typing import Any

from .base import ChatMessage, LLMResponse
from .sovereign import _SovereignTransport

MODEL = "SovereignEG/Qwen3.8-27B-FP8"
DESTINATION = "https://backend.sovereigneg.com/v1/chat/completions"
OUTPUT_TOKENS = 1024


def request_payload(messages, response_format):
    return {
        "model": MODEL, "messages": [message.as_dict() for message in messages],
        "reasoning_effort": "none", "temperature": 0, "max_tokens": OUTPUT_TOKENS,
        "response_format": response_format,
    }


class ReportingSovereignProvider(_SovereignTransport):
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        if (self.config.chat_model != MODEL or max_tokens != OUTPUT_TOKENS
                or temperature != 0 or response_format is None):
            raise ValueError("Unexpected Reporting configuration")
        payload = request_payload(messages, response_format)
        started = time.monotonic()
        async with self.semaphore:
            await self.rate_limiter.acquire()
            try:
                # Exactly one POST, with no redirects, environment proxies or retries.
                reply = await self._client.post("/chat/completions", json=payload)
                if reply.status_code != 200:
                    raise RuntimeError(f"SovereignEG HTTP {reply.status_code}")
                if (any(field in reply.headers for field in ("x-output-clamped", "x-plan-output-cap"))
                        or any(name in reply.headers.get(field, "").lower()
                               for field in ("x-dropped-params", "x-mapped-params")
                               for name in ("reasoning_effort", "temperature", "max_tokens", "response_format", "model"))):
                    raise ValueError("SovereignEG changed the approved configuration")
                wire = reply.json()
                choice, = wire["choices"]
                usage = wire["usage"]
                reasoning = usage["completion_tokens_details"]["reasoning_tokens"]
                if (wire["model"] != MODEL or choice["finish_reason"] != "stop"
                        or type(reasoning) is not int or reasoning != 0):
                    raise ValueError("Unexpected model, reasoning usage or incomplete response")
                input_tokens = usage["prompt_tokens"]
                output_tokens = usage["completion_tokens"]
                if (type(input_tokens) is not int or input_tokens <= 0
                        or type(output_tokens) is not int or not 0 < output_tokens <= OUTPUT_TOKENS):
                    raise ValueError("Unexpected Reporting token usage")
                content = choice["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("No visible report selection")
                response = LLMResponse(
                    content=content, model=MODEL, provider=self.name, finish_reason="stop",
                    prompt_tokens=input_tokens, completion_tokens=output_tokens,
                    reasoning_tokens=reasoning,
                    latency_s=round(time.monotonic() - started, 3),
                )
            except Exception:
                await self.usage.record_failure()
                raise
        await self.usage.record_chat(response)
        return response

    async def embed(self, texts):
        raise PermissionError("Reporting does not authorize embeddings")

