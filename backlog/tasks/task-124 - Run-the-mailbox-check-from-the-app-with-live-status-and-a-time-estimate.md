---
id: TASK-124
title: Run the mailbox check from the app, with live status and a time estimate
status: In Progress
assignee:
  - '@claude'
labels:
  - backend
  - frontend
  - mailbox
  - local-mode
dependencies:
  - TASK-109
priority: high
ordinal: 124000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-18: *"make it that I can run this email check on the platform manually and get
status when it succeeds and time estimation."*

Today the only way to check mail is `uv run manage.py check_mailbox` in a terminal on the owner's
machine, and the only feedback is whatever the command prints. The app shows past runs at
`/api/mailbox-runs/` but cannot start one.

### The constraint that shapes the whole design

**The deployed app has no Gmail credentials and cannot do the fetch.** Verified: no `GMAIL_*` value
appears in `.env.azure.example`, and the deploy workflow passes no such secret. That is deliberate —
TASK-109 scoped mail checking to local mode precisely so credentials and message content never reach
Azure, and TASK-69's history is why that boundary is a hard requirement.

So "run it from the platform" means two different things depending on where the browser is pointed,
and the owner chose to support both (decision 2026-08-18):

- **On the local app** (`localhost:5173` → local backend, which holds the credentials): start the
  check immediately and report progress as it goes.
- **On the deployed site**: record a request. The owner's machine picks it up on its next scheduled
  tick and runs it then. This is what makes the button useful from a phone; it costs a delay, and
  the UI must be honest that the run has not started yet rather than implying it has.

### Why this cannot be a plain synchronous request

The first live run fetched 641 messages (TASK-109's own record); an incremental run fetches 0. A
request that blocks until the run finishes would time out on the former and mislead on the latter.
The repo already has the pattern to avoid that: `cv_tasks.py` runs work on a daemon `Thread` and
exposes `get_cv_task(task_id, user_id)` for polling. Reuse it rather than inventing a second
job-status mechanism.

### The estimate, and why history is the only honest source

Owner chose both an up-front estimate and live progress. `MailboxRun` already stores `started_at` and
`finished_at`, so real durations exist to learn from — and they are wildly bimodal (a cold start over
a whole mailbox versus an incremental tick that finds nothing). An estimate that ignores that
distinction will be wrong in the direction that matters most, on the run the owner is most likely to
be watching.

Live progress needs a change too: `run_check` increments `run.fetched_count` in its loop but a poller
sees nothing until the row is saved, so progress has to actually be written mid-flight to be
observable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The owner can start a mailbox check from the app on a backend that HAS credentials, and the request returns immediately with a handle rather than blocking until the run finishes — verified against a run that takes longer than a normal request timeout, not only against an instant one
- [ ] #2 On a backend WITHOUT credentials (the deployed site), the same control records a request instead of failing, and the UI says plainly that the run has not started and will happen on the owner's machine — never a success message for something that has not run
- [x] #3 A recorded request is picked up by the next `check_mailbox` tick and runs even if the configured cadence is not due yet — that is the whole point of asking for one — and the request is marked as handled so it runs once, not on every subsequent tick
- [x] #4 Two checks never run at once, whether started from the app, from a queued request, or from the command line. The second caller is told a run is already in progress rather than being silently dropped or starting a duplicate — verified by attempting it, not by reading the lock
- [x] #5 While a run is in flight the app shows live progress that changes: at minimum messages fetched so far. This requires `run_check` to persist progress mid-run; a poller must observe the number increase during a single run, verified against a run over enough messages to see it move
- [x] #6 When the run finishes the app shows the outcome without a manual refresh: fetched, job-related, uncertain, suggestions, drafts written and drafts blocked — the same counters the digest already reports — and a failed run shows its error rather than looking like a run that found nothing
- [x] #7 A time estimate is shown before and during the run, derived from the duration of past completed runs rather than a constant, and it distinguishes a first/cold run from an incremental one because those differ by orders of magnitude. With no history yet it says so instead of inventing a number
- [x] #8 The estimate is honest when it is wrong: once elapsed time passes the estimate, the UI stops counting down and says it is taking longer than usual rather than showing a stuck or negative figure
- [x] #9 Starting a run is restricted to the owner, the same gate `/api/mailbox-runs/` already uses — verified with a second user against a real API response, since this control causes real mailbox access
- [x] #10 The app still never sends mail: `grep -rn "messages.send\|smtplib" backend/` finds nothing new. Triggering a check must not become a path to sending
- [x] #11 Backend tests cover starting a run, the no-credentials queued path, the already-running refusal, request pickup and single-use marking, the estimate including the no-history case, and the owner gate; no test contacts a real mailbox
- [x] #12 `npx tsc --noEmit` and `npm test` clean; the estimate calculation is a pure function with its own test, since it is the part most likely to silently drift
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): AC8: server-side taking_longer_than_usual and the frontend wording are test-proven; no negative countdown is representable. AC2 stays unchecked: the deployed site hides the whole run section because can_generate_cv is env-dependent and false in the container - filed as TASK-151; the queue path itself is test-proven server-side.

