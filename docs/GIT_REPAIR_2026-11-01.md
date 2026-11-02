# 3D Git registration — resolved 2026-11-01

Decision: **repaired**, not a permanent source-copy workaround. Investigation/repair took approximately eight minutes (14:38:53–14:46:46 UTC), within the requested 30-minute bound. This changed Git metadata/history only; all 135 backed-up working files retained their bytes.

## Diagnosis

Active worktree root: `C:\Users\khale\Downloads\KAYAN-video\kayan-company-office`.
The 3D app is its `kayan-3d/` subdirectory. The root `.git` file pointed to
`C:/Users/khale/Downloads/KAYAN-video/KAYAN-final/.git/worktrees/kayan-company-office`.
That administrative directory was missing. The common repository still contained
objects, refs and its main-worktree HEAD; no repository reinitialization was needed.

First standard repair failed exactly:

```text
error: unable to locate repository; .git file does not reference a repository: C:/Users/khale/Downloads/KAYAN-video/kayan-company-office/.git
```

## Completed repair

1. Copied the existing common `.git` directory, backed up the dangling active `.git` pointer, and archived/hashed the existing 3D working files. Excluded installed dependencies and build directories; followed no directory junctions.
2. Used Git's standard `worktree add --no-checkout` with a temporary path whose basename was `kayan-company-office`, creating the missing registration on the new branch `kayan-trustgate-console` from existing commit `1aecc86427cdcad64cc85042b247a101e8f23eb1`.
3. Ran `git worktree repair` against the real active folder. Git repaired the registration's backlink:

   ```text
   repair: gitdir incorrect: C:/Users/khale/Downloads/KAYAN-video/KAYAN-final/.git/worktrees/kayan-company-office/gitdir
   ```

4. Used `git read-tree HEAD` to populate the worktree index without checking out files. Retained the temporary pointer in the backup folder, so it is no longer another `.git` worktree pointer.
5. Committed only the current `kayan-3d` runtime/config/check paths. Existing absent runtime files were recorded as deletions relative to the old baseline; the repair did not remove any working files. No legacy handoff, old sibling server, Remotion project or unrelated root file was staged.

Frozen runtime commit: **300687a97bc379edb32035247060d1355f1fd2dd**, branch **kayan-trustgate-console**. It records the console already built and checked, including the TA planning UI; it adds no new product feature. Earlier source-copy evidence remains historical evidence, not the primary version-control mechanism.

## Verification and limits

- `git rev-parse --show-toplevel`, status, log and worktree listing now work in the active app.
- The 117 committed runtime paths match their working files. All 135 backup-file hashes and the other worktree's HEAD were unchanged.
- `git fsck --connectivity-only` exited 0. It listed retained dangling objects; these were not treated as corruption or deleted. No garbage collection/pruning was run.
- `git lfs ls-files` lists the four present FBX assets (AIManager, AIOps, AISales, Employee). The existing local LFS content remains available; no remote upload was attempted.
- Unrelated legacy documentation differences and repair scraps remain unstaged. **The whole parent worktree is not claimed clean.** The new branch records the frozen runtime, not a fabricated reconstruction of the lost original worktree registration/history.
- The active worktree shares its object store with `KAYAN-final/.git`; preserve that directory. It is still a separate repository from `kayan-trustgate`.

Backup and original-file hashes:
`C:\Users\khale\Documents\Codex\2026-10-31\stop-what-you-re-doing-and\work\git_repair_20261101`.
Machine-readable decision/result: [git_repair.json](../eval/reports/consolidation/2026-11-01_scope_freeze/git_repair.json).

Read-only verification:

```powershell
git -C 'C:\Users\khale\Downloads\KAYAN-video\kayan-company-office' rev-parse --show-toplevel
git -C 'C:\Users\khale\Downloads\KAYAN-video\kayan-company-office' log -2 --oneline
git -C 'C:\Users\khale\Downloads\KAYAN-video\KAYAN-final' worktree list --porcelain
git -C 'C:\Users\khale\Downloads\KAYAN-video\kayan-company-office' lfs ls-files
```

Do not repeat the reconstruction procedure on a healthy registration, reset the worktree, remove the common repository, stage unrelated changes or force-push history as a cleanup step.
