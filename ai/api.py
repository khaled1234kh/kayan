"""Status and compatibility routes for the paused cloud analysis experiment."""

from fastapi import FastAPI, HTTPException

from .config import load_config

_UNAVAILABLE = "The cloud experiment is paused. Evidence comparison is available offline."


def install_ai_api(app: FastAPI) -> None:
    @app.get("/ai/status")
    async def ai_status() -> dict:
        config = load_config(load_env=False)
        return {
            "provider": config.provider,
            "chat_model": config.primary.chat_model,
            "enabled": False,
            "status": "offline_evaluation",
            "reason": _UNAVAILABLE,
        }

    @app.get("/ai/usage")
    async def ai_usage() -> dict:
        return {}

    @app.post("/ai/assess")
    @app.get("/ai/assess/{job_id}")
    @app.post("/ai/mitre/reindex")
    async def ai_unavailable() -> None:
        raise HTTPException(503, _UNAVAILABLE)
