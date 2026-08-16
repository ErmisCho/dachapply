---
id: TASK-70
title: Automate database backups and prove restore
status: In Progress
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 15:05'
labels:
  - ops
  - backend
  - data
dependencies: []
priority: high
ordinal: 75000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The backup story is entirely manual: docs/backup-restore.md:9-13 says "Enable Neon backups" and gives a `pg_dump` command, but nothing in the repo schedules one — the only cron workflow is the uptime probe (.github/workflows/uptime-monitor.yml:9-10). TASK-4 was closed on "documented", and even Neon's own retention window is only recommended, not verified enabled.

For an app holding a user's entire job search, an unscheduled backup is a runbook, not a backup.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A scheduled job (e.g. GitHub Actions cron using the DATABASE_URL secret) runs pg_dump against production on a fixed cadence and stores the dump in a private location with a retention policy — never in the public repo (see TASK-69)
- [x] #2 A restore drill from a produced dump into a scratch database has been performed, with the exact commands recorded in docs/backup-restore.md
- [ ] #3 A failed backup run is visible (workflow failure notification), not silent
- [ ] #4 Neon's own point-in-time retention is verified enabled and its window documented
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lazy correct version: Actions cron + `pg_dump --format=custom` uploaded as a workflow artifact on a private repo or to private storage (artifacts on a public repo are not private — check before choosing). GitHub notifies on workflow failure by default, which covers AC3 if notifications are confirmed on.

### Progress (2026-08-16) — prep landed in Wave 6, three ACs need the owner

**The repository is PUBLIC.** `gh repo view --json visibility` returns
`{"isPrivate":false,"nameWithOwner":"ErmisCho/dachapply","visibility":"PUBLIC"}`, and workflow
artifacts inherit repository read access — so `actions/upload-artifact` would have published the
production database to the internet. That single fact decided the storage design, and the workflow
carries a header comment saying so, so a future edit has to argue with it rather than quietly add
one. This is also why TASK-69 (the personal data export still in git history) is live exposure
rather than latent risk.

`.github/workflows/database-backup.yml` runs nightly at 03:17 UTC, dumps via a pinned
`postgres:17-alpine` client (the runner's bundled `pg_dump` refuses a newer server), and PUTs
straight into private Azure Blob through a **write-only** container SAS. `permissions: {}`. The
connection string is passed as `docker run -e DBURL` with no value, so it never appears in any argv
on the runner. Retention is an Azure lifecycle rule rather than delete permission on the CI token.

**The workflow's real job is refusing to lie**, since "documented" is how TASK-4 was closed. Three
guards run before any upload, and each was exercised against a deliberately bad input:

    real dump       ACCEPT: 72,350 bytes, 21 TABLE DATA entries -> uploads
    500-byte dump   REJECT (size floor)
    truncated dump  REJECT (pg_restore --list: end of file)
    bare URL / empty SAS  REJECT before the dump even runs

Coordinator addition: the content-floor guard had a silent-failure hole. `tables=$(grep -c ...)`
under `set -euo pipefail` exits the step **without printing anything** when there are zero matches —
and zero matches is precisely the failure that guard exists to report (a dump that authenticated but
selected nothing). Verified by running it, then fixed with `|| true` so the intended
`::error::dump contains only 0 TABLE DATA entries` actually prints.

**AC2 is met, with its limit stated.** The restore drill was executed, not described: a real migrated
schema into a disposable Docker Postgres 17, dumped with the workflow's exact flags, restored into a
second scratch database — `pg_restore` exit 0, 21 tables both sides, `migrate --check` exit 0. The
source was a scratch database, not production (production was off-limits to the agent), so the
schema round-trip and command sequence are proven while dump size and restore duration at production
volume are not. `docs/backup-restore.md` tells the owner to re-run the drill against the first real
blob.

**Owner actions, each of which closes one AC:**
- **AC1** — add two repo secrets under Settings → Secrets and variables → Actions: `DATABASE_URL`
  (production Neon string) and `BACKUP_UPLOAD_URL` (container URL + write-only SAS; the exact
  `az storage container generate-sas --permissions cw` command is in the doc). Then apply the 30-day
  lifecycle rule and run the workflow once manually. Checked: no existing workflow uses a
  `DATABASE_URL` secret, so the name does not collide with the deploy pipeline.
- **AC3** — confirm https://github.com/settings/notifications → Actions → email on failed workflows.
  The workflow exits nonzero on every failure path; whether that reaches you is a setting only you
  can see.
- **AC4** — read Neon Console → project → Settings → Storage → History retention and record the
  window in `docs/backup-restore.md`. Deliberately not guessed: free and paid tiers differ enough
  that a wrong number decides whether Neon is a usable recovery path at all.
<!-- SECTION:NOTES:END -->
