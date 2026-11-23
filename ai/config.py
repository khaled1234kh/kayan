"""Configuration for the KAYAN AI layer.

Secrets are read from the environment (a local ``.env`` file is loaded for
convenience) and are never stored in ``config/ai.json`` or returned by APIs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "ai.json"
ENV_PATH = PROJECT_ROOT / ".env"


def load_dotenv(path: Path = ENV_PATH) -> None:
    """Minimal .env loader. Existing environment variables always win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    chat_model: str
    embedding_model: str
    max_concurrency: int
    request_timeout_s: float
    max_retries: int = 3
    max_tokens: int = 1024
    temperature: float = 0.0
    api_key_env: str | None = None
    reasoning_effort_tokens: int = 0
    requests_per_minute: int = 0

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None


@dataclass(frozen=True)
class MitreConfig:
    archive_path: Path
    archive_member: str
    version: str
    sha256: str
    source_url: str
    top_k: int = 5
    max_technique_chars: int = 900


@dataclass(frozen=True)
class TrustGateClientConfig:
    base_url: str
    authorize_path: str
    require_authorization: bool
    timeout_s: float


@dataclass(frozen=True)
class AIConfig:
    provider: str
    fallback_provider: str | None
    providers: dict[str, ProviderConfig]
    agent_names: tuple[str, ...]
    max_parallel_agents: int
    agent_retries: int
    mitre: MitreConfig
    trustgate: TrustGateClientConfig
    raw: dict[str, Any] = field(default_factory=dict)

    def get_provider(self, name: str | None = None) -> ProviderConfig:
        key = name or self.provider
        if key not in self.providers:
            raise KeyError(f"Unknown AI provider: {key}")
        return self.providers[key]

    @property
    def primary(self) -> ProviderConfig:
        return self.get_provider(self.provider)


def load_config(path: Path = CONFIG_PATH, *, load_env: bool = True) -> AIConfig:
    if load_env:
        load_dotenv()
    data = json.loads(path.read_text(encoding="utf-8"))

    providers: dict[str, ProviderConfig] = {}
    for name in ("sovereigneg", "ollama"):
        section = data.get(name)
        if not section:
            continue
        providers[name] = ProviderConfig(
            name=name,
            base_url=section["base_url"],
            chat_model=section["chat_model"],
            embedding_model=section.get("embedding_model", ""),
            max_concurrency=int(section.get("max_concurrency", 1)),
            request_timeout_s=float(section.get("request_timeout_s", 120)),
            max_retries=int(section.get("max_retries", 3)),
            max_tokens=int(section.get("max_tokens", 1024)),
            temperature=float(section.get("temperature", 0)),
            api_key_env=section.get("api_key_env"),
            reasoning_effort_tokens=int(section.get("reasoning_effort_tokens", 0)),
            requests_per_minute=int(section.get("requests_per_minute", 0)),
        )

    mitre_data = data["mitre"]
    tg_data = data["trustgate"]
    agents = data["agents"]

    return AIConfig(
        provider=data["provider"],
        fallback_provider=data.get("fallback_provider"),
        providers=providers,
        agent_names=tuple(agents["names"]),
        max_parallel_agents=int(agents.get("max_parallel", 4)),
        agent_retries=int(agents.get("retries", 1)),
        mitre=MitreConfig(
            archive_path=PROJECT_ROOT / mitre_data["enterprise_stix_archive"],
            archive_member=mitre_data["enterprise_stix_member"],
            version=mitre_data["enterprise_stix_version"],
            sha256=mitre_data["enterprise_stix_sha256"],
            source_url=mitre_data["enterprise_stix_source"],
            top_k=int(mitre_data.get("top_k", 5)),
            max_technique_chars=int(mitre_data.get("max_technique_chars", 900)),
        ),
        trustgate=TrustGateClientConfig(
            base_url=tg_data["base_url"],
            authorize_path=tg_data["authorize_path"],
            require_authorization=bool(tg_data.get("require_authorization", True)),
            timeout_s=float(tg_data.get("timeout_s", 8)),
        ),
        raw=data,
    )


def require_api_key(config: ProviderConfig) -> str:
    if not config.api_key:
        raise RuntimeError(
            f"Provider '{config.name}' requires {config.api_key_env} in the "
            "environment or in the local .env file."
        )
    return config.api_key


def require_local_http(base_url: str) -> None:
    endpoint = urlsplit(base_url)
    if (endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "::1"}
            or endpoint.username is not None or endpoint.password is not None
            or endpoint.path not in {"", "/"} or endpoint.query or endpoint.fragment):
        raise PermissionError("Experimental endpoint must be a local loopback HTTP service")
