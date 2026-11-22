"""Pinned local model transport for read-only Archived Reporting selections."""

from hashlib import sha256
import json
from time import monotonic

import httpx

from .base import LLMResponse

BASE_URL = "http://127.0.0.1:11534"
DESTINATION = f"{BASE_URL}/api/chat"
MODEL = "qwen2.5:7b"
MODEL_DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
OUTPUT_TOKENS = 192
CONTEXT_TOKENS = 4096
REQUEST_BYTES = 3072
RESPONSE_BYTES = 65536
TIMEOUT_SECONDS = 60


def selection_request(messages, response_format):
    verified = json.loads(messages[1].content)
    prompt = {name: verified[name] for name in ("admitted", "defensive_controls")}
    body = json.dumps({
        "model": MODEL,
        "messages": [
            messages[0].as_dict(),
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=True, separators=(",", ":"))},
        ],
        "format": response_format["json_schema"]["schema"],
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": 0, "seed": 19, "num_ctx": CONTEXT_TOKENS, "num_predict": OUTPUT_TOKENS},
    }, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(body) > REQUEST_BYTES:
        return None
    return body, sha256(DESTINATION.encode("ascii") + b"\0" + body).hexdigest()


async def _read_json(client, method, path, **options):
    async with client.stream(method, path, **options) as response:
        response.raise_for_status()
        raw = bytearray()
        async for piece in response.aiter_bytes():
            if len(raw) + len(piece) > RESPONSE_BYTES:
                raise ValueError("Local Reporting response exceeds its byte limit")
            raw.extend(piece)
    return json.loads(raw)


async def rank_verified(body, *, before_generate, transport=None):
    if not 0 < len(body) <= REQUEST_BYTES:
        raise ValueError("Local Reporting request exceeds its byte limit")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT_SECONDS, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        metadata = await _read_json(client, "GET", "/api/tags")
        matches = [row for row in metadata["models"] if row.get("name") == MODEL]
        if (len(matches) != 1 or matches[0].get("digest") != MODEL_DIGEST
                or matches[0].get("details", {}).get("quantization_level") != "Q4_K_M"):
            raise ValueError("Local Reporting model identity does not match the pin")
        before_generate()
        started = monotonic()
        wire = await _read_json(client, "POST", "/api/chat", content=body,
                                headers={"Content-Type": "application/json"})
        elapsed = round(monotonic() - started, 3)
    message = wire["message"]
    text = message["content"]
    input_tokens, output_tokens = wire["prompt_eval_count"], wire["eval_count"]
    if (wire.get("model") != MODEL or wire.get("done") is not True or wire.get("done_reason") != "stop"
            or message.get("role") != "assistant" or not isinstance(text, str) or not text.strip()
            or type(input_tokens) is not int or not 0 < input_tokens <= CONTEXT_TOKENS - OUTPUT_TOKENS
            or type(output_tokens) is not int or not 0 < output_tokens <= OUTPUT_TOKENS):
        raise ValueError("Invalid local Reporting response, model identity or token counts")
    return LLMResponse(content=text, model=MODEL, provider="ollama", finish_reason="stop",
                       prompt_tokens=input_tokens, completion_tokens=output_tokens, latency_s=elapsed)
