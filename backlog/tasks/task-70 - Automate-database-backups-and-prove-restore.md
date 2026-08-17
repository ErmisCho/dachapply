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
- [x] #1 A scheduled job (e.g. GitHub Actions cron using the DATABASE_URL secret) runs pg_dump against production on a fixed cadence and stores the dump in a private location with a retention policy — never in the public repo (see TASK-69)
- [x] #2 A restore drill from a produced dump into a scratch database has been performed, with the exact commands recorded in docs/backup-restore.md
- [ ] #3 A failed backup run is visible (workflow failure notification), not silent
- [x] #4 Neon's own point-in-time retention is verified enabled and its window documented
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

### 2026-08-16 — measured: only ONE secret is missing, not two

The note above told the owner to add two secrets. That was inferred from "no workflow uses a
`DATABASE_URL` secret" — which is true, and which is not the same question as whether the secret
exists. It does:

    gh secret list
    AZURE_CREDENTIALS  AZURE_WEBAPP_PUBLISH_PROFILE  DATABASE_URL  GHCR_PULL_TOKEN  SECRET_KEY
                                                     ^ set 2026-06-07

Confirmed by running the workflow rather than by reading the list, since a secret can exist and be
empty. Run **31959476142** (`gh workflow run database-backup.yml --ref main`) failed at step 1 of 6,
and its annotations name one secret and only one:

    failure: secret BACKUP_UPLOAD_URL is not set (write-only Azure Blob container SAS URL)
    failure: see docs/backup-restore.md for how to create both
    failure: Process completed with exit code 1

The guard checks both and reports every one it finds missing, so `DATABASE_URL` being absent from
that list is positive evidence it is populated. **Limit of the evidence:** this proves non-empty, not
correct — no workflow has ever consumed it, and it predates the current Neon project by two months.
Before trusting the first real backup, either re-set it from the current production string or check
that run 1's dump is non-trivial in size.

So **AC1 needs `BACKUP_UPLOAD_URL` and nothing else.** Blocked here for the same reason as TASK-88:
the local `az` credential is a service principal for an unrelated project and sees no dachapply
resources and no storage accounts at all, so the container and SAS cannot be created from this
session.

**AC3 has been put in flight rather than left as a setting to eyeball.** Run 31959476142 is a genuine
failed run of this exact workflow on `main`. If a GitHub email about it arrived, AC3 is verified
end to end — which is stronger than confirming a checkbox at
https://github.com/settings/notifications, because it tests delivery rather than configuration. If no
email arrived, the notification setting is off and AC3 is proven *not* met. Either way, check the
inbox for run 31959476142 and record the result here.

### 2026-08-16 (evening) — AC1 reduced to one paste; still owner-only, and why

`docs/backup-restore.md` now opens with a single runnable block that does the whole of AC1: discovers
the resource group the same way the deploy workflow does, creates the account and private container,
mints the write-only SAS, **pipes it straight into `gh secret set`** so the credential never reaches a
clipboard, a shell history or a browser form, applies the 30-day lifecycle rule, and dispatches the
workflow.

It still cannot be run from here, and the reason is worth stating precisely rather than as "no
access": the local `az` identity is a service principal for an unrelated project and returns empty for
every dachapply resource, so there is no subscription in which to create the storage account. The
rights live in the `AZURE_CREDENTIALS` repo secret, which is write-only by design.

**Two routes were considered and rejected, so they are not re-proposed later:**
- Have a workflow mint the SAS and write the secret itself. `GITHUB_TOKEN` cannot write Actions
  secrets, so this needs a PAT — trading a one-minute paste for a longer-lived credential.
- Drop the SAS entirely and have `database-backup.yml` authenticate with `AZURE_CREDENTIALS` and
  `az storage blob upload`. This works and needs no new secret, but it hands the backup job a full
  service principal in place of a token that can only create and write. The write-only SAS was a
  deliberate least-privilege choice, documented in the workflow header; swapping it for convenience
  is a security regression, not a simplification.

