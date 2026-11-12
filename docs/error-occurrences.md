<!-- TASK-372.1 -->
# Error occurrence collection

This is an **opt-in, local-only store**, not production observability. No Django
model or migration is added. Azure Container Apps has an ephemeral filesystem;
this implementation refuses collection with `DEBUG=False`. Production needs an
approved database-backed store before it can be described as durable. The local
runserver's normal Neon connection is not used by this collector.

Provision a private directory outside **every checkout** on persistent local disk.
On Windows restrict its inherited ACL to the owner and system administrators; on
POSIX use mode 0700. Set `ERROR_OCCURRENCE_LOCAL_DB` to an absolute SQLite filename
inside it and restart the local server. The parent directory must already exist.
Do not put it in a shared drive, repository, artifact export, or container disk.
The collector rejects paths under the current repository and does not create
directories or change ACLs. Deployment operators remain responsible for the
private directory's ACL. Tests blank this setting before doing any application work.

## Coverage matrix

All connected rows below require the local store. An unavailable row is **not
covered**. The tests are in `backend/jobradar/tests/test_error_occurrences.py`.

| Source | Availability and intake | Evidence / activation of unavailable sources |
| --- | --- | --- |
| Backend exceptions / HTTP 500 | Connected: ERROR handler on `django.request` and `jobradar`; warnings and ordinary successes excluded | `test_real_500_capture`; `test_logging_filters_warning_and_never_formats_payload`. Non-logging exceptions outside these namespaces are unavailable until routed to an application ERROR logger. |
| Pipeline and requirements analysis | Connected: `_save` explicit failed pipeline stage / analysis failure reason, including caught errors | `test_caught_worker_and_provider_failures`. Ordinary eligibility holds are excluded. Other pipeline services are covered only when they emit application ERROR. |
| Document / adjustment worker | Connected: `cv_tasks._update(status='failed')`, keyed by task id | `test_caught_worker_and_provider_failures`. Scheduled retries are not terminal document errors; provider attempts are captured separately. |
| Provider | Connected: `_provider_failure` captures failed structured provider attempts, even when caught and retried | `test_caught_worker_and_provider_failures`. Missing CLI, cancellation and failures outside this helper depend on enclosing worker failure or ERROR logging; no promise to capture every external provider invocation. |
| TeX compile | Connected: nonzero compiler result, before repair or failed-artifact handling | `test_compile_failed_attempt_even_before_repair`. Missing executable / process launch errors depend on enclosing worker failure. |
| Mailbox | Connected: `run_check` error row (scheduled and manual, including errors on skipped runs); manual task failures before a run exists | `test_mailbox_returned_failure`; `test_caught_worker_and_provider_failures`. Error-free skips/refusals and ordinary warnings are excluded. |
| Browser exceptions | Unavailable: no trusted browser error intake exists | Requires a bounded, sanitized browser reporter and backend intake endpoint; neither is added here. |
| Failing CI / deploy runs | Unavailable: no authenticated read-only run feed configured; CI files intentionally unchanged | Requires an approved read-only GitHub/Azure run adapter, stable run/attempt ids and persistent intake cursor. |
| Historical benchmark / adjustment JSONL, failed TeX/log files, bounded runtime events | Unavailable: historical files contain candidate/provider data and may already have rotated; runtime registry is ephemeral | Live document/compile hooks above capture new failures before rotation. Historical import needs a source-specific bounded adapter with generation/offset ids; do not blindly upload these files. |
| Azure production | Unavailable: local filesystem cannot meet durability; DEBUG=False refused | Needs an approved additive database migration/store, not an undocumented container volume assumption. |

`test_coverage_matrix_is_explicit` checks that all required source categories are
accounted for and unavailable sources carry activation guidance. It does not
claim browser, CI, historical-file or Azure collection works.

## Identity, privacy and future adapters

`ingest(source, events, cursor=...)` accepts at most 100 records atomically. Only
`status='failed'` records become occurrences. A producer must supply a stable
event id: e.g. source file generation + record offset, run id + attempt number,
or worker task id. Separate attempts must have different ids even if their errors
are identical. A new UUID is assigned by live capture where no upstream event
id exists. Replay uses deterministic UUIDs scoped to source, not message hashes.
Replay and separate identical errors are tested with concurrent writers.

Records retain UTC collection time, local environment, source, hashed operation
identity, fixed `OperationFailed` type and fixed source summary. Raw exception
types/messages, tracebacks, prompts, candidate/CV text, mail bodies, credentials,
sessions, request data, connection strings and filesystem paths are **never
retained**. Arbitrary incoming fields are ignored rather than regex-redacted.
An `occurrence:<uuid>` reference points to the sanitized local record itself;
there is no raw private evidence archive or public export endpoint. Original
private application artifacts retain their existing access/retention policies;
this collector neither copies nor publishes them. A single failure can have
separate provider, compilation, document and ERROR-log observations; these are
signals at different boundaries, not message-based deduplication.

