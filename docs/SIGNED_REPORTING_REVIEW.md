# Signed evidence review

In **Reporting → Archived Reporting → Independent evidence review**, an assigned reviewer opens the assessment, records supported, contradicted or unresolved assertions, and exports the evidence package. Reviews are immutable revisions. The package digest commits to the selected assessment, captured source hashes and current review decisions.

The custodian prepares the existing admission-v2 archive catalogue entry on a separate workstation. The entry must bind `assessment_id`, `operational_evidence_sha256` and the current `review_receipt_sha256` list to the exported package. The catalogue also carries its admission manifest, record payloads and custody authority. Use the custodian tool on that workstation:

```powershell
python -m console.backend.sign_reporting_receipt --package review.json --catalogue admission-entry.json --key-id <key-id> --private-key <externally-held-ed25519-pem> --output signed-receipt.json
```

An assigned custodian imports that JSON in the console. The receipt signature covers the canonical catalogue, canonical package digest, assessment ID, sequence and predecessor. The server rejects stale or conflicting reviews and rechecks the active enrollment and key whenever Reporting opens the receipt. The SQLite receipt history must be kept in trusted storage. It prevents replay against the current database and does not protect against an administrator restoring the entire database to an older backup.

## Enroll real people

1. Assign different people as `reviewer` and `custodian`. Use private, high-entropy, individual bearer tokens. Deliver tokens privately through an authorized channel.
2. Keep a JSON enrollment array on operator-controlled storage outside the checkout. Set `KAYAN_REPORTING_REVIEWERS_FILE` and `KAYAN_REPORTING_REVIEWERS_SHA256` in the backend environment. Each row has `reviewer_id`, `role`, `token_sha256`, `assessment_ids` and `active`. Names and tokens may not overlap. Custodian rows also require `key_id`, `public_key_file` and the SHA-256 of those exact public PEM bytes in `public_key_sha256`.
3. Keep the private key off the application and inference hosts. Give the backend only the pinned public PEM. To revoke an identity or key, set its enrollment inactive, update the trust pin and restart. Test rows use `test_only: true`. The console labels these and refuses cloud Reporting for their results.

The browser round trip used existing loopback diagnostic captures and explicitly test-only roles. Admission v2 evaluated the signed catalogue, held the unresolved candidate, and recovered the same report after a backend restart. Demo evidence is under `.build/signed-reporting-demo/`. No operational people were enrolled or cloud requests sent.

