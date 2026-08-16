---
id: TASK-86
title: Send email reminders for due follow-ups and overdue feedback
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 14:30'
labels:
  - product
  - email
  - backend
dependencies: []
priority: medium
ordinal: 91000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reminders exist only as an in-app count the user must come look at (backend/jobradar/views.py:719, `jobs_needing_follow_up`). Both halves of the infrastructure already exist: working production email via send_mail (views.py:226, in daily use for password reset since TASK-2) and a daily background-scheduler pattern with idempotent day-guarding (services/demo_scheduler.py:17-19 and ScheduledTaskRun — currently used only to seed demo data).

This is wiring, not invention: the app knows what is due and can already send mail; it just never connects the two.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A daily job emails each user a digest of due/overdue follow-ups and overdue feedback checks — only when there is at least one item
- [x] #2 A profile setting turns the digest off, and the setting is respected
- [x] #3 Digests are idempotent per day (scheduler retry sends no duplicates — reuse the ScheduledTaskRun day-guard)
- [x] #4 Backend tests cover the has-items/no-items and opted-out cases
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Plain-text email is enough. Follow the demo_scheduler pattern rather than adding celery/cron infrastructure — one more task type in the existing daily tick.

### Progress (2026-08-16) — backend landed in Wave 4, AC2's toggle UI is Wave 5

Left **In Progress**: the setting exists and is respected end to end, but a user cannot reach it
without the profile checkbox, so AC2 stays unchecked.

`services/followup_digest.py` builds a plain-text digest and sends it per user; the daily tick in
`demo_scheduler` now calls `send_due_digests()` after `seed_demo_if_due()` — one more task on the
existing 04:00 tick, not a second scheduler and not celery, as the notes required. The day is
claimed through `ScheduledTaskRun('followup_digest_daily')` under `select_for_update`, so multiple
gunicorn workers and any retry all no-op after the first (AC3, asserted by a test that runs the
sender twice and finds one mail).

Scoping decision worth recording: the digest deliberately does **not** use
`services.access.accessible_jobs`, because that grants staff every row in the table — correct for
the admin API, very wrong for a personal reminder email that would then list other people's jobs to
the owner. It filters `created_by | submitted_for` instead, pinned by a test using a staff user.

Robustness the ACs did not ask for but a daily batch needs: a user with no email address is skipped
without raising, and one failing send does not abort the rest of the batch — both tested.

**A test-suite hazard was found and closed while doing this.** `config.settings` picks the mail
backend from the environment, so what the suite does with `send_mail` depended on local
configuration rather than on the test settings. Measured on a clean checkout it resolves to the
*console* backend — which sends nothing, but also records nothing, so every `mail.outbox` assertion
would have passed against an empty list and proved nothing. An autouse fixture now pins locmem for
the whole suite. (The implementing agent reported this as "the .env holds real Brevo credentials and
tests would send real mail"; the coordinator checked and that is not true of this checkout — neither
`.env` has mail keys. The fixture is still right, for the two reasons now written in its docstring.)

**Not verified, and it needs a deploy:** that the scheduler thread actually ticks in the Azure
container. The code path is the same one that runs demo seeding daily in production, so the evidence
is good but indirect. First real confirmation is a `ScheduledTaskRun` row named
`followup_digest_daily` with a fresh `last_run_at` after the first 04:00 following deploy — check
that before trusting the feature.

Wave 5 owes exactly one thing: a checkbox in profile settings bound to `follow_up_digest_enabled`,
which `GET`/`PATCH /api/profile/` already returns and accepts as a real JSON boolean.

### Closed 2026-08-16 - AC2's toggle landed in Wave 5

A single checkbox in a new "Email reminders" section of profile settings, labelled
*"Email me a daily digest of due follow-ups and overdue feedback..."*, bound to
`follow_up_digest_enabled` and read so that a missing key defaults to on, matching the model default.

Verified as a round trip rather than by looking at it: the API reported `true`, the checkbox was
clicked and saved, and the API then reported `false`. The setting therefore reaches the send path
that the backend tests already prove respects it.

The deploy-time caveat from the backend half still stands and is the one thing to check after
shipping: confirm a `ScheduledTaskRun` row named `followup_digest_daily` appears with a fresh
`last_run_at` after the first 04:00 following deploy. Until then the daily tick is proven only in
tests.
<!-- SECTION:NOTES:END -->
