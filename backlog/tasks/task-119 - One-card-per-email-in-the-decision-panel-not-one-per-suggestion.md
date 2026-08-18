---
id: TASK-119
title: One card per email in the decision panel, not one per suggestion
status: Done
assignee:
  - '@claude'
labels:
  - frontend
  - mailbox
  - bug
dependencies:
  - TASK-117
priority: high
ordinal: 119000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-18: *"I see in the email decisions multiple emails for the same company/position
to send, there should be one."*

Correct, and it is a defect in TASK-117. The panel renders one card per **suggestion**
(`App.tsx`, `mailboxSuggestions.map(s => <MailboxSuggestionCard …/>)`), but one email routinely
produces two: `build_suggestions` (`mailbox.py:800-802`) adds a `feedback_clear` alongside the
`status_change`/`interview_date` whenever the job has a feedback clock running. Everything in
`MailboxSuggestionCard` except the single action line comes from `s.message`, so the sender, the
subject, the whole email body and the entire drafted reply are repeated verbatim, with two
identical-looking "Yes, apply this to Acme GmbH" buttons that do different things.

Observed in the browser during TASK-117 verification, and mistaken at the time for normal output:

    Acme GmbH — ERP Consultant: Clear the waiting-for-feedback clock
      [ Yes, apply this to Acme GmbH ]  [ No ]
    Acme GmbH — ERP Consultant: Set interview date to 25.08.2026 and move status to Interview
      [ Yes, apply this to Acme GmbH ]  [ No ]

Two cards, one email, the body printed twice.

The same repetition exists on the older `/mailbox` page (`MailboxReview`), which has its own inline
markup and does not use the shared card at all.

`JobMailboxTrigger` already receives the grouped shape from `GET /api/jobs/{id}/mailbox/` — messages
with `suggestions` nested — and deliberately flattens it with `.flatMap(m => m.suggestions)` to fit
the current one-suggestion-in prop. That flatMap is the seam: one call site already has what the
other needs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 One email renders as ONE card wherever pending suggestions are shown: the dashboard panel, the per-job row popup, AND the `/mailbox` page. The sender, subject, date, body and drafted reply appear exactly once per email, verified in a browser against a message carrying two pending suggestions
- [x] #2 The card lists every change that email proposes, each in its own words via `mailboxSuggestionSummary`, so nothing that was previously visible is lost by grouping
- [x] #3 The owner can accept the whole email's proposals with one action, and can still act on a single proposal independently — accepting the interview date without clearing the feedback clock must remain possible, since the backend models them as separate confirmable rows
- [x] #4 Each action still maps to exactly one `POST /api/mailbox-suggestions/{id}/confirm|dismiss/` call per suggestion; no new backend endpoint, and no client-side batching that could half-apply and leave the rest pending without saying so
- [x] #5 The busy/disabled state is per-card-action rather than a single global id, so confirming one proposal does not appear to freeze an unrelated email's buttons
- [x] #6 `JobMailboxTrigger`'s `.flatMap(m => m.suggestions)` is removed rather than worked around — both call sites pass the same grouped shape to the same component
- [x] #7 `npx tsc --noEmit` and `npm test` clean; the grouping itself is a pure function in `appUtils.ts` with its own test, since it is the part that can silently regress
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`MailboxSuggestion.message` is a full nested copy per suggestion (`serializers.py:323`), so grouping
client-side by `s.message.id` is safe and needs no backend change. That is the lazy correct fix:
`GET /api/jobs/{id}/mailbox/` already returns the grouped shape, so only the dashboard panel's
`/mailbox-suggestions/` list needs regrouping, and the component's props change from
`{s}` to `{m, suggestions}`.

AC3 is the one worth thinking about rather than assuming. Grouping the display must not group the
decision: a rejection whose status change is right but whose feedback-clock clear is not is a real
case, and the backend deliberately keeps them as separate `MailboxSuggestion` rows applied one at a
time through `apply_suggestion`. Per-proposal controls inside one card satisfy both halves; a single
Yes that fires N confirms is acceptable ONLY if a per-proposal route also exists.

Do not fix this by changing `build_suggestions` to emit one combined suggestion. The split rows are
what make partial acceptance possible, and merging them would mean a payload that applies two
unrelated changes atomically with no way to refuse half.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-18)

`groupMailboxSuggestions` (pure, in `appUtils.ts`, 7 new tests) groups a flat suggestion list by
`s.message.id`; `MailboxSuggestionCard` went from `{s, busy, onDecide}` to
`{m, suggestions, busyId, onDecide}`. All three call sites now render the grouped shape: the
dashboard panel, `JobMailboxTrigger`'s popup, and the `/mailbox` page, which previously had its own
inline per-suggestion markup and now uses the shared card.

MEASURED in a browser, not read off the JSX:

- **AC1** — the email body appears exactly **once** where it previously appeared twice, on the
  dashboard panel and on `/mailbox`. (`hr@acme.test` shows a second time on `/mailbox` only in the
  pre-existing run digest below, which is a different component.)
- **AC3** — clicking *Yes* on "Clear the waiting-for-feedback clock" alone left the interview-date
  proposal pending: `pendingBefore [3 feedback_clear, 2 interview_date]` → `pendingAfter
  [2 interview_date]`. Partial acceptance survives grouping, which was the point.
- **AC4** — exactly one request: `POST /api/mailbox-suggestions/3/confirm/ 200`. No batching endpoint.
- **AC5** — with two emails pending, clicking Acme's *Yes* disabled Acme's button while Formunauts'
  stayed enabled for the whole in-flight window (sampled every 100ms). The agent found and fixed a
  real bug here mid-build: the accept-all button originally tested the shared `busyId !== null`,
  which would have frozen every card whenever any suggestion anywhere was busy.
- **AC6** — the only `flatMap` left in `App.tsx` is inside a comment recording that it was removed.

`npx tsc --noEmit` clean, 52 frontend tests pass.
