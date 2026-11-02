"""Real local inference with typed outputs and serialized GPU use; no simulated fallback."""
import json
import threading
import time
from pathlib import Path

import httpx

INFERENCE_LOCK = threading.RLock()
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config/llm.json"


class OllamaClient:
    def __init__(self, config=None, transport=None):
        self.config = config or json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.client = httpx.Client(base_url=self.config["base_url"], timeout=httpx.Timeout(180, connect=5), transport=transport)
        available = {m["name"] for m in self.client.get("/api/tags").raise_for_status().json()["models"]}
        primary = self.config["model"]
        fallback = self.config["fallback_model"]
        if primary in available:
            self.model = primary
            self.selection_reason = "configured primary is installed"
        elif fallback in available:
            self.model = fallback
            self.selection_reason = f"explicit compute fallback; primary {primary} is not installed"
        else:
            raise RuntimeError(f"Neither authorized local Qwen model is installed: {primary}, {fallback}")

    def chat(self, messages, response_type=None, on_delta=None):
        body = {"model": self.model, "messages": messages, "stream": True,
                "options": {"temperature": 0, "num_ctx": self.config["num_ctx"], "num_predict": self.config["num_predict"]},
                "keep_alive": "15m"}
        if response_type is not None:
            body["format"] = response_type.model_json_schema()
        started = time.monotonic()
        content = ""
        final = None
        with INFERENCE_LOCK:
            with self.client.stream("POST", "/api/chat", json=body) as response:
                response.raise_for_status()
                last_update = 0.0
                for line in response.iter_lines():
                    if not line:
                        continue
                    frame = json.loads(line)
                    if frame.get("error"):
                        raise RuntimeError(frame["error"])
                    content += frame.get("message", {}).get("content", "")
                    if on_delta and time.monotonic() - last_update >= .25:
                        on_delta(content)
                        last_update = time.monotonic()
                    if frame.get("done"):
                        final = frame
                if final is None:
                    raise RuntimeError("Ollama stream ended without a completed response")
        if on_delta:
            on_delta(content)
        parsed = response_type.model_validate_json(content) if response_type else None
        return {"model": final.get("model", self.model), "text": content, "parsed": parsed,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "prompt_tokens": final.get("prompt_eval_count"), "output_tokens": final.get("eval_count"),
                "selection_reason": self.selection_reason}

    def close(self):
        self.client.close()
