"""Local operator HMAC signing; the key is private runtime data, never a published default."""
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

KEY_PATH = Path(__file__).resolve().parents[1] / "data/roe_signing_key"


def signing_key():
    configured = os.environ.get("TRUSTGATE_ROE_KEY")
    if configured is not None:
        if len(configured) < 32:
            raise ValueError("TRUSTGATE_ROE_KEY must contain at least 32 characters")
        return configured.strip()
    KEY_PATH.parent.mkdir(exist_ok=True)
    try:
        with KEY_PATH.open("x", encoding="utf-8") as file:
            file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return KEY_PATH.read_text(encoding="utf-8").strip()


def sign_roe(roe):
    scope = {k: roe["scope"].get(k, []) for k in ("targets", "allowed_techniques", "forbidden_actions")}
    window = {k: roe["time_window"][k] for k in ("start", "end")}
    compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    canonical = f"{roe['engagement_id']}:{roe['authorized_by']}:{compact(scope)}:{compact(window)}"
    return hmac.new(signing_key().encode(), canonical.encode(), hashlib.sha256).hexdigest()
