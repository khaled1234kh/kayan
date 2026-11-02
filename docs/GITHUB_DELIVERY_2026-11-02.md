# GitHub delivery - 2026-11-02

User-selected destination: https://github.com/khaled1234kh/kayan. It had no remote refs when inspected. The canonical repository's branch is now main and origin points to that destination. No force push or remote-history replacement is planned.

Source readiness is recorded in DEMO_READY_2026-11-02.md: 17/17 final checks and actual local-Qwen acceptance, including final 51bba207... with 2 findings / 29 allowed / 1 denied. The complete audit journal verified after its serialization fix and restart. The published interface is backed by rendered evidence, with stated viewport/camera/performance limits.

The current tree excludes local runtime keys/journal, bytecode, dependency/build caches, recovery archives and duplicate exports. Those local files are retained. The original asset backup ZIP and development history remain local. The public main branch will start from the clean tested snapshot; original commits are retained in the local-history branch and recovery bundle, rather than being pushed into the public history.

Publication review inspected selected credential-signature patterns in tracked text and 23 existing commits without printing values. That bounded scan missed two Google OAuth-shaped fixture strings: GitHub push protection rejected the first push, naming historical commit 6665c94 and config_test.go lines 73/74. No override was used. The two fixtures were replaced with explicitly nonfunctional placeholders; the affected Go config tests were added to the consolidated profile. No live-provider validation of the old strings was attempted. The original local history is retained separately; no rejected historical commit is included in the clean published ancestry. Other reviewed matches were vendored examples/test defaults and instructional examples, including a URL substring false positive. This is not a comprehensive secret-detection guarantee. Large models/recordings use Git LFS.

Initial clean main was accepted as a542f8ad6ae5adb9430ec1360ee7a49a8dcbc51a, without an override or force push. A new clone fetched all six current LFS assets from GitHub and passed fsck, npm ci, production build and ten frontend checks. The README/screenshots and isolated-install dependency follow-up are published separately, with final remote verification recorded below. Local tests alone do not establish publication.

The asset-payload regression now uses checked-in original fingerprints instead of requiring the author's temporary candidate directory. All 84 Python tests passed again after that portability change; no temporary-directory skip is required for this test in a fresh clone.

Publish only the clean main branch. The local-history-20261102 branch and output/backups/pre-github-publication-20261102.bundle preserve the original development ancestry, including the credential-shaped historical fixtures, and are intentionally not pushed. This retains recovery evidence without bypassing GitHub push protection or rewriting an existing remote branch.

## Verified publication closure

Code/README commit **532a4871769a03013ffb81ffe1f02943388131e6** matched local main, GitHub main and the downloaded verification clone. Its lab/backend imported successfully without Jinja installed, and all 84 Python tests passed in the isolated environment (28 retained warnings). The clean download also passed npm ci, production build, ten frontend scripts and LFS fsck for all six current model/video assets. No local LFS cache was copied into that verification clone.

The public GitHub page was inspected in the authorized browser. All five README images decoded with natural dimensions 2183x1244; their rendered content and repository-relative links were checked. JSON proof, screenshot, source/clone/remote commit comparison and raw test logs are under eval/reports/final_todo_retry_20261102/. A subsequent documentation-only commit closes the TODO record and adds this evidence; the tested runtime source is unchanged.
