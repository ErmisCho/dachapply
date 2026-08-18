---
id: TASK-109
title: Check Gmail regularly and sync recruiter email into the pipeline
status: In Progress
assignee: []
created_date: '2026-08-16 18:57'
updated_date: '2026-08-17 15:50'
labels:
  - product
  - email
  - backend
  - local-mode
dependencies: []
priority: high
ordinal: 110000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-08-16: the app should check the owner's Gmail on a schedule — default hourly,
skipping hours where the owner's Google Calendar shows a busy event (interviews live there) — and
reflect what it finds in the pipeline, instead of the owner doing inbox triage by hand. Both the
cadence and the calendar-quiet behaviour are app settings, with those defaults.

Scope of this task is ingest and sync only (drafting is TASK-110): fetch new mail, classify what is
job-search-related (recruiter replies, rejections, interview invitations, offers), match messages
to JobLeads by sender domain and company, and turn matches into pipeline suggestions — a detected
rejection suggests the status change, an interview invitation extracts the proposed date into the
existing interview_at field, any reply on an applied job clears its waiting-for-feedback clock.
Suggestions, not silent mutations: the owner confirms each one.

This runs in **local mode only**, like CV generation: Gmail credentials and message content never
reach the Azure deployment or this public repository. Given this repo's history (TASK-69), that
boundary is a hard requirement, not a preference.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A local job (management command runnable by the existing scheduler pattern or a Windows scheduled task) fetches new mail since its last run via IMAP app password or Gmail-API OAuth in personal testing mode; credentials live only in the local .env, which stays gitignored. Cadence is hourly while the machine is on (owner decision 2026-08-16); a missed or skipped run is harmless because the next run catches up from the last-seen marker
- [ ] #7 Calendar-aware quiet hours (owner decision 2026-08-16): before running, the job checks the owner's Google Calendar via its private ICS URL (stored only in the local .env); if the current time falls inside a busy event, the run is skipped and the next idle-hour run catches up — no OAuth or Calendar API, and a fetch failure fails open (the run proceeds) so a broken calendar URL cannot silently stop mail checking
- [x] #8 Cadence and calendar-quiet are owner-changeable settings in the app (profile/settings page), defaulting to hourly + calendar-aware; the local job reads the stored setting on each tick, so changing it on the website takes effect without touching the machine
- [x] #2 Classification has a heuristic floor that works with no LLM configured; a local LLM is an optional env-gated upgrade, matching the CV-generation pattern
- [x] #3 Matched messages produce reviewable suggestions in the app (status change, interview_at date, feedback-clock close) that apply only on the owner's confirmation
- [x] #4 Nothing is silently missed: each run's digest lists every message classified as job-related AND every message it was uncertain about
- [x] #5 Every message read and every suggestion made is recorded in an append-only log table
- [x] #6 Backend tests cover classification, JobLead matching, and suggestion generation on fixture emails; no test touches a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMAP with a Gmail app password is the lazy correct transport (no Google app verification, ~stdlib
imaplib + email parsing); the Gmail API is the upgrade path if labels/threads are ever needed.
Owner involvement is one-time: creating the app password (see wave-plan owner checklist). Uncertain
classification goes in the digest rather than being dropped — a missed recruiter email costs an
interview; a false positive costs a glance.

### 2026-08-17 — AC1 CLOSED against a live mailbox, via OAuth rather than an app password

The owner declined 2-Step Verification. Google only issues app passwords when 2SV is on and retired
"less secure app access", so the IMAP route was permanently unavailable to them — not deferred,
closed. AC1 already allowed the alternative ("or Gmail-API OAuth in personal testing mode"), so the
Gmail-API transport was built to that clause rather than the AC being reworded.

**Measured on the real mailbox, not on fixtures:**

    run 1 (cold):        641 fetched, 133 job-related, 4 uncertain, 8 suggestion(s)
    run 2 (incremental):   0 fetched

Run 2 is the AC's actual requirement — "a missed or skipped run is harmless because the next run
catches up from the last-seen marker". Zero re-reads and zero duplicates against a 641-message
history is that marker working end to end. Credentials live in the gitignored `.env`
(`.gitignore:6`) and the refresh token in `dachapply-gmail-oauth-token.json` (`.gitignore:27`);
neither is committable. Cadence default is 60 minutes.

