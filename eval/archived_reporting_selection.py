"""Replay authored Reporting selections through the local API and mocked transport."""

import json
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.providers.reporting_sovereign import MODEL, ReportingSovereignProvider
from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from eval.archived_reporting_projection import fixtures
from pentagi.agents.archived_reporting import request_for, review_archive, review_archive_document


LOCK = Path(__file__).with_name("fixtures") / "ai" / "archived_reporting_selection_v1.json"
PREFIX = "/reporting/archive"


def load_archives(spec):
    raw_archives = dict(fixtures())
    reports = {}
    for key, expected in spec.items():
        if key == "slate":
            report = review_archive()
        else:
            raw, *_ = raw_archives[key]
            report = review_archive_document(json.loads(raw), sha256(raw).hexdigest())
        prepared = request_for(report)
        if (report["source_sha256"] != expected["archive_sha256"]
                or (prepared[2] if prepared else None) != expected["request_sha256"]):
            raise ValueError(f"Frozen archive or request changed for {key}")
        reports[key] = report
    return reports


def replay(case, report, digest):
    attempts = []

    class Gate:
        def close(self):
            pass

        async def authorize(self, **arguments):
            action = arguments["action"]
            return TrustGateDecision("reporting_agent", action, True, "ALLOW", "fixture", None, f"audit-{action}")

    def respond(request):
        body = {"destination": str(request.url), **json.loads(request.content)}
        actual = sha256(json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode())
        if actual.hexdigest() != digest:
            raise ValueError("Replay transport received a different request")
        attempts.append(actual.hexdigest())
        if "provider_status" in case:
            return httpx.Response(case["provider_status"])
        content = case.get("reply_text")
        if content is None:
            content = json.dumps({"highlights": case["highlights"], "recommendations": case["recommendations"],
                                  "emphasis": "observed_impact"})
        return httpx.Response(200, json={
            "model": MODEL,
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 24,
                      "completion_tokens_details": {"reasoning_tokens": 0}},
        })

    app = FastAPI()
    with TemporaryDirectory(prefix="reporting-selection-replay-") as directory:
        install_reporting_api(
            app, load_archive=lambda: report, output=Path(directory), make_gate=lambda _: Gate(),
            approved_scope=digest or "", make_provider=lambda config, **kw: ReportingSovereignProvider(
                config, transport=httpx.MockTransport(respond), **kw),
        )
        with patch("console.backend.reporting_api.require_api_key", return_value="synthetic-replay-key"):
            with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
                run = client.post(PREFIX + "/run", json={"mode": "local"})
                run.raise_for_status()
                local = run.json()
                reply = client.post(PREFIX + "/run", json={"mode": "sovereigneg"})
                if reply.status_code == 409:
                    return local, None, len(attempts), False
                reply.raise_for_status()
                saved = client.get(PREFIX + "/result", params={
                    "mode": "sovereigneg", "download": True,
                    "expected_sha256": sha256(reply.content).hexdigest(),
                })
                return local, reply.json(), len(attempts), saved.status_code == 200 and saved.content == reply.content


def order_metrics(actual, desired):
    positions = {value: index for index, value in enumerate(actual)}
    comparable = [(a, b) for a, b in combinations(desired, 2) if a in positions and b in positions]
    return {
        "matching": len(positions.keys() & set(desired)),
        "returned": len(actual),
        "desired": len(desired),
        "exact": actual == desired,
        "ordered_pairs": sum(positions[a] < positions[b] for a, b in comparable),
        "comparable_pairs": len(comparable),
    }


def selection_metrics(report, oracle):
    highlights = [(row["technique"], row.get("occurrence"), row["id"]) for row in report["summary"]]
    recommendations = [row["id"] for row in report["recommendations"]]
    admitted = {(row["technique"], row["occurrence"]) for row in report["findings"]}
    covered = {pair for pair in admitted
               if any(technique == pair[0] and (occurrence is None or occurrence == pair[1])
                      for technique, occurrence, _ in highlights)}
    return {
        "highlights": {"references": [list(ref) for ref in highlights],
                       **order_metrics(highlights, [tuple(ref) for ref in oracle["highlights"]])},
        "recommendations": {"references": recommendations,
                            **order_metrics(recommendations, oracle["recommendations"])},
        "covered_occurrences": len(covered),
        "admitted_occurrences": len(admitted),
        "published_coverage": report.get("summary_coverage"),
    }


def run_replays():
    raw = LOCK.read_bytes()
    spec = json.loads(raw)
    reports = load_archives(spec["archives"])
    runs = []
    for case in spec["replays"]:
        oracle = spec["archives"][case["archive"]]
        original = reports[case["archive"]]
        local, cloud, attempts, exported = replay(case, original, oracle["request_sha256"])
        result = cloud if cloud is not None else local
        runs.append({
            "id": case["id"],
            "archive": case["archive"],
            "expected_status": case["expected"],
            "status": cloud["status"] if cloud is not None else "blocked",
            "attempts": attempts,
            "findings_unchanged": result["findings"] == local["findings"] == original["findings"],
            "withheld_unchanged": result["withheld"] == local["withheld"] == original["withheld"],
            "fallback_matches_local": (all(cloud[field] == local[field]
                                            for field in ("summary", "recommendations", "emphasis"))
                                       if cloud is not None and cloud["status"] == "degraded" else None),
            "export_matches": exported if cloud is not None else None,
            "local": selection_metrics(local, oracle),
            "selected": selection_metrics(cloud, oracle) if cloud is not None and cloud["status"] == "selected" else None,
        })
    return {"protocol": spec["protocol"], "fixture_sha256": sha256(raw).hexdigest(), "cases": runs}


if __name__ == "__main__":
    print(json.dumps(run_replays(), indent=2, ensure_ascii=True))
