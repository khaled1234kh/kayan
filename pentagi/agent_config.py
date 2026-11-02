"""Role capabilities and tier labels. These do not replace ROE authorization."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def agent_config(role):
    contracts = json.loads((ROOT / "config/agent_contracts.json").read_text(encoding="utf-8"))
    tiers = json.loads((ROOT / "config/model_tiers.json").read_text(encoding="utf-8"))
    contract = contracts[role]
    tier = contract["model_tier"]
    if tier not in ("A", "B", "C") or not isinstance(tiers.get(tier), str):
        raise ValueError(f"Invalid tier configuration for {role}")
    return {**contract, "model_name": tiers[tier]}
