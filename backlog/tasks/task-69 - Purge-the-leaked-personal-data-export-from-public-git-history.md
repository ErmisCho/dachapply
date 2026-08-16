---
id: TASK-69
title: Purge the leaked personal data export from public git history
status: To Do
assignee: []
created_date: '2026-08-16 00:43'
labels:
  - security
  - privacy
  - P0
dependencies: []
priority: high
ordinal: 74000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Commit 912b853 (2026-05-22) added `dachapply-full-2026-05-22.json` — a complete account export (~59 KB) containing the owner's job-search history, application statuses, and two personal email addresses. Commit a08f5b8 removed and gitignored the file, but a deleted file stays permanently fetchable from history, and `gh repo view ErmisCho/dachapply --json visibility` returns PUBLIC.

Verified 2026-08-16: `git show 912b853:"dachapply-full-2026-05-22.json"` returns the full export including the personal email in the user record; `git log --all --diff-filter=A -- "*dachapply-full*"` confirms 912b853 is the adding commit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The export blob is unreachable from every ref on GitHub (history rewritten with git-filter-repo or BFG; `git log --all -- "dachapply-full-2026-05-22.json"` is empty on a fresh clone)
- [ ] #2 The force push is performed by the owner personally, after coordinating any open branches (PSA-003 — agents never force-push)
- [ ] #3 A full-history secret/PII sweep (gitleaks or trufflehog over all refs) confirms no other personal exports or credentials remain reachable, with the command and result recorded in the task notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`git filter-repo --invert-paths --path "dachapply-full-2026-05-22.json"` on a fresh clone, then force-push all refs. Note the limits honestly when closing: existing forks/clones and GitHub's commit-view cache can retain the blob — GitHub support can be asked to run GC on cached views. The file contains no credentials, so this is exposure minimization, not rotation. Do this before TASK-70 stores any backup dumps anywhere near the repo.
<!-- SECTION:NOTES:END -->
