---
id: TASK-7
title: Polish friend submission flow
status: Done
assignee:
  - '@claude'
created_date: '2026-06-20 09:51'
updated_date: '2026-06-20 09:54'
labels:
  - P1
  - frontend
  - public-submit
  - ux
  - phase-2
milestone: m-2
dependencies:
  - TASK-1
priority: medium
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Friends submitting leads should need minimal explanation.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Scoped to the JobForm component in App.tsx. AC3 needed nothing: the subtitle already read "Paste a
link only, or add more details if you have them", which is exactly the intent, so it was left alone.

AC1: publicMode now gets its own "Sent" confirmation section, mirroring the existing private
"Job saved" pattern and naming the friend when known, plus a "Submit another link" action that
clears the draft through the existing helpers.

AC2 was the real gap and the interesting one. The banner never explained why no code is needed on
repeat visits. Before writing that copy, the mechanism was checked rather than assumed: grepping
`invite` in App.tsx returns ZERO hits - the invite_code field belongs to the anonymous submit path
in views.py, which the authenticated /public-submit route never exercises. What actually persists is
profile.submit_for, set once in views.friend_requests when the friend approves. The banner now
describes that truthfully instead of describing an invite-code flow the UI does not have.

KNOWN IMPRECISION, pre-existing and not introduced here: a logged-in user with no friend relationship
who opens /public-submit directly becomes their own owner server-side, so the friend-framed copy
reads slightly oddly for that corner case. It matches the previous banner's behaviour, so this is
not a regression.
<!-- SECTION:NOTES:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Successful submission shows a clear confirmation
- [x] #2 Invite code persistence is explained
- [x] #3 URL-only submission feels intentional and not like an incomplete form
<!-- AC:END -->
