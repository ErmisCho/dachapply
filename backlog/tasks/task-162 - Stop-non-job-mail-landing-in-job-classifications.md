---
id: TASK-162
title: Stop non-job mail landing in job classifications
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - classification
dependencies:
  - TASK-161
priority: medium
ordinal: 162000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-21 while measuring TASK-161. The classifier puts mail that is not about a job
application into the classes that carry the strongest consequences.

Two of the six most recent messages classified as `rejection` or `interview_invitation` — the two
classes that, on attach, change a job's status outright — are not job mail at all:

    rejection             "Re: [Ticket#2026080110000112] Ersatzteil fuer PRINZ PZ-STM1"
                          a spare-parts support ticket
    interview_invitation  "You've got 3 unread messages"
                          a LinkedIn/Xing notification digest

This is worse than ordinary misclassification. `record_suggestions` turns `rejection` into
`{'status': 'rejected'}` and `interview_invitation` into an interview status plus a feedback-clock
clear. A false positive here does not merely add a row to a list — it offers the owner a one-click
action that would put a real job into a wrong state on the strength of a spare-parts email.

It also undermines TASK-161: ranking by consequence is only as good as the classification the rank
is computed from. TASK-161 is still worth shipping first (the ordering is right even when a few
inputs are wrong, and it surfaces these false positives instead of burying them), but the two
together are what make the panel trustworthy.

Note the shape of both examples: neither is an ATS or a recruiter. One is transactional support mail
that happens to contain refusal language, the other is a platform digest whose subject reads like an
invitation. A fix that only adds keywords will move the boundary rather than find it — the sender
and the message's relationship to any known application are the stronger signals, and
`_match_by_ats_display_name` and the ATS host-domain work (TASK-137) already exist to build on.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The two named messages — the `Ersatzteil`/Ticket support mail and the "You've got 3 unread messages" digest — no longer classify as `rejection` / `interview_invitation`, verified by re-running the classifier over those exact stored messages
- [ ] #2 A measured false-positive rate is reported before and after, over a stated sample of production messages, rather than a claim that it "looks better" — state the sample size and how the ground truth was decided
- [ ] #3 No regression on true positives: every message currently classified `rejection` or `interview_invitation` that IS genuinely a rejection or invitation still classifies that way, counted over the same sample
- [ ] #4 Platform notification digests (LinkedIn, Xing, Wellfound, Substack and the other non-ATS senders already visible in the unmatched data) are excluded on a basis that is not a subject-line keyword list, and the basis is named
- [ ] #5 The fix is defended against the case it exists for: a message that contains refusal or invitation language but has no relationship to any application does not reach a status-changing classification
- [ ] #6 Any message whose classification changes is re-classified in place rather than left stale, or the task states explicitly why historical rows are not re-run and what that means for the 321-row panel
- [ ] #7 Backend suite green, with a test per false-positive class that fails against the current classifier
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Filed alongside TASK-161 on the owner's instruction ("file both, build the ranking first"), so the
ordering work is not blocked on the classifier work. Do not fold them together.
<!-- SECTION:NOTES:END -->
