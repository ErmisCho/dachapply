---
id: TASK-172
title: The Mailbox page takes 36 seconds to load
status: Done
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
- [x] #1 `/api/mailbox-runs/` responds in under 2 seconds against the production database — stated as a measured number, before and after
- [x] #2 The response no longer carries full `body_text`: measured payload size is reported before and after, and no query in the request selects the unbounded column
- [x] #3 The per-run digest still shows what it showed before — the same messages, in the same order, with enough text to be useful; a preview is acceptable, silently dropping messages is not
- [x] #4 No N+1: the endpoint's query count does not scale with the number of runs or the number of messages per run, verified by counting queries rather than by reading the code
- [x] #5 The reuse is explicit: `MailboxMessageListSerializer` (or a stated reason it cannot serve this case) rather than a second bounded-preview implementation
- [x] #6 If the full body is genuinely needed for a run's digest, it is fetched on demand via TASK-142's existing `retrieve` action rather than shipped with the list
- [x] #7 Verified in the owner's browser at `localhost:8000/mailbox`: the page renders its content without a visible "Loading..." stall, stated as a measured time
- [x] #8 Backend suite green; frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-23 close-out - 35.83 s -> 0.76 s, measured against production

    metric                          before        after
    wall clock                     35.83 s       0.76 s      (47x)
    payload                     1,271,114 B    686,655 B
    queries                              -           10, flat
    queries selecting full body_text     -            0

All 13 runs still return their digests, and every run's message ids match the database's own
`-uid` order exactly (checked run by run, 472 digest messages total). Bodies are bounded to the
301-char preview with `body_truncated` set. Nothing was dropped to buy the speed.

The fix reuses TASK-142's machinery rather than a second implementation: a `_digest_queryset()`
helper carrying the `Substr` preview + `.defer('body_text')` + `select_related`, consumed by a new
`MailboxRunListSerializer` that batches EVERY run's digest into ONE query (`run_id__in=[...]`) and
groups in Python, instead of one query per run. `select_related('matched_job')` is the one addition
beyond `/unmatched/`'s shape -- that endpoint can skip it because it filters `matched_job__isnull=True`,
while a run's digest carries real matched jobs routinely.

**A second defect was found while verifying, and is worth recording.** `MailboxRunViewSet.get_queryset()`
still chains `.prefetch_related('messages__matched_job','messages__draft')`, written for the old
`get_digest_messages`. It never worked even then -- a filtered `.exclude().order_by()` on a related
manager bypasses Django's prefetch cache entirely -- but it fires unconditionally the moment the run
queryset is evaluated and pulls every stored message's full `body_text` into the app server. The list
path now neutralises it with Django's own `prefetch_related(None)` reset. The DETAIL action
(`GET /api/mailbox-runs/<id>/`) still pays for it, because it fires inside `get_object()` before any
serializer runs. That is a one-line removal in `views.py`, left out of this change only because
`views.py` belonged to another agent's territory this wave.

Read TASK-142's comment block above the `unmatched` queryset in `views.py` before starting. It records
two rounds of measurement: truncating inside `to_representation()` was NOT enough, because Django had
already pulled every row's full `body_text` off the wire before that Python code ran — the truncation
has to happen in the SQL. Then a second round found the payload fixed but the wall-clock unchanged, at
320 queries, from a reverse one-to-one lazy load. Expect both failure modes here.
<!-- SECTION:NOTES:END -->
