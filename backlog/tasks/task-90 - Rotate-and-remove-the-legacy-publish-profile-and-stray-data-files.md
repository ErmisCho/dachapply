---
id: TASK-90
title: Rotate and remove the legacy publish profile and stray data files
status: To Do
assignee: []
created_date: '2026-08-16 00:43'
labels:
  - security
  - hygiene
dependencies: []
priority: medium
ordinal: 95000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`dachapply.PublishSettings` at the repo root contains a live MSDeploy password for the old App Service deployment (publishUrl `dachapply-…scm.westeurope-01.azurewebsites.net`). It was never committed (verified: `git log --all -- dachapply.PublishSettings` is empty; gitignored at .gitignore:2) — but it sits in a folder literally named "Backup" that may sync to other machines or cloud storage. Deployment moved to Container Apps (TASK-49), so the credential guards a door nobody uses.

The root also collects untracked personal-data files: `db.sqlite3`, `azure-sqlite-data.json`, and four `dachapply-full-*.json` account exports (all confirmed untracked via `git ls-files`).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The old App Service publish credential is rotated, or the App Service itself is retired
- [ ] #2 dachapply.PublishSettings is deleted from disk
- [ ] #3 The root-level personal exports and sqlite files are moved outside the synced repo folder or deleted — owner's choice, recorded in the closing notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner action (PSA-003 — these files were not created by agents, so agents must not delete them). Five minutes of hygiene; do it in the same sitting as TASK-69, which handles the one export copy that DID reach git history.
<!-- SECTION:NOTES:END -->
