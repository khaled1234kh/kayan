"""Opt-in cross-runtime recovery exercise using a disposable Rust audit journal."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import socket
import subprocess
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from ai.providers.base import LLMResponse
from ai.providers.reporting_ollama import MODEL
from ai.trustgate.client import TrustGateDecision
from console.backend.reporting_api import install_reporting_api
from console.backend.reporting_audit import AUDIT_URL
from console.backend.reporting_exchange import digest
from integration.roe_signing import sign_roe
from integration.trustgate_client import AuthorizationResult
from pentagi.agents.archived_reporting import review_archive
from test_signed_reporting_exchange import CUSTODY, ID, review, setup, sign


WSL = ["wsl.exe", "--distribution", "Ubuntu", "--exec"]
BINARY = os.environ.get("KAYAN_AUDIT_RESTART_WSL_BINARY")
TASK = "tool-" + "2" * 32


@contextmanager
def running_gate(directory, client):
    linux_directory = subprocess.check_output(
        [*WSL, "wslpath", "-a", str(directory)], timeout=15, text=True,
    ).strip()
    # WSL's Windows-side relay may briefly remain after the Linux process exits.
    deadline = time.monotonic() + 15
    while True:
        with socket.socket() as check:
            check.settimeout(0.5)
            if check.connect_ex(("127.0.0.1", 8000)) != 0:
                break
        assert time.monotonic() < deadline, "TrustGate test port already in use"
        time.sleep(0.1)
    script = '''
set -eu
cd "$2"
test -z "$(ss -Hlt 'sport = :8000')"
export TRUSTGATE_HMAC_KEY="$(cat fixture-hmac-key)"
export TRUSTGATE_ROE_KEY="$TRUSTGATE_HMAC_KEY"
printf '%s\n' "$$" > fixture-process
exec "$1"
'''
    with (directory / "gate-output.log").open("ab") as log:
        process = subprocess.Popen(
            [*WSL, "sh", "-c", script, "fixture", BINARY, linux_directory], stdout=log, stderr=log,
        )
        try:
            deadline = time.monotonic() + 20
            while True:
                assert process.poll() is None, f"Fixture Gate exited. See {log.name}"
                try:
                    client.get("/health").raise_for_status()
                    break
                except httpx.HTTPError:
                    assert time.monotonic() < deadline, f"Fixture Gate unavailable. See {log.name}"
                    time.sleep(0.1)
            yield
        finally:
            if process.poll() is None:
                stop = '''
set -eu
pid=$(cat "$2/fixture-process")
test "$(readlink "/proc/$pid/exe")" = "$1"
test "$(readlink "/proc/$pid/cwd")" = "$2"
kill -TERM "$pid"
'''
                subprocess.run(
                    [*WSL, "sh", "-c", stop, "fixture", BINARY, linux_directory],
                    timeout=15, check=True,
                )
                process.wait(timeout=15)


def capture_denial(client, catalog):
    scope = {"engagement_id": ID, "agent_id": "test-only-audit-fixture", "agent_role": "recon_agent",
             "tool_name": "inert_fixture_record", "target": "127.0.0.1"}
    response = client.post("/authorize", json={**scope, "tool_args": {}, "technique": "reporting", "provenance": {}})
    authorization = response.raise_for_status().json()
    assert authorization["decision"] == "DENY"
    audit_id = authorization["audit_entry_id"]
    ref = catalog.source_store.record(
        engagement=ID, agent=scope["agent_id"], role=scope["agent_role"], task=TASK,
        tool=scope["tool_name"], target=scope["target"],
        auth=AuthorizationResult(False, "DENY", "test only", audit_entry_id=audit_id),
        result=None, dispatched=False,
    )
    state = catalog.sessions.load(ID)
    meta = {**scope, "task_id": TASK}
    state["transcript"].extend([
        {**meta, "kind": "authorization_decision", "decision": "DENY", "audit_entry_id": audit_id},
        {**meta, "kind": "tool_denied", "source_artifact_sha256": ref},
    ])
    catalog.sessions.save(state)


def reporting_client(catalog, output):
    class Gate:
        async def authorize(self, **arguments):
            assert arguments["action"] == "write_report"
            return TrustGateDecision("reporting_agent", "write_report", True, "ALLOW", "fixture", None, "test-write")

        def close(self):
            pass

    app = FastAPI()
    install_reporting_api(app, catalog=catalog, output=output, make_gate=lambda _: Gate())
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 5060))


@pytest.mark.skipif(os.name != "nt" or not BINARY, reason="requires an explicitly supplied native Ubuntu fixture binary")
def test_signed_reporting_distinguishes_real_ledger_restarts_and_corruption(tmp_path, setup):
    launch, key, _, _, _ = setup
    directory = tmp_path / "isolated-gate"
    directory.mkdir()
    (directory / "fixture-hmac-key").write_text(secrets.token_hex(32), encoding="ascii")
    journal = directory / "audit_log.jsonl"
    output = tmp_path / "reports"
    params = {"assessment_id": ID}
    audits, report_bytes, receipt_head = [], None, None

    def check(current):
        # Reconstruct both the archive catalog and the actual Reporting routes.
        catalog, review_client = launch()
        with review_client, reporting_client(catalog, output) as client:
            meta = client.get("/reporting/archive", params=params).json()
            assert meta["verification"] == "independent_custody" and meta["custody_test_only"] is True
            assert catalog.exchange.head(ID) == receipt_head
            saved = client.get("/reporting/archive/result", params={
                **params, "download": True, "expected_sha256": digest(report_bytes),
            })
            assert saved.status_code == 200 and saved.content == report_bytes
            read = client.get("/reporting/archive/audit", params=params)
            assert read.status_code == 200
            body = read.json()
            assert body["source_sha256"] == meta["source_sha256"]
            assert body["counts"] == {"missing_reference": 1, current: 1}
            assert {row["source_id"]: row["status"] for row in body["references"]}[TASK] == current
            audits.append(current)

    with httpx.Client(base_url=AUDIT_URL, timeout=1, trust_env=False) as runtime:
        with running_gate(directory, runtime):
            assert runtime.get("/health").json()["audit_entries"] == 0
            catalog, review_client = launch()
            capture_denial(runtime, catalog)
            with review_client, reporting_client(catalog, output) as client:
                review(review_client)
                receipt = review_client.post("/reporting/custody/receipt", headers=CUSTODY, json=sign(review_client, key))
                assert receipt.status_code == 201, receipt.text
                receipt_head = catalog.exchange.head(ID)
                written = client.post("/reporting/archive/run", json={"mode": "local", **params})
                assert written.status_code == 200, written.text
                assert written.json()["findings"] == [] and written.json()["custody_test_only"] is True
                assert [row["technique"] for row in written.json()["withheld"]] == ["T1486"]
                report_bytes = written.content
            check("verified")
            assert runtime.get("/health").json()["audit_entries"] == 1
        original = journal.read_bytes()
        check("unavailable")

        with running_gate(directory, runtime):
            check("verified")
            assert runtime.get("/health").json()["audit_entries"] == 1
        assert journal.read_bytes() == original
        damaged = original + b"{incomplete-test-entry\n"
        journal.write_bytes(damaged)
        with running_gate(directory, runtime):
            assert runtime.get("/audit/verify").json()["valid"] is False
            check("ledger_invalid")
        assert journal.read_bytes() == damaged

        journal.write_bytes(original)
        with running_gate(directory, runtime):
            check("verified")
            assert runtime.get("/health").json()["audit_entries"] == 1
        assert journal.read_bytes() == original

    assert audits == ["verified", "unavailable", "verified", "ledger_invalid", "verified"]
    saved_path, = output.glob("*-local.json")
    assert saved_path.read_bytes() == report_bytes
    print(f"Signed custody and exact export preserved through {audits}")


@pytest.mark.skipif(os.name != "nt" or not BINARY, reason="requires an explicitly supplied native Ubuntu fixture binary")
def test_local_archived_ranking_respects_real_cedar_denial_and_approval(tmp_path, monkeypatch):
    directory = tmp_path / "isolated-local-ranking-gate"
    directory.mkdir()
    key = secrets.token_hex(32)
    (directory / "fixture-hmac-key").write_text(key, encoding="ascii")
    monkeypatch.setenv("TRUSTGATE_ROE_KEY", key)
    monkeypatch.setenv("KAYAN_REPORTING_LOCAL_RANKING", "1")
    source = review_archive()
    requests = []

    async def simulated_model(body, *, before_generate):
        before_generate()
        requests.append(body)
        selection = {"highlights": ["T1486/E2.1"], "recommendations": ["T1486-1"], "emphasis": "observed_impact"}
        return LLMResponse(content=json.dumps(selection), model=MODEL, provider="ollama", finish_reason="stop",
                           prompt_tokens=100, completion_tokens=25, latency_s=0.01)

    app = FastAPI()
    install_reporting_api(app, output=tmp_path / "reports", rank_local=simulated_model, approved_scope=False)

    def load_scope(runtime, forbidden):
        now = datetime.now(timezone.utc)
        contract = {
            "engagement_id": source["assessment_id"], "authorized_by": "Isolated Reporting test",
            "scope": {"targets": ["127.0.0.1"], "allowed_techniques": ["reporting"], "forbidden_actions": forbidden},
            "time_window": {"start": (now - timedelta(seconds=5)).isoformat(),
                            "end": (now + timedelta(minutes=2)).isoformat()},
        }
        contract["signature"] = sign_roe(contract)
        response = runtime.post("/roe/load", json=contract)
        assert response.status_code == 200, response.text

    outcomes = {}
    with httpx.Client(base_url=AUDIT_URL, timeout=2, trust_env=False) as runtime:
        with running_gate(directory, runtime), TestClient(
            app, base_url="http://127.0.0.1", client=("127.0.0.1", 5060),
        ) as client:
            assert client.post("/reporting/archive/run", json={"mode": "ollama"}).status_code == 403
            assert not requests
            load_scope(runtime, ["llm_inference"])
            fallback = client.post("/reporting/archive/run", json={"mode": "ollama"})
            assert fallback.status_code == 200 and fallback.json()["status"] == "degraded"
            assert not requests
            outcomes["DENY"] = fallback.json()
            load_scope(runtime, [])
            selected = client.post("/reporting/archive/run", json={"mode": "ollama"})
            assert selected.status_code == 200, selected.text
            assert selected.json()["status"] == "selected" and len(requests) == 1
            assert client.get("/reporting/archive/result?mode=ollama&download=true").content == selected.content
            assert runtime.get("/audit/verify").json()["valid"] is True
            outcomes["ALLOW"] = selected.json()

    journal = {row["entry_id"]: row for row in map(json.loads, (directory / "audit_log.jsonl").read_text().splitlines())}
    for verdict, result in outcomes.items():
        assert result["findings"] == source["findings"] and result["withheld"] == source["withheld"]
        write = journal[result["audit"]["write_report"]]
        assert write["decision"] == "ALLOW" and write["tool_name"] == "write_report"
        audit_field = "llm_inference" if verdict == "ALLOW" else "llm_inference_denied"
        observed = journal[result["audit"][audit_field]]
        assert (observed["decision"], observed["tool_name"], observed["engagement_id"]) == (
            verdict, "llm_inference", source["assessment_id"],
        )
        assert observed["tool_args"]["request_sha256"] == result["request_sha256"]
