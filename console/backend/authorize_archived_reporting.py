"""Local operator command to permit one archive's local report writing."""

from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone

from integration.roe_signing import sign_roe
from integration.trustgate_client import TrustGateClient
from console.backend.reporting_api import RESULTS
from console.backend.reporting_evidence import ROOT, SLATE_ID, ReportingCatalog
from console.backend.session_store import SessionStore


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("assessment_id", nargs="?", default=SLATE_ID)
    args = parser.parse_args()
    catalog = ReportingCatalog(SessionStore(ROOT / "data/engagement_sessions"), RESULTS / "evidence")
    try:
        archive = catalog.load(args.assessment_id)
    except (KeyError, ValueError, OSError) as error:
        parser.error(f"Assessment unavailable ({type(error).__name__})")
    now = datetime.now(timezone.utc)
    contract = {
        "engagement_id": archive.get("authorization_id", archive["assessment_id"]),
        "authorized_by": "Local archived Reporting operator",
        "scope": {
            "targets": ["127.0.0.1"],
            "allowed_techniques": ["reporting"],
            "forbidden_actions": ["llm_inference"],
        },
        "time_window": {"start": now.isoformat(), "end": (now + timedelta(minutes=30)).isoformat()},
    }
    contract["signature"] = sign_roe(contract)
    gate = TrustGateClient(trust_env=False)
    try:
        gate.load_roe(contract)
    finally:
        gate.close()
    print(f'Local report writing permitted for {archive["assessment_id"]} for 30 minutes.')


if __name__ == "__main__":
    main()