`progress(source)` returns the digest of the last committed opaque cursor.
Adapters can compare generation/offset tokens while replaying a bounded batch;
it cannot reconstruct an original offset from a digest. No file poller is
implemented. Batch writes, cursor and replay ids commit together. Failed batches
leave both evidence and progress unchanged. The store survives local process
restart and does not rely on source files remaining unrotated. Anything that
fails while collection is disabled/degraded cannot be reconstructed without
replaying an upstream source; live hooks have no durable retry queue.

`unresolved(limit=100)` returns only unresolved sanitized records, with a hard
100-record limit. It and stable occurrence ids are the seams for triage and
TASK-372.3. No resolution, public endpoint or migration is included.

## Bounds, retention and health

There is no automatic expiry: **unresolved evidence is never evicted**. The store
stops accepting new records at 10,000 total rows or 4,096 SQLite pages (normally
16 MiB). A transaction has a 200 ms lock wait, at most 100 events, and a finite
source vocabulary. Full, locked, unavailable or corrupt storage returns an empty
result and sets `health()` to the safe process-local `degraded` signal. Collection
errors never log, send email, or escape into application work. A successful
intake sets `ok`; unset configuration sets `disabled`. This is an operator Python
query, not a new public health endpoint. Monitor it in the local owning process;
it resets on restart and is not a durable audit of collector outages.

At saturation retain the store, inspect `health()`, and provision capacity or
archive it privately before restarting intake. Do not delete unresolved records
to make room. No deletion/resolution command is provided in this collection-only
task. New failures during saturation are not persisted; the explicit degraded
signal is the warning that coverage is incomplete. SQL rollback, bounded batches,
concurrency, restart/replay, generation rotation and failure isolation have
hermetic tests. No network or production database is needed.

<!-- TASK-372.2 -->
## Incremental maintenance triage

From `backend`, run `uv run python manage.py triage_errors --dry-run` before
`uv run python manage.py triage_errors`. Maintenance sessions can request
`uv run python manage.py triage_errors --list` for every currently unresolved
group, its classification, disposition, count and linked task id, including
unchanged groups. These commands use the opt-in local store and never call a
model. Dry-run and list do not invoke Backlog or advance checkpoints; opening
an older store may create the additive triage tables.

The producer may supply `classification` and `build` to `ingest`. Build is
hashed; classification accepts only `cancelled`, `quota`, `transient`,
`actionable`, `retry_exhausted`; anything else becomes `unknown`. Legacy rows
and current hooks that cannot reliably classify a failure remain `unknown`.
No cause is inferred from discarded messages. Unknown groups require manual
review and are always available through `--list`; they do not create bugs.
Cancellation is expected, quota requires operator review, transient failures
require operational retry. Only actionable or retry-exhausted groups create
product bugs. These dispositions are persisted, not silently dropped. A trusted
local reviewer/adapter can update `occurrence_context.classification` to one of
these values after examining private evidence; the next triage detects it.
There is no automatic escalation by count and no new classification UI.

Signature = SHA-256 of source, environment, build digest (or unknown), operation
digest and technical error type. Existing intake retains only `OperationFailed`,
so this groups by the known technical boundary, not exception text. Different
operations/builds remain separate; unknown builds cannot be distinguished.
For each group, the fingerprint of its unresolved rows/context is the persistent
checkpoint. Only changed groups reach the CLI; resolved rows never participate.
The bounded store (10,000 rows) is scanned locally to detect changes, rather than
assuming insertion order catches later evidence edits.

`error_groups` keeps signature, task_id, checkpoint and disposition;
`error_group_links` maps occurrence ids to groups and private evidence references.
These tables are the queryable handoff to TASK-372.3. Shared bug descriptions
contain fixed symptoms, counts, collection times, operation/build digests,
unknown reproduction/root cause and verification AC. Private occurrence links
stay in SQLite. No raw logs or local paths are sent to Backlog.

Backlog is invoked with argument arrays from the repository root. A full
`error-group:<signature>` title marker is searched before creation and after
creation, recovering a task even if creation succeeded but the process/CLI
failed before the local link committed. Ambiguous matches fail closed.
CLI errors retain checkpoints for retry and the command emits only a fixed
safe error. A SQLite write transaction serializes cooperating triagers across
processes; it includes CLI calls (60-second timeout each), so intake can report
degraded while that lock is held. Run maintenance when intake is quiet.
The marker must remain in task titles for crash recovery; manual marker removal
before a pending link is recovered cannot be deduplicated. Linked tasks are
updated in place, including closed tasks: reopening, resolution and regression
policy belong to TASK-372.3. Nothing here resolves occurrences or closes tasks.

Tests: `backend/jobradar/tests/test_error_triage.py` fakes subprocess.run for
all Backlog access, including interrupted creation, update failures, concurrent
triage, restart idempotence, legacy rows, grouping, redaction and maintenance
commands. It never creates real task files or invokes providers.
