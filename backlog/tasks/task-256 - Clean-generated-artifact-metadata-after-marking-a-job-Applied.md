---
id: TASK-256
title: Clean generated artifact metadata after marking a job Applied
status: Done
assignee:
  - '@pi'
created_date: '2026-10-01 08:34'
updated_date: '2026-10-07 11:00'
labels:
  - backend
  - workflow
  - ux
dependencies: []
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/serializers.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/tests/test_api.py
priority: medium
type: task
ordinal: 254000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-10-01: generated application metadata files are useful while revising an application, but should be removed once that position is marked Applied. Human-facing CV and motivation-letter filenames should not expose internal job IDs, database keys, or other implementation metadata.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 After a job is successfully changed to Applied, its generated local metadata sidecar files are deleted
- [x] #2 Cleanup is limited to metadata for that job and never deletes its CV, motivation letter, TeX source, or another job's files
- [x] #3 Missing metadata files or an unavailable local workspace do not undo or falsely fail the persisted Applied status
- [x] #4 Generated CV and motivation-letter filenames omit internal job IDs, database keys, and metadata markers while retaining a clear recipient-facing document name and collision suffix when needed
- [x] #5 Revision and artifact lookup still work before application without depending on internal metadata embedded in the human-facing filename
- [x] #6 Tests cover Applied cleanup, isolation, missing-file behavior, simplified filenames, and collision handling
- [x] #7 After Applied, the job keeps a read-only link to its sent CV and letter; no later generation, revision or recompile modifies them (owner decision 2026-10-01)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Store each pending job’s artifact paths in one hidden, hashed local metadata sidecar so human-facing filenames no longer carry database IDs while equal-looking jobs still resolve independently.
2. Remove job IDs and template keys from new CV, letter, and archive filenames; retain exact legacy lookup fallbacks for files generated before this change.
3. After a persisted transition to Applied, best-effort delete only that job/user’s hidden artifact sidecar and matching cache metadata/archive entries, never its TeX or PDF files.
4. Add focused tests for naming, collision-safe job isolation, revision lookup, Applied cleanup, other-job preservation, and missing/unavailable metadata; then run full backend/frontend gates and browser verification.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Finished by code-implementer on 2026-10-01, building on pi's uncommitted work.

- **Sidecar.** Generation records each job's paths in `<workspace>/.dachapply-artifacts/<sha256(user:job)>.json`. Both the fresh-generation path and the cached-package path write it. `latest_generated_sources` reads the sidecar first. It then falls back to TASK-253 `-Job-<id>` names and the pre-253 exact names. Name-based fallbacks skip any path that another sidecar claims.
- **Names.** CV and letter files are now `<Applicant>-CV-<Company-Title>.tex` and `<Applicant>-<LetterLabel>-<Company-Title>.tex`. Download zips are `<Applicant>-Application-<Company-Title>.zip`, both for generate and recompile. On a collision the existing `_unique_destination` adds `-2`, `-3`, and so on, so nothing is overwritten. The cache key version is bumped to 6.
- **Cleanup.** `JobLeadSerializer.update` registers `transaction.on_commit(delete_generated_metadata, robust=True)` when status becomes `applied`. That covers the board PATCH and confirmed mailbox suggestions, which were the only paths I found that move an existing job to Applied. It deletes that job's sidecar(s) and its cache `.json`/`.zip`, including pre-256 `application-<id>-*` cache entries. It never deletes TeX or PDF files and never raises.
- **Pi's version and why it changed.** Pi called cleanup synchronously inside the serializer. In the mailbox path that runs inside `transaction.atomic()`, so a rollback would still have deleted the files. Pi's version also had no outer guard against an exception escaping into the request.
- **Sent-document pointer (AC7, owner decision 2026-10-01: "Keep the links").** Cleanup copies the deleted sidecar into the user's `retired-<sha256(user)>.json`, under the same job hash, as a map `jobs[<hash>] = {artifacts, letters, latest_letter, paths}`. There is no id in any filename and no migration. `paths` keeps every path the job ever sent.
  - Lookup order in `latest_generated_sources`: the live sidecar, then the sent pointer, then TASK-253 `-Job-<id>` names, then pre-253 names. Name fallbacks still skip all sidecar and retired paths, so an equal-looking job never adopts a sent file.
  - The board reads App.tsx:650/657, which calls GET `/jobs/<id>/cv-generation/` (views.py:1943 `cv_generation_preview`). That goes through `generation_preview` (cv_generator.py:602/605), then `latest_generated_artifacts`, then `latest_generated_sources`.
  - Read-only enforcement sits in the only two writers that every `latest_generated_sources` write path reaches, and it protects the sent paths of every account:
    - `persist_generated_files` handles AI revision and confirm-replacement. If the target is a sent path, it writes a fresh `_unique_destination` file instead.
    - `recompile_generated_package` handles recompile-latest and exact OLD/NEW revisions. A compiled sent source goes to a fresh `<stem>-N` TeX/PDF pair, which is recorded as the job's live revision.
  - If the retired write fails, the sidecar is kept rather than leaving the documents unprotected.
- **Not covered.** A data import that restores `status=applied` (`user_data_portability`) does not trigger cleanup. Mailbox-created leads that start out as `applied` have no files, so they need no cleanup.
- **Not verified.** I did not try this against the owner's real CV workspace or in a browser.
- **Tests (test_api.py).** AC7: `test_applied_job_keeps_read_only_link_to_its_sent_documents` and `test_revising_or_recompiling_an_applied_job_never_modifies_its_sent_documents` (sha256 checks); the equal-looking test also covers non-adoption. Earlier: `test_applied_status_deletes_only_its_local_metadata`, `test_applied_cleanup_runs_only_after_commit`, `test_applied_status_persists_when_metadata_is_missing_or_unavailable` and `test_equal_looking_jobs_get_collision_suffixed_names_and_stay_separate`. I also extended the name, lookup and e2e generation tests, adding package/recompile zip names and TASK-253 legacy resolution. I ran 11 mutation reverts and each one made at least one test fail.
- Owner verification 2026-10-07: the owner applied to Accenture after marking it Applied and reported "the 256 was working also when I did the application for accenture". The coordinator listed C:atex: the CV .tex and .pdf from 09:54 are still present, and `.dachapply-artifacts` holds one `retired-*.json` sent-document pointer.
<!-- SECTION:NOTES:END -->
