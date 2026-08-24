---
id: TASK-185
title: Mailbox health alert sends one email every five minutes
status: To Do
assignee: []
labels:
  - backend
  - alerting
  - bug
dependencies:
  - TASK-160
priority: high
ordinal: 185000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-24, forwarding an 83-message Gmail thread: *"I keep getting these emails"*.

Measured from the forwarded thread: **83 identical "DACHApply mailbox check needs attention" emails**
between 21 Aug 23:28 and 24 Aug 13:32 — roughly one every 25 to 50 minutes for three and a half days.
The only thing that changes between them is the hours counter climbing from 24.0 to 86.1.

`_send_mailbox_health_alert` (views.py) is not broken; it is tuned for the wrong duration. Its
cooldown is `settings.ERROR_ALERT_COOLDOWN_SECONDS`, which defaults to **300 seconds**, borrowed from
TASK-88's *error* alerting. Five minutes is a reasonable floor for a transient exception that may or
may not repeat. It is the wrong unit entirely for a condition that, by construction, persists until a
human runs an interactive OAuth command — `MAILBOX_STALE_ALERT_HOURS` defaults to 24, so the alert
only fires once the problem is already a day old and then keeps firing for as long as it lasts.

So the two settings disagree about what kind of event this is: one says "this condition is measured in
days", the other says "re-notify every five minutes".

The alert is also indistinguishable from its predecessor — same subject, same body, same advice — so
83 copies carry exactly as much information as one, while burying anything else the owner is sent.

**The underlying Gmail token expiry is NOT this task.** The advice in the email body is correct, and
the owner has to run `gmail_oauth_setup` and publish the OAuth consent screen themselves. This task is
only about the app sending 83 emails to say one thing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A persistent unhealthy condition produces at most one email per day by default, not one per five minutes — stated as a named setting with its own default, not shared with `ERROR_ALERT_COOLDOWN_SECONDS`
- [ ] #2 The cooldown is proven by test to suppress the second alert inside the window and to allow one after it, using a controlled clock rather than a sleep
- [ ] #3 A transition matters more than a repeat: recovery is not silent — state what the owner sees when the check starts working again, or state deliberately that nothing is sent and why
- [ ] #4 A DIFFERENT failure reason within the window is not swallowed by a cooldown keyed only on "some alert was sent" — either the key distinguishes reasons, or the notes state why one alert for any reason is correct
- [ ] #5 TASK-160's guarantees still hold: the alert never raises, still routes through `settings.ADMINS`, and an unconfigured recipient list is still a no-op rather than a crash
- [ ] #6 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The cooldown mechanism itself is sound and should be kept: `cache.add()` is atomic and the cache is
`DatabaseCache`, so it is shared across workers and processes — the docstring's reasoning about why
that beats a per-process dict is still right. Only the duration and the key are wrong.

Do not fix this by raising `ERROR_ALERT_COOLDOWN_SECONDS`. That setting is TASK-88's, it governs
ordinary error alerting, and lengthening it would silence unrelated alerts that legitimately want a
short floor.

Consider whether the hours counter in the body earns its place. It is the only text that varies
between the 83 messages, and a subject line identical across all of them is what made the thread
collapse into noise; a subject that says how long it has been broken would at least let the owner see
escalation at a glance.
<!-- SECTION:NOTES:END -->
