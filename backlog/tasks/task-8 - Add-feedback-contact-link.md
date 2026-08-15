---
id: TASK-8
title: Add feedback/contact link
status: Done
assignee:
  - '@claude'
created_date: '2026-06-20 09:51'
updated_date: '2026-06-20 09:54'
labels:
  - P1
  - ux
  - product
  - phase-2
milestone: m-2
dependencies:
  - TASK-1
priority: medium
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Small beta users need an easy way to report confusion, bugs, or feature requests.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1: a Feedback entry now appears in two places, because the desktop nav row is `hidden ... sm:flex`
and would have left the link invisible on a phone - which is where "visible on authenticated pages"
would have quietly failed. It is in the desktop nav row AND in the profile dropdown, which is
reachable at every width.

AC2: settings.FEEDBACK_URL, read from the FEEDBACK_URL env var and surfaced through /api/auth/me/.
Any destination works - a form, an issue tracker - and it defaults to a mailto for
CODEX_CV_OWNER_EMAIL so the link is never dead. The client renders nothing when it is empty.

AC3: a mailto opens the user's own mail client with an empty body, so no job, evaluation or profile
content is transmitted unless the user types it. The /api/auth/me/ payload carries a destination
string only. test_me_exposes_a_feedback_destination_without_leaking_job_data asserts both halves:
that the destination is present and configurable, and that the response body contains none of
raw_description, company, evaluations, job_id or notes.

Note on rollout: the client reads the user object from localStorage, so the link appears once
/auth/me/ refreshes it on the next page load - it will not show for an already-open tab.
<!-- SECTION:NOTES:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Authenticated pages include a visible feedback/contact entry
- [x] #2 Feedback destination is configurable or documented
- [x] #3 No private job data is sent automatically without consent
<!-- AC:END -->
