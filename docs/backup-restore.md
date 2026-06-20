# Backup and restore plan

DACHApply stores user data in PostgreSQL/Neon in production. Treat the database as the source of truth and use the app export/import only as an additional user-level portability path.

## Database backups

Recommended baseline for beta:

1. Enable Neon backups/restore points for the production branch.
2. Before risky deploys or migrations, create a manual restore point/snapshot in Neon.
3. Periodically verify that a restore can be made into a separate non-production branch.

Optional manual logical backup:

```bash
pg_dump "$DATABASE_URL" --format=custom --file=dachapply-$(date +%Y%m%d-%H%M).dump
```

Restore into a non-production database first:

```bash
pg_restore --dbname "$RESTORE_DATABASE_URL" --clean --if-exists dachapply-YYYYMMDD-HHMM.dump
```

Do not restore over production until you have confirmed the backup and understand the data loss window.

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
