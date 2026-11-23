# Feasibility reviewer instructions and adjudication form

20 November 2026 · Blank study materials

## Assignment and blinding

The review coordinator verifies two reviewers with practical Windows Security telemetry interpretation experience and ATT&CK evidence assessment competence. A separate adjudicator must meet equivalent criteria and have experience resolving evidence disagreements. For each role, record identity or controlled pseudonym, credential evidence, relevant experience, validity of authorization and conflicts. Reviewers must be independent of evidence collection and preparation, system development or scoring for the assigned cases, and each other’s review decisions. The adjudicator takes no part in either initial review. Identity verification records stay in the restricted enrolment register.

The custodian supplies both reviewers the same locked pseudonymized originals, source and timing context permitted by the data owner, reviewer rubric and pinned taxonomy. Use separately randomized order and opaque case IDs. Keep cohort strata, verifier outputs, normalized values, prepared proposals, earlier reference labels and other reviewer answers hidden. Reviewers independently identify facts and evidence groups, then submit signed records privately tied to packet hashes. A proposed session link under score is withheld from the reviewers. Provide the authorized source evidence needed to identify supportable links.

## Independent review worksheet

Fill one sheet for each event in a case. Add separate rows for distinct occurrences, including when a source record relates to several events. Cite exact record references and locators. Mark missing values or unresolved alternatives explicitly and describe their relevance.

| Field | Reviewer entry |
| --- | --- |
| Packet identity | Case ___ · Packet hash ___ · Assigned slot ___ · Rubric/taxonomy revision ___ |
| Event and original observations | Event occurrence ___ · Source/profile and locator ___ · Record IDs and revisions ___ · Raw field values or restricted audit pointers ___ · Expected typed values/precision ___ |
| Scope and timing | Tenant/host/authority/principal/session generation ___ · Event time interval/clock basis ___ · Provenance and uncertainty ___ |
| Attribution and link | Candidate clear–logon pair(s) ___ · Process/session association per pair, supported/refuted/uncertain ___ · Distinct upstreams or dependency ___ · Exact locator(s) ___ |
| Behavior and outcome | Mechanic/action ___ · Affected object ___ · Completed/failed/prevented/unresolved ___ · Supporting record and locator ___ |
| Authorization | Applicable written or recorded authority, issuing party and scope/window ___ · Authorized/unauthorized/unresolved ___ · Supporting and contradictory records ___ |
| Adverse or missing facts | Applicable contradiction, withdrawal, provenance dispute or coverage gap ___ · Which claim it affects ___ · Evidence references and reason ___ |
| Claim and reference decision | Technique and occurrence, or empty mapping ___ · Positive/negative/ambiguous/incomplete ___ · Eligible/withhold/no supported submission ___ · Rationale ___ |
| Sufficiency | List each jointly required evidence group by role and locator ___ · List independently sufficient alternatives ___ · State unresolved objections ___ |
| Reviewer declaration | Credentials record ___ · Independence/conflicts attestation ___ · Completion time ___ · Signature ___ · **Pending** |

Judge evidence as supplied. Preserve reports of authorization as unresolved when scope or timing is uncertain. Distinguish hypothesis, correlation, reviewed attribution and verified action/outcome. An alert, a matching string or a logon identifier alone cannot establish authorization or the full finding. Track absent and refuted links individually. Preserve relevant adverse facts even when a proposal could omit them.

## Adjudication and audit template

1. The coordinator verifies both signatures, packet hashes and completeness. Lock the original returns and compute agreement from those versions. Record blinded exposure incidents and whether a case was excluded or flagged under approved rules.
2. The adjudicator receives both locked submissions, conflicting evidence and source records after both reviews close. Resolve on evidence and rubric, retaining uncertainty where evidence cannot settle an issue. Neither verifier output nor earlier model results should inform reference adjudication.
3. Save each adjudication as a new revision citing both review hashes. Reference labels remain frozen until the scoring outputs are sealed. Corrections follow the approved revision and disclosure policy. Preserve original returns and earlier decisions in the restricted audit store.

| Adjudication field | Entry |
| --- | --- |
| Case/event and packet digest | ___ |
| Reviewer submissions and hashes | A ___ · B ___ |
| Disputed field/link/claim | ___ |
| Before-adjudication decisions | A ___ · B ___ |
| Supporting and adverse source locators | ___ |
| Final decision, rationale and unresolved constraints | ___ |
| Accepted evidence groups and required roles | ___ |
| Change from prior revision and downstream effects | ___ |
| Adjudicator credential reference, conflict disclosure, timestamp and signature | ___ · **Pending** |

[Earlier blinded review procedure](ATTACK_LABEL_REVIEW_AND_CONFIRMATION_2026-11-20.md) · [Feasibility protocol](ATTACK_ADMISSION_FEASIBILITY_PROTOCOL.md)
