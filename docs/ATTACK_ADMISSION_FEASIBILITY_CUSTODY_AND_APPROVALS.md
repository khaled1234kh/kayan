# Feasibility custody, privacy and approval record

20 November 2026 · Blank approval templates · Intake unauthorized

## Responsibility and go/no-go matrix

Role labels designate responsibilities. Names, credentials and approvals are pending unless the row cites completed engineering evidence. The study coordinator records the controlling evidence and checks each item before presenting the intake decision.

| Gate | Accountable role | Required evidence | Status and remaining action |
| --- | --- | --- | --- |
| A · Offline v2 engineering | Independent engineering reviewer | Dated targeted sign-off, reviewed source hashes, 313 test results and 71 preserved historical digests. | **Completed** for the bounded offline version. Record the signed-off revision in the registration before execution. [Sign-off](ATTACK_PROVENANCE_ADMISSION_V2_FINAL_SIGNOFF_2026-11-20.md) |
| B1 · Collection and record integrity | Source owner and independent custodian | Authenticated collection/export record with system and collector IDs, stream/channel, profile, acquisition window, clock bounds, export coverage and gaps, native record IDs, original-byte SHA-256, timestamps and transfer acknowledgments. | **Pending.** Assign roles and verify a synthetic chain of custody. |
| B2 · Independent lineage | Separate source attester | Reviewed collector graph identifying sources, aliases, upstreams and origin families. Include explicit roots, attestation provenance and head-bound approvals. Show that unrelated sources were independently operated and shared relays were identified. | **Pending.** Designate an independent attester and verify explicit declarations, disputed aliases and versioned commitments. |
| B3 · Head and case control | Independent custodian | Authenticated case assignment, current head, predecessor pin and sequence, exact snapshot digest, and persisted histories. Demonstrate rollback rejection after restart and atomic update with an audited transfer. | **Pending.** Approve the mechanism by which evaluators obtain fresh authority outside the submission channel. |
| B4 · Adverse decisions and revocations | Custodian and review authority | Reconciled intake and review ledgers with contiguous revisions, active roster, withdrawals and revoked approvals. Document late evidence and have a way to invalidate affected items and reconcile decisions. | **Pending.** Rehearse omissions, supersession and revocation with synthetic records. |
| B5 · Time and receipts | Independent time administrator and review authority | Authenticated clock source and audit of verification time and bounds. Credential verification, role and validity records, independently issued receipt approvals, scope and exact digest binding. Show expiry and revocation checks. | **Pending.** Confirm operating controls for clock faults, lost keys and stale receipts. |
| C · Data owner, privacy and ethics | Data owner and institutional privacy/ethics authority | Signed scope agreement, privacy determination, ethics approval or documented institutional exemption where applicable, and approved access/retention and withdrawal procedures. | **Pending.** Complete the two templates below. |
| D · Independent reviewers | Review coordinator and adjudicator | Verified qualification and conflict declarations from two independent reviewers and a separate adjudicator. Signed blinding and preservation plan. | **Pending.** Obtain approval for reviewer arrangements and confirm two independent assignments and an adjudicator before study use. |
| E · Protocol and acceptance | Research lead, statistician and stakeholder | Dated preregistration, cohort separation and analysis plan, finalized thresholds and safety stopping rules. | **Pending.** Approve and freeze the protocol and evaluation criteria. |
| F · Real-telemetry intake | Study sponsor and authorized data owner | Written decision referencing each completed prerequisite, exact approved scope, custodians and the start and stop window. | **Unauthorized.** Obtain a separate signed go decision before collection or ingestion. |

The submitting team supplies evidence bytes and candidate claims. Authority arrives through a separate authenticated channel. The custodian archives the signed collection manifest, accepted head and predecessor, roster/revision ledgers and time attestation under access control. The evaluator verifies the current case assignment, raw snapshot digest, role-bound receipt approvals and scoped ancestry commitments against that channel. Reconcile the evidence roster with the independently controlled collection log before scoring. Record known collection gaps and disputes as such.

## Template 1 · Data-owner permission

- Legal/organizational data owner ___ · Authorizing role and basis ___ · Approval reference ___
- Study purpose and permitted uses ___ · Permitted custodian, collectors and recipients ___
- Approved source systems/assets and tenants ___ · Effective time window and collection cutoff ___
- Permitted observations ___ · `1102 v0` / `4624 v2` approval per profile ___ · Specifically permitted contextual records and exact permitted fields ___
- Collection coverage, clock basis, export procedure, original storage and transfer controls ___
- Authorized party who can pause evidence capture or withdraw data ___ · Contact path ___ · Deadline or rules for implementing withdrawal ___ · Treatment of already aggregated results ___
- Agreement revision ___ · Owner signature/date ___ · Custodian acknowledgement/date ___ · **Status unapproved**

## Template 2 · Privacy and institutional determination

- Privacy authority and institutional ethics body ___ · Applicable determinations/references ___ · Approved purpose and basis for handling ___
- Necessity and minimization review ___ · Allowed identifiers/context ___ · Prohibited fields and populations ___ · Export or publication restrictions ___
- Pseudonymization plan ___ · Scope of stable tokens needed for valid joins ___ · Separate key holder and storage ___ · Controlled transformation and lineage verification ___
- Named-role access, encryption, transfer and access logging ___ · Authorized review location ___ · Workspace and backup constraints ___
- Retention start/end or event triggers ___ · Deletion and verification for working data, exports, key maps and backups ___ · Retention exception owner ___
- Incident notification contacts, timelines and containment procedure ___ · Authority to stop processing ___ · Withdrawal request and audit procedure ___
- Privacy approver/date ___ · Ethics determination/signature/date ___ · **Status unapproved**

## Custodian and privacy checklist

- [ ] Match sources, requested fields and contextual records against the signed scope before collection. Record untouched evidence only in the approved restricted store.
- [ ] Preserve a verifiable mapping from originals to separately hashed review copies. Reviewers receive pseudonymized records with the intended joins and chronological relationships preserved. Keep identity keys under a separate key holder and log every access.
- [ ] Reconcile inventory, explicit ancestry, independent head assignments, adverse records and receipt revocations. Document and test fail-closed behavior when a dependency is unavailable.
- [ ] Verify reviewer enrolment, access scope, expiry and separation of duties. Lock and hash original reviewer returns. Keep reference labels separate from operational input reviews and evaluation outputs.
- [ ] Verify permissions, storage, use, transfers and release with the privacy owner. Record deletion certificates, withdrawal handling and incident reporting contacts.
- [ ] Confirm study and data owner written authorization references before enabling intake. Intake approver/date ___ · Approved window ___ · Decision ___ · **Status pending**.
