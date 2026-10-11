"""Agent profile parity with the frontend.

The backend seed must not drift from ``kayan-3d/src/agents/agentProfiles.ts``.
The frontend is untouched; this test parses it read-only and asserts the ids,
names, roles, kinds, capabilities and restrictions match.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agents import AGENT_SEEDS

PROFILE_PATH = (
    Path(__file__).resolve().parents[2] / "kayan-3d" / "src" / "agents" / "agentProfiles.ts"
)


def _parse_frontend_profiles(source: str) -> dict[str, dict]:
    """Extract each profile object from the TypeScript source without a TS parser."""
    profiles: dict[str, dict] = {}
    for match in re.finditer(
        r"\{\s*id:\s*'(?P<id>[^']+)'(?P<body>.*?)\n  \}", source, re.DOTALL
    ):
        body = match.group("body")

        def field(name: str) -> str | None:
            found = re.search(rf"{name}:\s*'([^']*)'", body)
            return found.group(1) if found else None

        def string_list(name: str) -> list[str]:
            found = re.search(rf"{name}:\s*\[(.*?)\]", body, re.DOTALL)
            if not found:
                return []
            return re.findall(r"'([^']*)'", found.group(1))

        profiles[match.group("id")] = {
            "name": field("name"),
            "role": field("role"),
            "kind": field("kind"),
            "objective": field("objective"),
            "capabilities": string_list("capabilities"),
            "restrictions": string_list("restrictions"),
        }
    return profiles


@pytest.fixture(scope="module")
def frontend_profiles() -> dict[str, dict]:
    if not PROFILE_PATH.exists():
        pytest.skip("frontend profile file not present")
    return _parse_frontend_profiles(PROFILE_PATH.read_text(encoding="utf-8"))


def test_frontend_defines_the_same_five_seats(frontend_profiles):
    assert set(frontend_profiles) == {seed.id for seed in AGENT_SEEDS}


def test_agent_ids_match_frontend(frontend_profiles):
    for seed in AGENT_SEEDS:
        assert seed.id in frontend_profiles


def test_identity_fields_match_frontend(frontend_profiles):
    for seed in AGENT_SEEDS:
        front = frontend_profiles[seed.id]
        assert seed.name == front["name"]
        assert seed.role == front["role"]
        assert seed.kind == front["kind"]
        assert seed.objective == front["objective"]


def test_capabilities_and_restrictions_match_frontend(frontend_profiles):
    for seed in AGENT_SEEDS:
        front = frontend_profiles[seed.id]
        assert seed.capabilities == front["capabilities"]
        assert seed.restrictions == front["restrictions"]