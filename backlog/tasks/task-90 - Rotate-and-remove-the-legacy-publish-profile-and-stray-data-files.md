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

### 2026-08-16 — there is a second copy of this credential, in GitHub

The description tracks the on-disk `dachapply.PublishSettings` and correctly notes it was never
committed. It misses the other copy: **`AZURE_WEBAPP_PUBLISH_PROFILE` is a repository secret**, added
2026-05-22, and no workflow references it any more —

    gh secret list                          -> AZURE_WEBAPP_PUBLISH_PROFILE  2026-05-22
    grep -rl AZURE_WEBAPP_PUBLISH_PROFILE .github/   -> no matches

Deployment moved to Container Apps in TASK-49 and the App Service workflow went with it, so this is a
live deployment credential with no consumer: it can only be used by something that should not be
using it. Deleting it is the cheapest half of AC1 and needs no Azure access at all:

    gh secret delete AZURE_WEBAPP_PUBLISH_PROFILE

Not run from this session — it is irreversible (the value cannot be read back before deleting), the
secret was not created by an agent, and AC1's real question is whether the App Service itself should
be retired. Deleting the secret without retiring the service rotates nothing on the Azure side; the
publish endpoint stays open and the on-disk `.PublishSettings` still holds working credentials.
Retire the App Service, and both copies become inert at once.
<!-- SECTION:NOTES:END -->
