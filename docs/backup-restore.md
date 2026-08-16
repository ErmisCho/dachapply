# Backup and restore plan

DACHApply stores user data in PostgreSQL/Neon in production. Treat the database as the source of truth and use the app export/import only as an additional user-level portability path.

## Database backups

Two independent layers, because they fail differently:

| Layer | Covers | Window | Status |
| --- | --- | --- | --- |
| Neon history retention (point-in-time) | "the migration ate the data 20 minutes ago" | see [Neon point-in-time retention](#neon-point-in-time-retention) | needs owner verification |
| Nightly `pg_dump` to Azure Blob | "the Neon project itself is gone or the account is locked out" | 30 days of nightly dumps | needs owner setup, see below |

Neon's own retention lives inside Neon, so it cannot help if the Neon project, the account, or the
billing relationship disappears. That is what the off-site dump is for. Neither layer replaces the
other.

### Nightly automated dump

`.github/workflows/database-backup.yml` runs `pg_dump --format=custom` against production at 03:17
UTC daily and PUTs the dump into a private Azure Blob Storage container.

**Not a workflow artifact, on purpose.** `ErmisCho/dachapply` is a public repository, and workflow
artifacts inherit repository read access — on a public repo that means anyone can download them. A
production dump is every user's job search, so the workflow must never use `actions/upload-artifact`
while the repo is public.

The workflow refuses to upload a dump it cannot vouch for. It fails the run if the dump is under
20 KB, if `pg_restore --list` cannot parse it, or if it contains fewer than 15 `TABLE DATA` entries.
A backup job that reports success while producing nothing is worse than no backup job at all.

#### Owner setup — the whole thing as one block

Steps 1–4 below explain each piece. If you just want it done, paste this instead; it discovers the
resource group the same way the deploy workflow does, and pipes the SAS straight into `gh secret set`
so the credential never lands in your clipboard, your shell history, or a browser form.

```bash
# Prereqs: az logged in to the subscription holding the container app, gh logged in to this repo.
set -euo pipefail
ACCOUNT=dachapplybackups            # 3-24 lowercase alphanumerics, GLOBALLY unique -- add digits if taken
CONTAINER=dachapply-backups
RG=$(az containerapp list --query "[?name=='dachapply'].resourceGroup | [0]" -o tsv)
test -n "$RG" || { echo "could not find the dachapply container app; wrong subscription?"; exit 1; }
LOCATION=$(az group show --name "$RG" --query location -o tsv)

az storage account create --name "$ACCOUNT" --resource-group "$RG" --location "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false --output none
az storage container create --name "$CONTAINER" --account-name "$ACCOUNT" --output none

# Write-only (create+write, no read, no delete) so a leaked CI token can neither download the
# backups nor destroy them. Expiry is deliberate: this must be re-minted, not forgotten.
SAS=$(az storage container generate-sas --name "$CONTAINER" --account-name "$ACCOUNT" \
  --permissions cw --expiry "$(date -u -d '+1 year' +%Y-%m-%d)" --https-only --output tsv)
printf 'https://%s.blob.core.windows.net/%s?%s' "$ACCOUNT" "$CONTAINER" "$SAS" \
  | gh secret set BACKUP_UPLOAD_URL
unset SAS

# 30-day retention as a storage lifecycle rule, so CI never needs delete permission.
az storage account management-policy create --account-name "$ACCOUNT" --resource-group "$RG" \
  --policy '{"rules":[{"enabled":true,"name":"expire-30d","type":"Lifecycle","definition":{"filters":{"blobTypes":["blockBlob"],"prefixMatch":["'"$CONTAINER"'/dachapply-"]},"actions":{"baseBlob":{"delete":{"daysAfterModificationGreaterThan":30}}}}}]}' \
  --output none

gh workflow run database-backup.yml --ref main   # then check Actions for a green run and a blob
```

Note the expiry: a SAS with a one-year life is a thing that will silently stop working next year. The
workflow fails loudly when the upload is rejected, so it shows up as a failed run rather than a silent
gap — that is the whole reason the guards exist.

#### Owner setup, step by step (one-time, roughly five minutes)

1. Create a storage account and a private container (any region; `dachapply-backups` below):

   ```bash
   az storage account create --name dachapplybackups --resource-group <rg> \
     --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false
   az storage container create --name dachapply-backups --account-name dachapplybackups
   ```

2. Generate a **write-only** container SAS. `--permissions cw` means create+write with no read and
   no delete, so a leaked CI token can neither download the backups nor destroy them:

   ```bash
   az storage container generate-sas --name dachapply-backups \
     --account-name dachapplybackups --permissions cw \
     --expiry 2027-08-16 --https-only --output tsv
   ```

   The full secret value is the container URL plus that token:
   `https://dachapplybackups.blob.core.windows.net/dachapply-backups?<sas-token>`

3. Add the repository secret. **Only `BACKUP_UPLOAD_URL` is missing** — `DATABASE_URL` already
   exists (added 2026-06-07). Verified 2026-08-16 by dispatching the workflow rather than by reading
   the secret list, since a secret can exist and be empty: run 31959476142 failed at step 1 and its
   annotations named `BACKUP_UPLOAD_URL` and nothing else. That proves it is populated, not that it
   is current — no workflow has ever consumed it and it predates this Neon project, so either re-set
   it or check that the first real dump is a plausible size.

   | Secret | Value | State |
   | --- | --- | --- |
   | `DATABASE_URL` | the production Neon connection string (`?sslmode=require`) | already set |
   | `BACKUP_UPLOAD_URL` | the container URL + SAS from step 2 | **missing** |

4. Apply a 30-day retention rule. This is a storage-account lifecycle policy rather than code in the
   workflow, because deleting old blobs from CI would require a SAS with delete permission:

   ```bash
   az storage account management-policy create --account-name dachapplybackups \
     --resource-group <rg> --policy '{"rules":[{"enabled":true,"name":"expire-30d","type":"Lifecycle",
     "definition":{"filters":{"blobTypes":["blockBlob"],"prefixMatch":["dachapply-backups/dachapply-"]},
     "actions":{"baseBlob":{"delete":{"daysAfterModificationGreaterThan":30}}}}}]}'
   ```

5. Run the workflow once manually (**Actions → Database backup → Run workflow**) and confirm a blob
   appears. Then do the restore drill below against that real dump.

**The SAS expires.** Note the expiry date from step 2 — when it passes, the workflow starts failing,
which is the intended loud behaviour. Renew with the same command.

#### When a backup run fails

The workflow exits nonzero and GitHub emails the repository owner, the same way
`uptime-monitor.yml` already reports outages. Confirm that path is actually on:
**<https://github.com/settings/notifications> → Actions → Notify on: "Failed workflows only"** (or
"All workflows"), with email enabled. If that box is off, backup failures are silent and the whole
workflow is decorative.