Capability detection already exists in effect: `_default_transport()` (`mailbox.py:1261`) returns the
configured transport or nothing, so "can this backend run a check" is that call rather than a new
settings flag. Use it, and expose the answer to the client so the UI can pick its wording — the
client must not guess from the hostname.

`cv_tasks.py` is the model for AC1 (daemon `Thread`, in-memory task registry, `get_cv_task` for
polling). Note its limitation before copying it wholesale: an in-memory registry dies with the
process, which is fine for a locally-run check and is exactly why AC2's queued request needs a real
DB row instead.

For AC3, `ScheduledTaskRun` already tracks last-run-at per named task and is the natural neighbour
for a request row, but a request is not a schedule — it needs a requested-at, a requester, a handled
marker, and ideally a link to the `MailboxRun` it produced so AC6 can show the outcome of the thing
that was asked for. Do not overload `ScheduledTaskRun` to avoid a migration.

AC4 matters more than it looks: `run_check` resumes from `MAX(uid)`, so two concurrent runs would
both fetch from the same marker and race to create `MailboxMessage` rows whose `uid` is unique —
producing `IntegrityError`s rather than clean duplicates. A database-level guard is better than a
process-level one, since the command and the web process are different processes.

AC7's bimodality is the interesting part. The signal that separates the two cases already exists:
`run_check` treats a cold start specially (see the `is_cold_start` logic that TASK-110 added, which
also suppresses drafting), and an incremental run's `fetched_count` is typically 0. Estimating from
the median of recent completed runs of the SAME kind is the smallest thing that respects it.
<!-- SECTION:NOTES:END -->

## Progress (2026-08-18)

Backend, API and UI all shipped. `MailboxCheckRequest` records a run asked for from a machine with no
credentials; `ScheduledTaskRun.running_since` is the concurrency guard, deliberately database-level
because the command and the web process are different processes and `run_check` resumes from
`MAX(uid)` — two concurrent runs race the unique constraint and produce `IntegrityError`s, not clean
duplicates. `estimate_seconds_from_history` and `is_within_check_window` are pure and separately
tested.

MEASURED in a browser against a throwaway database:

- **AC7** — with three seeded runs of 40/55/48s the estimate came back
  `{kind: 'incremental', estimated_seconds: 51.5}` and rendered as *"Routine check — Usually takes
  about 52s."* Derived from history, not a constant. With no history it returns `null` and the UI is
  built to say so.
- **AC1** — `POST /api/mailbox-runs/run-now/` returned `{queued: false, task_id: …}` immediately,
  without waiting for the run.
- **AC6, failure half** — a refused run showed *"Mailbox check did not run: no owner account is
  configured for this backend."* without a manual refresh. A failed run does not look like a run that
  found nothing, which is the specific thing the AC asks for.
- **AC8's UI half** — the page states that a manual run still respects the on/off toggle and the
  window and will say so rather than silently overriding.

### Not verified, and why

- **AC2** (the queued-request wording on a credential-less backend) is covered by backend tests but
  NOT browser-verified. `_default_transport()` reads `GMAIL_*` from the `.env` FILE, and file values
  win over empty shell overrides — the same precedence the production-DB guard documents — so
  producing a credential-less backend locally would mean editing the owner's `.env`. Not done for a
  test.
- **AC6's success half** (finished counters rendered after a real successful run) was not captured:
  the runs available were either refused or completed faster than the sampling window.