Note the expiry when running it: a one-year SAS is a thing that stops working silently. It will
surface as a failed workflow run rather than a silent gap, which is what the guards are for.


### 2026-08-16 (late) — AC1 built the service-principal way, on the owner's instruction

The SAS design was replaced rather than waited on. `database-backup.yml` now logs in with the
`AZURE_CREDENTIALS` service principal that already deploys this app and uploads with
`az storage blob upload`; **`BACKUP_UPLOAD_URL` no longer exists** and no secret has to be minted by
hand. A new `provision-backup-storage.yml` (workflow_dispatch, create-if-missing, deletes nothing)
makes the account, the private container and the 30-day lifecycle rule.

The trade-off, stated plainly so it can be reversed knowingly: a write-only SAS (`--permissions cw`)
is genuinely tighter for this one job. It was dropped because minting it needs subscription access,
which left the workflow unrunnable — and a backup that is not running is worth less than one holding
a broader token. `AZURE_CREDENTIALS` was already in this repo's CI with rights to update the
Container App, so the blast radius if it leaks did not widen; what changed is that this job now has
an Azure login it previously did not. The SAS variant is preserved in `docs/backup-restore.md` behind
a `<details>` for the day this repo goes private.

Two properties deliberately kept:
- **The job still cannot delete.** Retention is an account lifecycle rule, not code in the run, so a
  compromised nightly run cannot destroy the backup history even with the wider credential.
- **The three guards are untouched** — size floor, `pg_restore --list`, and the TABLE DATA count.
  Refusing to upload a dump that authenticated but selected nothing is the whole point of the task.

Storage account and container names are repository **variables** (`BACKUP_STORAGE_ACCOUNT`,
`BACKUP_STORAGE_CONTAINER`), not secrets — they are identifiers, and a workflow cannot write repo
secrets without a PAT, whereas variables could be set from here without one.

The account key is read at run time into `AZURE_STORAGE_KEY` rather than passed as an argument:
anything in argv is readable via `ps` by any other process on the runner, which is the same reasoning
the dump step already used for the connection string.


### AC1 built, and blocked on exactly one subscription-level command

Everything is in place and merged: `database-backup.yml` authenticates with `AZURE_CREDENTIALS` and
uploads with `az storage blob upload`; `provision-backup-storage.yml` creates the account, private
container and 30-day lifecycle rule; `BACKUP_STORAGE_ACCOUNT` and `BACKUP_STORAGE_CONTAINER` are set
as repository variables. Four provisioning runs were needed to find out why it could not finish, and
the trail is worth keeping because three of those failures pointed at the wrong thing.

    run 1  SubscriptionNotFound   -- assumed the login's default subscription was wrong
    run 2  SubscriptionNotFound   -- pinned the subscription from the app's resource id; no change
    run 3  SubscriptionNotFound   -- removed every subscription-scoped call; no change
    run 4  diagnostic step, which finally said it plainly

The diagnostic (run 31970739281):

    subscriptions visible:  Azure subscription 1 (Enabled)
    resource groups:        rg-dachapply
    Microsoft.Storage:      NotRegistered

**Azure reports a call against an unregistered resource provider as `SubscriptionNotFound`.** That
single piece of API behaviour cost three fixes that were each locally reasonable and completely
useless: the subscription was never missing, and the calls were never wrongly scoped. This
subscription has simply never used Azure Storage.

Attempting the registration then gave the real boundary (run 31970835640):

    AuthorizationFailed: client object id ca616712-3108-4b09-ae49-a37260d1905c does not have
    authorization to perform action 'Microsoft.Storage/register/action' over scope
    '/subscriptions/f0d59028-...'

So `AZURE_CREDENTIALS` is scoped to the **resource group**, not the subscription — enough to update
the Container App, not enough to register a provider. Registration is inherently subscription-level.

**One command from a subscription owner unblocks everything:**

    az provider register --namespace Microsoft.Storage