### Restore drill

Performed 2026-08-16 with PostgreSQL 17.5 client tooling against a disposable Docker Postgres 17.
Commands below are exactly what was executed; only the source database differs from a live restore,
which is called out at the end.

```bash
# 1. Scratch Postgres, thrown away afterwards. Never restore into anything shared.
export PGPASSWORD="$(openssl rand -base64 18)"   # throwaway, lives only in this shell
docker run -d --name dachapply-backup-drill -e POSTGRES_PASSWORD="$PGPASSWORD" \
  -p 55432:5432 postgres:17-alpine
psql -h localhost -p 55432 -U postgres -c "CREATE DATABASE dachapply_drill_restore;"

# 2. Fetch the dump to restore. Either download the newest blob from the backup container,
#    or produce one by hand with the same flags the workflow uses:
pg_dump "$SOURCE_DATABASE_URL" --format=custom --no-owner --no-acl \
  --file="dachapply-$(date -u +%Y%m%dT%H%M%SZ).dump"

# 3. Inspect before trusting. A dump that lists no TABLE DATA is not a backup.
pg_restore --list dachapply-<stamp>.dump | grep -c 'TABLE DATA'

# 4. Restore. --exit-on-error turns a partial restore into a failure instead of a surprise.
pg_restore --dbname "postgres://postgres:$PGPASSWORD@localhost:55432/dachapply_drill_restore" \
  --no-owner --no-acl --clean --if-exists --exit-on-error dachapply-<stamp>.dump

# 5. Verify the restore rather than assuming it.
psql -h localhost -p 55432 -U postgres -d dachapply_drill_restore \
  -tAc "select count(*) from information_schema.tables where table_schema='public'"
psql -h localhost -p 55432 -U postgres -d dachapply_drill_restore -tAc "select count(*) from auth_user"

# 6. Strongest check: Django agrees the restored schema is complete and current.
cd backend && env DATABASE_URL="postgres://postgres:$PGPASSWORD@localhost:55432/dachapply_drill_restore" \
  DB_SSL_REQUIRE=0 uv run manage.py migrate --check

# 7. Clean up.
docker rm -f dachapply-backup-drill
```

Result of the 2026-08-16 run: dump 72,350 bytes with 21 `TABLE DATA` entries; `pg_restore` exited 0;
source and restored databases both reported 21 public tables and the same row counts;
`migrate --check` exited 0, so no migration was missing from the restored schema.

`--no-owner --no-acl` matter: the dump carries Neon's role names, and a scratch database has
different roles. Without those flags the restore fails on ownership statements that are irrelevant
to recovery.

Caveat, stated plainly: the drilled dump came from a scratch database carrying the real migrated
schema and a single seeded row, not from production — production is deliberately off-limits to
tooling runs. The command sequence and the schema round-trip are proven; dump *size* and restore
*duration* at production data volume are not. Re-run steps 2–6 against the first real nightly blob
once `BACKUP_UPLOAD_URL` is configured, and record the timing here.

Do not restore over production until you have confirmed the backup and understand the data loss
window.

### Neon point-in-time retention

**Unverified — needs the owner to check the console.** Neon keeps a WAL history that lets you branch
from any moment inside the retention window, which is the fastest recovery path for "the last
migration deleted the wrong rows".

To verify and record it: <https://console.neon.tech> → the DACHApply project → **Settings → Storage
→ History retention**. Read the configured window, then replace this paragraph with the actual value
and the plan it comes from. Free-tier projects retain far less than paid ones, and the difference
decides whether Neon alone is a usable recovery path or whether the nightly dump is the only real
one. Do not assume a value; read it.

Before risky deploys or migrations, create a named restore point / branch in Neon regardless of the
window, so recovery does not depend on guessing a timestamp.

## App-level export/import check

For each beta release, test with a non-critical user:

1. Log in.
2. Open the Data/Export page.
3. Export jobs and preferences as JSON.
4. Import the file into a separate test account/environment.
5. Verify jobs, evaluations, notes, follow-ups, and preferences appear as expected.

The app intentionally excludes passwords, sessions, auth tokens, invite codes, admin logs, and secrets from exports.

## Before account deletion or data cleanup

1. Export the user's data from the app.
2. Confirm the export file opens and contains expected jobs/evaluations/notes/follow-ups.
3. If needed, take a database snapshot before destructive operations.
