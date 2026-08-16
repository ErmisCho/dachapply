---
id: TASK-109
title: Check Gmail regularly and sync recruiter email into the pipeline
status: In Progress
assignee: []
created_date: '2026-08-16 18:57'
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
- [ ] #1 A local job (management command runnable by the existing scheduler pattern or a Windows scheduled task) fetches new mail since its last run via IMAP app password or Gmail-API OAuth in personal testing mode; credentials live only in the local .env, which stays gitignored. Cadence is hourly while the machine is on (owner decision 2026-08-16); a missed or skipped run is harmless because the next run catches up from the last-seen marker
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
