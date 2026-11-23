"""Analyst-normalized fixtures for the offline Experiment D guard diagnostic."""
from eval.attack_evidence_guard_v3 import Event, Fact, review
from eval.attack_evidence_v2 import spans
from eval.attack_experiment_v2 import compact

CEDAR = Event("fixture", "JUN-4", "security-journal-clear")
SLATE_ENCRYPT = Event("fixture", "SE-2", "archive-encryption")
SLATE_RECOVERY = Event("fixture", "SE-2", "snapshot-purge-Z")
SILVER = Event("Blue", "finance-review", "grant-418")
FLINT = Event("fixture", "WC-14", "retracted-clear-allegation")

ANALYST_FACTS = {
    "cedar": (
        Fact("E2.1", "security-journal", CEDAR, "mechanic", "windows_event_log_clear", "6M"),
        Fact("E2.1", "security-journal", CEDAR, "outcome", "completed", "6M"),
        Fact("E3.1", "incident-custody", CEDAR, "actor", "adversary", "6M"),
        Fact("E3.1", "incident-custody", CEDAR, "authorization", "unauthorized", "6M"),
    ),
    "slate_encryption": (
        Fact("E2.1", "filesystem-ledger", SLATE_ENCRYPT, "mechanic", "availability_impact_encryption", "B19"),
        Fact("E2.1", "filesystem-ledger", SLATE_ENCRYPT, "outcome", "completed", "B19"),
        Fact("E1.1", "incident-response", SLATE_ENCRYPT, "actor", "adversary", "B19"),
        Fact("E1.1", "incident-response", SLATE_ENCRYPT, "authorization", "unauthorized", "B19"),
    ),
    "slate_recovery": (
        Fact("E4.1", "backup-service", SLATE_RECOVERY, "mechanic", "recovery_inhibition", "B19"),
        Fact("E3.1", "backup-inventory", SLATE_RECOVERY, "outcome", "completed", "B19"),
        Fact("E1.1", "incident-response", SLATE_RECOVERY, "actor", "adversary", "B19"),
        Fact("E1.1", "incident-response", SLATE_RECOVERY, "authorization", "unauthorized", "B19"),
    ),
    "silver": (
        Fact("E1.1", "blue-role-ledger", SILVER, "mechanic", "cloud_role_grant", "grant-418"),
        Fact("E1.1", "blue-role-ledger", SILVER, "outcome", "completed", "grant-418"),
        Fact("E2.1", "signed-schedule", SILVER, "authorization", "authorized", "grant-418"),
    ),
    "flint": (
        Fact("E2.1", "examiner", FLINT, "outcome", "unconfirmed"),
        Fact("E3.1", "incident-record", FLINT, "veto", "retracted"),
    ),
}


def diagnostic(records):
    def entries(tid, citations):
        return [{"technique": tid, "cite": ref} for ref in citations]
    checks = (
        ("cedar_complete", "cedar", ANALYST_FACTS["cedar"], entries("T1685.005", ["E2.1","E3.1"])),
        ("cedar_action_only", "cedar", ANALYST_FACTS["cedar"], entries("T1685.005", ["E2.1"])),
        ("slate_encryption", "slate", ANALYST_FACTS["slate_encryption"], entries("T1486", ["E1.1","E2.1"])),
        ("slate_recovery", "slate", ANALYST_FACTS["slate_recovery"], entries("T1490", ["E1.1","E3.1","E4.1"])),
        ("slate_shared_address", "slate", ANALYST_FACTS["slate_encryption"]+ANALYST_FACTS["slate_recovery"],
         entries("T1486", ["E1.1","E2.1"])+entries("T1490", ["E1.1","E3.1","E4.1"])),
        ("silver_omit_authorization", "silver", ANALYST_FACTS["silver"], entries("T1098.003", ["E1.1"])),
        ("flint_retracted", "flint", ANALYST_FACTS["flint"], entries("T1685.005", ["E1.1","E2.1","E3.1"])),
    )
    findings = {}
    for name, cid, facts, proposal in checks:
        addresses = spans(records[cid])
        if not {f.cite for f in facts} <= addresses.keys():
            raise ValueError(f"Analyst fixture cites unknown observations in {cid}")
        findings[name] = review(compact({"mappings":proposal}), facts)
    return findings