Scope granted is `https://www.googleapis.com/auth/gmail.modify`, confirmed in the live consent URL.
Bolting XOAUTH2 onto the existing IMAP transport would have been a far smaller diff, but IMAP OAuth
requires `https://mail.google.com/` — full mailbox access. Bigger diff, smaller grant.

**Two defects that only running it could have found**, both fixed before AC1 was checked:

- `gmail_oauth_setup` was refused by the local prod-DB guard (`settings.py:216`) because it is not a
  "serving command", and so could not run at all in the owner's configuration. It opens no database
  connection; the guard had nothing to protect. Exempted via a second frozenset rather than the
  existing one, because "deliberately uses production" and "never touches a database" are different
  claims and merging them would hand the wrong exemption to the next command added.
- The same command then died on `EOFError`: `input()` has no TTY in an agent harness or CI. It now
  takes `--code` and degrades to a printed instruction instead of a traceback.

**AC7 stays unchecked.** `GMAIL_CALENDAR_ICS_URL` is unset, so the calendar path has never executed
against a real calendar. The fail-open behaviour is proven by test (a raised `TimeoutError` and an
unparseable body both let the run proceed) but not by observation. Unblock: paste the private ICS
address from Google Calendar → Settings → *Integrate calendar* → *Secret address in iCal format*
into `.env` as `GMAIL_CALENDAR_ICS_URL`, then run `check_mailbox` once during a calendar event and
confirm the run records `skip_reason=quiet_hours`.

### 2026-08-17 verification (code-implementer, credential-vs-code audit for AC1/AC7)

Independently re-read `backend/jobradar/services/mailbox.py` and
`backend/jobradar/management/commands/check_mailbox.py` end to end (not just the prior outcome
notes) and ran the backend test suite before writing this. Both open ACs are CODE-COMPLETE,
CREDENTIAL-BLOCKED — nothing in the code itself is missing or stubbed:

- **AC1** (fetch since last run via a marker that makes a missed run harmless, hourly cadence):
  `run_check()` (mailbox.py:828) no-ops — returns `None`, touches no table — unless
  `settings.GMAIL_IMAP_USER` and `settings.GMAIL_IMAP_APP_PASSWORD` are both set
  (`config/settings.py:135-137`, read only from `os.getenv`, no default). `ImapTransport.fetch_new()`
  (mailbox.py:73) resumes via IMAP `UID {last_uid+1}:*` where `last_uid =
  MailboxMessage.objects.aggregate(Max('uid'))` (mailbox.py:856) — the resume point is the highest
  UID this app has ever logged, not a separate cursor that could drift or get lost, so a missed run
  is genuinely harmless. `_claim_tick()` (mailbox.py:808) enforces
  `profile.mailbox_check_cadence_minutes` (default 60, i.e. hourly) via a `select_for_update` claim;
  `--force` bypasses only the cadence gate, never the calendar check below. Verified by test, not
  just by reading: `test_run_check_resumes_from_last_seen_uid` asserts the second run's fetch call is
  `[5]` (MAX(uid) from the first run), never `[0]`; `test_run_check_respects_cadence_gate_and_force_overrides_it`
  asserts a same-tick second call returns `None` and `--force` overrides it. Both pass.

- **AC7** (calendar-aware quiet hours, fails open on fetch failure): `calendar_busy_now()`
  (mailbox.py:399-414) reads `settings.GMAIL_CALENDAR_ICS_URL` and returns `False` immediately if
  blank. When set, the fetch+parse path is wrapped in `except (HTTPError, URLError, TimeoutError,
  ValueError)` *and* a catch-all `except Exception` underneath it — both branches log a warning and
  return `False`; there is no exception a broken calendar URL could raise that escapes this and
  stops mail checking. Call site traced: `run_check()` only calls `calendar_busy_now()` at all when
  `profile.mailbox_check_calendar_aware` is `True` (mailbox.py:848), and a skip sets
  `run.skipped`/`run.skip_reason` *before* any IMAP fetch happens (`transport.calls == []` in the
  skip test). This fail-open behaviour is covered by test, not just asserted:
  `test_calendar_busy_now_fails_open_on_fetch_error` injects a raised `TimeoutError` from
  `_fetch_ics` and asserts `calendar_busy_now(...) is False`;
  `test_calendar_busy_now_fails_open_on_unparseable_text` feeds back garbage ICS text
  (`DTSTART:not-a-date`) and asserts the same. Both pass.

