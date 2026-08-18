---
id: TASK-125
title: Turn the mailbox check off, and confine it to a time-of-day window
status: To Do
assignee: []
labels:
  - backend
  - frontend
  - mailbox
  - local-mode
dependencies:
  - TASK-109
priority: high
ordinal: 125000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-18: *"user should be able to toggle this functionality on and off and set time
range that it would run and how often."*

**"How often" already exists** and needs nothing: `UserProfile.mailbox_check_cadence_minutes`
(default 60) is editable on the settings page and read by the local job on every tick, so changing it
in the app takes effect without touching the machine (TASK-109 AC8). This task is the other two.

**Off does not exist.** There is no way to stop the check from the app. The only levers are deleting
credentials from `.env` or not running the scheduled command — both machine-level, neither visible in
the app. Note that setting the cadence to 0 is *not* the answer and is explicitly rejected by
`CandidateProfileSerializer.validate_mailbox_check_cadence_minutes`, with the model comment
(`models.py:55`) recording why: a falsy cadence would read as "unset" and fall back to the default,
so 0 would silently mean *every hour* rather than *never*. An explicit enabled flag is the only
honest way to express off.

**A time-of-day window does not exist either.** The only "don't run now" rule today is
calendar-aware quiet hours (`mailbox_check_calendar_aware`), which asks the owner's calendar whether
they are busy. That is a different question from "never check my mail at 3am".

### The trap this task has to avoid

The repo has already filed a task about exactly this failure mode. TASK-115's whole point was that
two configuration paths for one setting is how someone changes a value in one place and cannot work
out why nothing happens. After this task there will be **three** independent reasons a run can be
skipped — disabled, outside the window, calendar-busy — plus a fourth that already exists (cadence
not yet due). If a run does nothing and does not say which of the four it was, this task has made the
system harder to trust rather than easier to control.

`MailboxRun.SKIP_REASONS` is currently `[('', 'Not skipped'), ('quiet_hours', 'Calendar busy')]` and
is the right place to record the answer — that column exists precisely so a skip is never silent.

### Timezone is not a detail

A window of 08:00-20:00 is meaningless without saying whose clock. The owner is in DACH; the server
may not be. The window must be interpreted in one clearly stated timezone, and the UI must show which
one, or the owner will set 08:00 and watch it fire at 09:00 after a DST change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The owner can turn mailbox checking off and on from the app, and off genuinely means no fetch happens — verified by running the check while disabled and observing that no mail was read, not merely that a counter stayed at zero
- [ ] #2 Off is its own explicit setting, not a cadence of 0 — the existing validator rejects 0 for a documented reason and that reason still holds
- [ ] #3 The owner can set a time-of-day window and the check only runs inside it, verified at a time inside the window and at a time outside it, with the clock manipulated in the test rather than by waiting
- [ ] #4 A window that wraps past midnight (e.g. 22:00-06:00) behaves correctly, because a naive `start <= now <= end` comparison silently never fires for that case
- [ ] #5 The timezone the window is interpreted in is stated in the UI beside the setting, and is the same one the code uses — verified against a run near a boundary, not assumed from `settings.TIME_ZONE`
- [ ] #6 Every reason a run did not happen is recorded and distinguishable: disabled, outside the window, calendar-busy, and cadence-not-due. `MailboxRun.SKIP_REASONS` gains the new values rather than a new parallel mechanism, and the app shows which one applied
- [ ] #7 Turning the feature off does not hide the evidence: past runs, suggestions and drafts remain visible and the UI says checking is off rather than looking like a mailbox with no mail in it
- [ ] #8 A manual run requested from the app (TASK-124) has defined behaviour when checking is disabled or the current time is outside the window — either it is refused with the reason, or it deliberately overrides, and the choice is stated in the UI rather than left for the owner to discover
- [ ] #9 Backend tests cover disabled, inside-window, outside-window, the midnight-wrapping window, and each skip reason being recorded; no test contacts a real mailbox
- [ ] #10 `npx tsc --noEmit` and `npm test` clean; the in-window decision is a pure function with its own test, since the wrap-past-midnight case is where this class of bug lives
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Two new `UserProfile` fields plus the existing cadence covers the settings surface; they belong in
`CandidateProfileSerializer.Meta.fields` next to `mailbox_check_cadence_minutes` and
`mailbox_check_calendar_aware`, which is where the owner already looks. Note the serializer's
existing `to_representation` quirk (`serializers.py:85`) about booleans and ints serialising oddly —
read that comment before adding a boolean.

Store the window as two times rather than a string, so the wrap case is a comparison rather than
parsing. AC4 is the specific bug worth writing the test for first: for a window where `start > end`,
"inside" means `now >= start OR now <= end`, and every naive implementation gets this wrong once.

AC6 is the acceptance criterion that keeps this feature honest. The gate order should be decided
deliberately and written down — cheapest and most-specific first (disabled → outside window →
cadence not due → calendar busy) means the recorded reason is the most useful one rather than
whichever check happened to run first.

AC8 needs a decision, not a default. The owner asking for a run by hand while the window says "not
now" is a plausible everyday case; refusing it silently would be the worst of the options.
<!-- SECTION:NOTES:END -->
