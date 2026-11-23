# Security fixture remediation — 2026-11-23

## Reported detection

Two Windows computers reported `Backdoor:PHP/Perhetshell.B!dha` (also reported as `Backdoor:PHP/PeterShell.B!dha`) when downloading the GitHub ZIP. Microsoft Defender identified:

`pentagi_upstream/backend/pkg/tools/searchers/testdata/sploitus_result_nginx.json`

## Static findings

No `.php`, `.phtml`, or `.phar` files are tracked in the repository. The warning was triggered by web-shell source text embedded in archived exploit-search JSON fixtures, not by an executable PHP file in the checkout.

Repository-wide and nearby-fixture scans found:

| File | Finding | Action |
|---|---|---|
| `pentagi_upstream/backend/pkg/tools/searchers/testdata/sploitus_result_nginx.json` | 4 `<?php` tags, 3 `system($_GET[...])` command-execution strings, `base64_decode`, two `PD9waHA...` base64 PHP payloads (one decodes to `<?php system($_GET['cmd']);?>`), log-poisoning and reverse-shell instructions | **Removed** — unreferenced by code or tests |
| `pentagi_upstream/backend/pkg/tools/searchers/testdata/sploitus_result_cve_2026.json` | Full JSP web shell (`Runtime.getRuntime().exec(request.getParameter("cmd"))`), WAR-deployment instructions, encoded PowerShell command, reverse-shell material | **Removed** — unreferenced by code or tests |
| `pentagi_upstream/backend/pkg/tools/searchers/testdata/sploitus_result_metasploit.json` | No dangerous markers | Kept |
| `pentagi_upstream/backend/pkg/tools/searchers/testdata/sploitus_result_nmap.json` | No dangerous markers | Kept |
| `ddg_result_*.html` fixtures | No dangerous markers | Kept |

`sploitus.go` and `sploitus_test.go` build their responses from small inline JSON literals; no test or production code reads the two removed fixtures. `git grep` found no references to either filename.

A wider repository scan also identified `skills/library_index.json`, a curated third-party reference index consumed by `pentagi/call_context.py`. It contains security-education text with illustrative PHP/PowerShell strings but no executable files. The complete remediated ZIP scanned clean with Microsoft Defender, and modifying that index would change the frozen grounding corpus; it was therefore left unchanged by this remediation.

## Files removed

- `pentagi_upstream/backend/pkg/tools/searchers/testdata/sploitus_result_nginx.json`
- `pentagi_upstream/backend/pkg/tools/searchers/testdata/sploitus_result_cve_2026.json`

No payload was rewritten into a replacement fixture because neither file is used. No antivirus exclusions were added, no protections were disabled, and Git history was not rewritten.

## Verification

- `go test ./pkg/tools/searchers/... -count=1` — **pass** (`ok pentagi/pkg/tools/searchers`).
- `python -B -m pytest -q` — **747 passed, 21 skipped, 124 subtests passed**.
- `go test ./... -count=1` — all packages pass except pre-existing `pentagi/pkg/server/services`, which fails in this environment because `CGO_ENABLED=0` and no `gcc` is available for `go-sqlite3`; this is unrelated to the removed fixtures. CGO-enabled compilation was also attempted and failed only because `gcc` is absent.
- Repository marker scan after removal: no `<?php`, `system($_GET`, `PD9waHA`, JSP `Runtime.exec` web shell, or PeterShell/FilesMan strings remain in any searcher test fixture.
- Microsoft Defender `Start-MpScan -ScanType CustomScan` on a locally built ZIP of the remediated working tree — **clean**.

Post-merge step: after approval and merge into `main`, download a fresh `main` ZIP and repeat the Defender custom scan. Until then the same scan has been verified against the pushed `khaled` branch ZIP.
