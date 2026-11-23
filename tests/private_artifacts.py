"""Skip helper for tests that replay intentionally private .build artifacts.

Public clones exclude raw request ledgers, model responses and mutable run output. When those
artifacts are present locally (the canonical development checkout), the assertions run unchanged.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def require_private(*relative_paths: str) -> None:
    missing = [p for p in relative_paths if not (ROOT / p).is_file()]
    if missing:
        pytest.skip(
            "requires private .build artifacts not published in the public repository: "
            + ", ".join(missing),
            allow_module_level=False,
        )
