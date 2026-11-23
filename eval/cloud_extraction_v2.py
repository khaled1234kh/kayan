"""Fixed-hypothesis extraction comparison on pinned synthetic defensive records."""
import argparse
import json
from pathlib import Path
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from eval import cloud_automatic_proof_v1 as v1
from eval.attack_evidence_v2 import Response, compact, parse

LOCK = v1.ROOT / "eval/fixtures/ai/cloud_extraction_v2.json"
TextQuote = Annotated[str, Field(min_length=1, max_length=120)]


class AddressedAtom(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    technique: str = Field(min_length=1, max_length=24)
    anchor: str = Field(min_length=1, max_length=24)
    cite: str = Field(min_length=1, max_length=24)


class Mechanic(AddressedAtom):
    role: Literal["mechanic"]
    value: Literal["observed"]


class Outcome(AddressedAtom):
    role: Literal["outcome"]
    value: Literal["completed", "failed", "unresolved"]


class Actor(AddressedAtom):
    role: Literal["actor"]
    value: Literal["adversary", "benign", "unresolved"]
    identity_quote: TextQuote | None = None
    confidence: Literal["stated", "uncertain"] | None = None


class Authorization(AddressedAtom):
    role: Literal["authorization"]
    value: Literal["authorized", "unauthorized", "unresolved"]
    scope_quote: TextQuote | None = None


class ProcessSession(AddressedAtom):
    role: Literal["process_session"]
    value: Literal["linked", "unlinked", "unresolved"]
    relationship_quote: TextQuote | None = None


class Provenance(AddressedAtom):
    role: Literal["provenance"]
    value: Literal["recorded"]
    source_quote: TextQuote | None = None


class Contradiction(AddressedAtom):
    role: Literal["contradiction"]
    value: Literal["adverse"]


class Uncertainty(AddressedAtom):
    role: Literal["uncertainty"]
    value: Literal["unresolved"]
    missing_role: Literal["mechanic", "actor", "authorization", "outcome",
                          "process_session", "provenance"] | None = None


class ExtractionV2(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    facts: list[Mechanic | Outcome | Actor | Authorization | ProcessSession | Provenance
                | Contradiction | Uncertainty] = Field(max_length=18)


STRUCTURED = v1.COMMON + (
    "Extract role-specific facts even when proof is incomplete. Each fact cites an original record and "
    "the same occurrence's action anchor. A mechanic cites its own anchor. Use uncertainty for missing "
    "support and preserve adverse facts. Optional quotes must be exact substrings of the cited record. "
    "Provenance describes recorded context. It never establishes independence or approval."
)
CORE = frozenset(("technique", "anchor", "cite", "role", "value"))


def atom_tuple(item):
    return tuple(item[key] for key in ("technique", "anchor", "role", "value", "cite"))


def normalize_v2(raw, evidence):
    atoms = ExtractionV2.model_validate(parse(raw)).model_dump(exclude_none=True)["facts"]
    normalized = []
    for atom in atoms:
        for field, quote in atom.items():
            if field.endswith("_quote") and quote not in evidence.get(atom["cite"], ""):
                raise ValueError(f"{field} is absent from cited record")
        core = {key: value for key, value in atom.items() if key in CORE}
        if atom.get("confidence") == "uncertain":
            core["value"] = "unresolved"
        normalized.append(core)
    return compact({"facts": normalized})


def score_cell(arm, raw, evidence, hypotheses, reviewed_key, admit):
    parsed, assembled, rejected, verdict, atoms, diagnostics = False, None, [], None, set(), {}
    wire_atoms = []
    try:
        if arm == "direct":
            mapped = Response.model_validate(parse(raw)).mappings
            parsed = True
            pairs = {(item.technique, item.cite) for item in mapped}
            if len(pairs) != len(mapped) or any(t not in hypotheses or c not in evidence for t, c in pairs):
                raise ValueError("invalid direct citations")
            assembled = raw
        else:
            schema = ExtractionV2 if arm == "v2" else v1.Extraction
            wire_atoms = [atom_tuple(item) for item in schema.model_validate(parse(raw)).model_dump()["facts"]]
            parsed = True
            normalized = normalize_v2(raw, evidence) if arm == "v2" else raw
            assembled, atoms, diagnostics = v1.assemble(normalized, evidence, hypotheses)
        candidate_ids = {item.technique for item in Response.model_validate(parse(assembled)).mappings}
        # Assembly is blind to the key. Independent scope and polarity are
        # checked as a separate veto, with no adding or replacing evidence.
        for technique in sorted(candidate_ids):
            if any(t == technique and role in v1.POLARITY
                   for t, _, role, _, _ in atoms - reviewed_key):
                rejected.append(technique)
        submitted = compact({"mappings": [
            item for item in parse(assembled)["mappings"] if item["technique"] not in rejected
        ]})
        verdict = admit(submitted) if not rejected or parse(submitted)["mappings"] else None
        error = None
    except (ValueError, TypeError, RecursionError) as exc:
        error = str(exc)
    wire_atoms = set(wire_atoms)
    return {
        "schema_valid": parsed, "error": error, "assembled": assembled,
        "semantic_withheld": rejected, "verdict": verdict, "groups": diagnostics,
        "role_hits": sorted(atoms & reviewed_key), "role_misses": sorted(reviewed_key - atoms),
        "role_extras": sorted(atoms - reviewed_key),
        "raw_hits": sorted(wire_atoms & reviewed_key), "raw_extras": sorted(wire_atoms - reviewed_key),
        "raw_misses": sorted(reviewed_key - wire_atoms),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    plan = v1.read(LOCK)
    for path, digest in plan["files"].items():
        if v1.sha(v1.ROOT / path) != digest:
            raise ValueError(f"Frozen input changed: {path}")
    old = v1.read(v1.LOCK)
    prepared = []
    for name, arms in plan["schedule"].items():
        cell = old["cases"][name]
        case, payloads, evidence = v1.fixture(name)
        hypotheses = cell["hypotheses"]
        display = {tid: {"mechanic": v1.MECHANICS[tid], "requires_process_link": link}
                   for tid, link in hypotheses.items()}
        requests = {
            "direct": v1.request(v1.DIRECT, Response, evidence, display),
            "v1": v1.request(v1.STRUCTURED, v1.Extraction, evidence, display),
            "v2": v1.request(STRUCTURED, ExtractionV2, evidence, display),
        }
        if not all(v1.fits(body) for body in requests.values()):
            raise ValueError(f"Case exceeds matched budget: {name}")
        prepared.append((name, arms, cell, case, payloads, evidence, requests))

    with httpx.Client(base_url="http://127.0.0.1:11434", trust_env=False, timeout=180) as client:
        version = client.get("/api/version").raise_for_status().json()["version"]
        models = client.get("/api/tags").raise_for_status().json()["models"]
        if version != old["ollama"] or {m["name"]: m["digest"] for m in models}.get(v1.MODEL) != v1.MODEL_HASH:
            raise ValueError("Pinned local runtime unavailable")
        with args.output.open("x", encoding="utf-8", newline="\n") as ledger:
            def log(row):
                ledger.write(json.dumps(row, ensure_ascii=True) + "\n")
                ledger.flush()

            log({"event": "registration", "manifest_sha256": v1.sha(LOCK), "ollama": version,
                 "model_digest": v1.MODEL_HASH, "mode": "local_loopback"})
            for name, arms, cell, case, payloads, evidence, requests in prepared:
                manifest, authority = v1.issue(case)
                reviewed_key = v1.role_key(case)

                def admit(raw):
                    return v1.evaluate_in_custody(raw, manifest, payloads, authority=authority)

                log({"event": "oracle", "case": name, "verdict": admit(v1.proposal(**cell["oracle"]))})
                for arm in arms:
                    body = requests[arm]
                    log({"event": "start", "case": name, "arm": arm, "request": body})
                    wire, error, elapsed = v1.run_cell(client, body)
                    metrics = {"error": error}
                    if error is None:
                        metrics = score_cell(arm, wire["response"], evidence, cell["hypotheses"],
                                             reviewed_key, admit)
                    log({"event": "result", "case": name, "arm": arm, "wire": wire,
                         "wall_seconds": elapsed, **metrics})


if __name__ == "__main__":
    main()
