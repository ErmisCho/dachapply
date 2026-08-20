---
id: TASK-154
title: build_suggestions has no bulk-mail guard, and now it sees marketing text
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-114
  - TASK-152
priority: medium
ordinal: 154000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Surfaced 2026-08-20 by the TASK-152 implementation, which deliberately flagged it rather than
quietly widening a guard's call sites inside a bugfix.

`bulk_mail_reason()` — the guard TASK-114 built so the app never drafts a reply to a newsletter or
an automated blast — is called at the top of `maybe_draft_reply()`. It reads headers only
(`List-Unsubscribe`, `Precedence: bulk`, `Auto-Submitted`, no-reply sender), so it is fast and
robust, and it protects the thing that matters most: nothing is ever written into Gmail Drafts for
bulk mail.

`build_suggestions()` has **no such guard**. Its only gate is the job-status one TASK-143 added.
What it produces is an in-app `MailboxSuggestion` — a proposed status change the owner sees on the
board and can accept with one click. Meanwhile `_classify_heuristic()` reads `body_text`, and three
of its keyword categories (`offer`, `rejection`, `interview_invitation`, `application_confirmed`)
fire regardless of whether the sender's domain is known.

This was already reachable before TASK-152 (a subject line alone could do it), but TASK-152 widened
the practical surface: messages whose Gmail copy is HTML-only used to store an EMPTY body and now
store real text. So a company that sends both genuine recruiter mail and HTML-templated marketing
from the same tracked domain can now produce a false suggestion from the marketing mail's body.

The failure is bounded — a suggestion is reviewable and reversible, and no draft is written — but it
is exactly the class of wrongness TASK-137 exists to prevent: a plausible-looking proposal attached
to the wrong message.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A message that `bulk_mail_reason()` identifies as bulk produces NO suggestion, asserted by test with a fixture carrying each of the bulk markers in turn
- [ ] #2 The refusal is counted and explained the way TASK-114 made drafting refusals explicit, not skipped silently — an owner asking "why did this not turn up" can find the reason
- [ ] #3 Genuine recruiter mail that happens to carry one bulk-ish header is not lost without a trace: state the chosen precedence rule explicitly and test it (an ATS that sets `Auto-Submitted` on real application confirmations is the realistic collision — TASK-136 recovered 138 of those)
- [ ] #4 The existing draft-side guarantee is untouched: `maybe_draft_reply()` still refuses bulk mail for the same reasons and with the same reporting
- [ ] #5 Measured against the real mailbox: how many currently-stored messages would newly be refused a suggestion under this rule, and a spot-check of at least three of them confirming each really is bulk
- [ ] #6 Backend suite green; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The cheap shape is to call the same `bulk_mail_reason()` at the top of `build_suggestions()` and
record the reason on the run the way the drafting path already does — one guard, two call sites, no
second rule to keep in sync. AC3 is the trap: refusing every `Auto-Submitted` message would throw
away application confirmations, which are the single largest class TASK-136 recovered. Decide
deliberately whether the suggestion side needs a narrower marker set than the drafting side, and
write the decision down rather than inheriting the drafting list by accident.
<!-- SECTION:NOTES:END -->