Then re-run **Actions → Provision backup storage**, then **Database backup**. If the account creation
then fails with `AuthorizationFailed` too, the service principal also needs Contributor on
`rg-dachapply` for `Microsoft.Storage/storageAccounts/write` — the workflow now distinguishes that
case in its error message rather than making you guess.

AC1 stays unchecked until a real dump is sitting in the container.


### AC1 CLOSED 2026-08-16 — a real production dump is in private blob storage

The owner registered `Microsoft.Storage` on subscription `f0d59028-…` (the one command the resource
group-scoped CI credential could not perform), and the rest ran from CI.

    Provision backup storage  31971317245  success
      created storage account dachapplybackups
      container dachapply-backups ready (private)
      retention: blobs under dachapply-backups/dachapply- deleted after 30 days

    Database backup           31971571361  success
      dump size: 258038 bytes
      TABLE DATA entries: 22
      uploaded dachapply-20260816T204730Z.dump to dachapplybackups/dachapply-backups

**Verified against Azure directly, not from the workflow's own claim** — the whole point of this task
being that a backup job which reports success while producing nothing is worse than none:

    blob      dachapply-20260816T204730Z.dump   258,038 bytes   2026-08-16T20:48:02Z
    account   allowBlobPublicAccess: false
    container publicAccess: (empty -- private)
    policy    expire-backups, 30 days

Both guards fired correctly on real data rather than being taken on trust: 258 KB clears the 20 KB
size floor, and 22 TABLE DATA entries clears the floor of 15 (the drill measured 21; migrations have
added one since, which is exactly why the floor was set below the observed value rather than at it).

**One more thing this run flushed out.** The first attempt reached production, authenticated, and
refused to dump:

    pg_dump: error: aborting because of server version mismatch
    pg_dump: detail: server version: 18.4 (c9a59a4); pg_dump version: 17.11

Neon has moved to PostgreSQL 18.4 while the pinned client was 17. The workflow anticipated this in a
comment and the fix was the one-line bump it described; the measured versions are now recorded there
so the next person recognises the symptom. `docs/backup-restore.md`'s restore drill moved with it, so
the drill client cannot silently lag the dumps it has to read.

The nightly cron (03:17 UTC) now has everything it needs. **AC2's caveat still stands:** the drill was
executed against a scratch database, not this blob. Re-running it against a real dump means putting a
full production export on a local disk, which is the owner's call to make deliberately rather than
something to do in passing — the commands are in `docs/backup-restore.md`.

### AC4 CLOSED 2026-08-17 — the window is 6 hours, and it changes which layer is primary

The owner read it from Neon Console → project → Settings → Storage → History retention: **6 hours**.
Recorded in `docs/backup-restore.md`, both in the two-layer table and in its own section. Deliberately
not guessed earlier, and the reason that mattered is now visible: the number is small enough to
invert the design.

The assumption baked into this task was "Neon for recent mistakes, off-site dumps for disasters".
At a 6-hour window that is wrong. **Six hours is shorter than a night's sleep**, so a bad migration at
23:00 noticed at 08:00 is already outside it. The real split:

    noticed within 6 h   -> Neon branch from a timestamp   -> near-zero loss
    noticed after 6 h    -> last nightly dump (03:17 UTC)  -> up to 24 h of loss

So the nightly dump is not the exotic-failure backstop this task treated it as — it is the primary
recovery path for anything not caught inside one working session. That reframing is the actual
deliverable of AC4; the number on its own would have been trivia.

Two mitigations written into the doc rather than left implied: run migrations in the morning (the
window is only worth anything while someone is awake inside it), and create a named Neon branch
before risky work, because a branch does not expire with the retention window and so converts 6 hours
into an indefinite window for the one moment you cared about.

**AC3 is the last one open** and is not a code question: it asks whether a failed run actually reaches
the owner. Run **31959476142** is a genuine failure of this workflow on `main` — search the inbox for
`from:notifications@github.com dachapply` around 2026-08-16 and record yes or no here. A "no" proves
AC3 *not* met and points at https://github.com/settings/notifications → Actions → email on failure.

<!-- SECTION:NOTES:END -->
