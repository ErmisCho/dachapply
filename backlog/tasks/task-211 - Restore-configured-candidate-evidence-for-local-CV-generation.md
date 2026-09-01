---
id: TASK-211
title: Restore configured candidate evidence for local CV generation
status: Done
assignee:
  - '@pi'
created_date: '2026-09-01 18:02'
updated_date: '2026-09-01 18:36'
labels:
  - backend
  - cv
  - local-runtime
dependencies: []
modified_files:
  - backend/config/settings.py
  - backend/jobradar/tests/test_local_runtime_launcher.py
  - scripts/dachapply-local-runtime.cmd
  - frontend/package-lock.json
priority: high
type: bug
ordinal: 210000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The local Generate CV dialog reports 'Candidate evidence is empty: paste it into account settings, or fix the configured evidence file' even though this owner workflow previously used configured candidate evidence. Diagnose the released local runtime and restore the existing owner evidence source without inventing candidate facts or weakening the intentional empty-evidence guard.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When usable owner candidate evidence exists in the supported account or configured-file source, Generate CV preview and generation no longer report that candidate evidence is empty
- [x] #2 The fix preserves the established evidence-source precedence and never substitutes fabricated, demo, or another user's evidence
- [x] #3 A genuinely empty account and unavailable/empty configured source still fails closed with an actionable error
- [x] #4 Regression tests use synthetic evidence and cover the reproduced local-runtime boundary without invoking an external model
- [x] #5 Full backend/frontend gates and browser verification pass on the released local workflow
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Pass the already-validated source checkout path from the released local-runtime launcher without copying private evidence into the disposable worktree. 2. Resolve only the existing DEBUG candidate-evidence fallback from that source root; keep stored account evidence first, explicit path overrides intact, and production unchanged. 3. Add one focused detached-runtime regression and run existing synthetic evidence/empty/owner-scope checks. 4. Rebuild the released local runtime, verify the owner evidence boundary and Generate CV dialog without starting an external model, then run full gates, Asian Dad evaluation, release, and post-merge closure.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause measured in the released runtime: stored evidence=0 chars; effective fallback points inside the detached runtime where the ignored file is absent; the source checkout contains 105,835 UTF-8 characters; load_candidate_evidence reproduces the exact 503 message with zero writes/model/Gmail calls. Debug artifact: .orchestrator/debug/task-211-2026-09-01-bugfix-1-1.md.

Implemented the root fix: the local launcher exports its validated source checkout through DACHAPPLY_SOURCE_REPO, and only the existing DEBUG file fallback resolves from that root. Stored per-account evidence and explicit CODEX_CANDIDATE_EVIDENCE_PATH still win; production remains empty by default. Added a subprocess regression for the detached runtime boundary. Synthetic measurement resolved the source file and built a 42,287-character grounded context. Full backend: 1,046 passed. Frontend: 206 passed and build passed. A newly published transitive audit failure was separately root-caused and fixed with compatible lock-only patches; final audit reports 0 vulnerabilities.

Released through PR #118 as 25876651f9624fde69a8ed105ea46cb91401e975. Main run 33543860626 passed tests, image build, Azure deployment, and public verification. The dedicated local runtime synchronized to the released SHA and ports 5173/8000 return HTTP 200. Released owner-flow verification returned 202 at a fake task boundary with 120,577 grounded context characters, source file present, and guarded measurements of 0 database writes, 0 model calls, and 0 Gmail calls. Chrome confirmed the released localhost frontend responds without the prior global error; the backend response that drives its ErrorBox no longer contains the empty-evidence failure. Asian Dad verdict: PERFECT (self-graded disclosed).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Restored the owner evidence file to detached localhost runs by passing the validated source checkout to the existing DEBUG fallback, without copying private data or changing stored/explicit/production precedence. Verified with full gates, runtime/API/browser boundaries, a fake model boundary, and zero-write/no-external-call guards.
<!-- SECTION:FINAL_SUMMARY:END -->