Also confirmed for TASK-110 AC1 (shares this task's credential): no send capability exists anywhere
in this feature — `grep -n "smtplib\|messages.send\|\.send("
backend/jobradar/services/mailbox.py backend/jobradar/management/commands/check_mailbox.py` returns
zero matches, and the test double `FakeTransport` exposes only `fetch_new`/`append_draft`, no
`send` method to even accidentally call.

Test command run for this audit (from `backend/`):
`uv run pytest -q -k "mailbox or gmail or draft or calendar"` →
`89 passed, 321 deselected`.

Exact env vars the owner sets in the local `.env` (commented template at
`.env.local.example:18-22`) to close AC1 and AC7:
```
GMAIL_IMAP_USER=<the Gmail address>
GMAIL_IMAP_APP_PASSWORD=<a Gmail App Password — spaces are stripped automatically>
GMAIL_CALENDAR_ICS_URL=<the calendar's private "secret address" ICS URL, from Google Calendar
  Settings -> Integrate calendar>
```

Exact command to close AC1/AC7 once those are set (from `backend/`):
```
uv run manage.py check_mailbox --force
```
then confirm against the real mailbox: the run's digest at `/mailbox` shows a non-zero
`fetched_count` (or `0` if the inbox genuinely has nothing new since the last UID, which is also a
valid observation), and — if the calendar is currently inside a busy event — a second run started
during that window shows `skip_reason: quiet_hours` instead. Only after one real, observed run
against the actual mailbox (and, for AC7, one observed quiet-hours skip or an explicit owner
confirmation that the ICS URL is reachable) should these two boxes be checked and status flipped to
Done. Nothing here is a code gap; both blockers are exactly "the credential does not exist locally
yet."
### 2026-08-18 — AC7's ".env" wording is superseded by TASK-115

AC7 says the private ICS URL is "stored only in the local .env". Owner decision on 2026-08-18: quiet-hours
calendars are managed from the app instead, several of them, and the `GMAIL_CALENDAR_ICS_URL`
environment variable is removed. See [[TASK-115]], which carries that change and its reasoning.

AC7's intent is untouched — calendar-aware quiet hours that fail open on a broken calendar — and it is
still what has to be verified. Only the storage location moves, so the criterion is not weakened and is
deliberately left as-is here rather than quietly rewritten; TASK-115 is the paper trail TW-005 asks for.

Practical effect: AC7 no longer closes by pasting a URL into `.env`. It closes when TASK-115 ships and a
real calendar configured through the app causes a run to record `skip_reason=quiet_hours`.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-16, wave 13 — In Progress, owner-blocked on two live halves)

Built and verified: check_mailbox management command (UID last-seen resume, interval cadence gate
adapted from the demo scheduler), injectable IMAP transport, heuristic EN/DE classification with
env-gated LLM upgrade, JobLead domain matching, MailboxRun/MailboxMessage (append-only)/
MailboxSuggestion (pending/confirmed/dismissed), confirm-only application reusing
JobLeadSerializer.update, per-run digest with uncertain as first-class, stdlib ICS quiet-hours
check that fails open (ponytail: no RRULE expansion; upgrade path recurring-ical-events), cadence +
calendar-aware as profile settings editable in the UI and re-read every tick, /mailbox review page.

MEASURED by the coordinator: 357 backend tests (298 + 59, re-run independently), tsc clean,
npm 33/33; browser on the live stack: seeded fake run rendered on /mailbox, Confirm flipped the
job interview -> rejected, zero pending after; digest showed "1 fetched, 1 job-related,
0 uncertain"; settings section present on /settings/profile; tracked files carry no secrets
(placeholders only). Asian-dad: PERFECT on all gradable criteria.

AC1/AC7 stay unchecked — blockers, exactly:
1. Owner creates a Gmail app password and sets GMAIL_IMAP_USER + GMAIL_IMAP_APP_PASSWORD in the
   local .env (see .env.local.example:19), then runs `uv run manage.py check_mailbox` once against
   the real mailbox and schedules it (Windows Task Scheduler, hourly).
2. Owner sets GMAIL_CALENDAR_ICS_URL to the calendar's private "secret address" ICS URL.
Once both are done and one real run has been observed, check AC1/AC7 and flip status to Done.
