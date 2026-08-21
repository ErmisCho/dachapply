---
id: TASK-172
title: The Mailbox page takes 36 seconds to load
status: To Do
assignee: []
labels:
  - backend
  - performance
  - mailbox
  - bug
dependencies: []
priority: high
ordinal: 172000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report, 2026-08-21: */mailbox* *"is forever loading here"*, with the page's "Loading..."
placeholder screenshotted.

It is not hung. Measured from the owner's own browser against `localhost:8000`:

    /api/mailbox-suggestions/          200      704 ms       18,907 bytes
    /api/mailbox-runs/                 200   35,831 ms    1,271,114 bytes   <-- this one
    /api/mailbox-health/               200      461 ms           15 bytes
    /api/mailbox-messages/unmatched/   200      578 ms       34,234 bytes

**Root cause.** `MailboxRunSerializer.get_digest_messages` serializes every job-related message of
every run with the FULL `MailboxMessageSerializer`:

    def get_digest_messages(self, obj):
        rows = obj.messages.exclude(classification='not_job_related').order_by('-uid')
        return MailboxMessageSerializer(rows, many=True).data

`MailboxMessage.body_text` holds up to 5,000 characters per message (TASK-117 widened this model to
store bodies). With 13 runs covering ~1,000 stored messages, the endpoint ships every one of those
bodies in full, on a page that only renders a per-run digest.

This is the SAME defect TASK-142 already fixed one endpoint over. That task built
`MailboxMessageListSerializer` — a bounded `Substr` preview computed in SQL, with `.defer('body_text')`
so the column never leaves the database, plus `select_related('draft')` to kill a reverse-one-to-one
N+1 — and took `/unmatched/` from 13,006 ms to 756 ms. None of it was applied here. The machinery
exists and is simply not used by this serializer.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `/api/mailbox-runs/` responds in under 2 seconds against the production database — stated as a measured number, before and after
- [ ] #2 The response no longer carries full `body_text`: measured payload size is reported before and after, and no query in the request selects the unbounded column
- [ ] #3 The per-run digest still shows what it showed before — the same messages, in the same order, with enough text to be useful; a preview is acceptable, silently dropping messages is not
- [ ] #4 No N+1: the endpoint's query count does not scale with the number of runs or the number of messages per run, verified by counting queries rather than by reading the code
- [ ] #5 The reuse is explicit: `MailboxMessageListSerializer` (or a stated reason it cannot serve this case) rather than a second bounded-preview implementation
- [ ] #6 If the full body is genuinely needed for a run's digest, it is fetched on demand via TASK-142's existing `retrieve` action rather than shipped with the list
- [ ] #7 Verified in the owner's browser at `localhost:8000/mailbox`: the page renders its content without a visible "Loading..." stall, stated as a measured time
- [ ] #8 Backend suite green; frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Read TASK-142's comment block above the `unmatched` queryset in `views.py` before starting. It records
two rounds of measurement: truncating inside `to_representation()` was NOT enough, because Django had
already pulled every row's full `body_text` off the wire before that Python code ran — the truncation
has to happen in the SQL. Then a second round found the payload fixed but the wall-clock unchanged, at
320 queries, from a reverse one-to-one lazy load. Expect both failure modes here.
<!-- SECTION:NOTES:END -->
