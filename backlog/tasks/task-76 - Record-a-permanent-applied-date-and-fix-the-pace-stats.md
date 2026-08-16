---
id: TASK-76
title: Record a permanent applied date and fix the pace stats
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 11:45'
labels:
  - product
  - backend
  - data
dependencies: []
priority: high
ordinal: 81000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`status_date` is a single overwritable field (backend/jobradar/models.py:59 — verified 2026-08-16) that is re-set on every dated transition: applied → interview → rejected each prompt a fresh date (frontend datedStatuses, App.tsx:10).

Consequences for the stats the owner reads daily: the pace buckets count any job with a status_date (views.py:691 filters only `status_date__isnull=False`), so a rejection dated this week counts as "an application this week"; and `applications_sent` counts only jobs *currently* in applied (views.py:719), so every application that progressed to interview or rejection silently leaves the total. The pace numbers are quietly wrong in both directions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An applied_at date is recorded when a job first enters applied and is never overwritten by later transitions
- [x] #2 Pace buckets count by applied_at, and applications_sent counts every job that ever entered applied regardless of current status
- [x] #3 A data migration backfills applied_at where derivable (jobs currently in applied with a status_date); the unknowable historical cases are named in the closing notes, not guessed
- [x] #4 A backend test walks applied → interview → rejected and asserts exactly one application counted, in the week the apply happened
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Keep status_date as-is — it correctly means "date of the last transition" and the UI uses it that way. applied_at is one nullable DateField set in the status-change path only when previous status was pre-applied and new status is applied.

### Closing notes (2026-08-16)

The write-once guard lives in `JobLead.save()`, not only in the serializer, because the serializer is
not the only writer — demo seeding, JSON import and `_assign_fields` all reach the DB through
`save()`. One line covers every caller and is inherently write-once:

    if self.status=='applied' and not self.applied_at:
        self.applied_at = self.status_date or timezone.localdate()

Deriving from `status_date` rather than "today" means a backdated apply
(`PATCH status=applied, status_date=2026-01-05`) records the real day.

`status_date` keeps its old meaning untouched. A `DATED_STATUSES` constant on the model replaced the
five copies of the `['applied','interview']` literal that had been drifting across
`serializers.py` and `views.py` — that mirrored-literal drift is the same class of bug this task
exists to fix. `applied_at` was also added to `job_replace.REPLACE_FIELDS` (an overridden duplicate
must reset to a fresh lead, or it keeps counting as an application sent), to
`user_data_portability.JOB_FIELDS` (so the export/import round-trip does not silently drop it), and
to the demo seed rows (without it the demo dashboard read "1 application sent, 4 interviews").

AC2/AC4 are pinned by tests that fail against the old code:
`test_stats_count_one_application_for_a_job_walked_to_rejection` walks applied → interview →
rejected through the API and asserts the job ends `rejected` with `status_date is None` yet
`applications_sent == 1`, `applications_this_week == 1`, and the whole weekly series sums to 1 with
the count landing in the apply week. `test_applied_at_survives_later_transitions_and_reentry`
covers re-entry: applied → rejected → applied again leaves `applied_at` at the original date while
`status_date` moves. Suite: **167 passed** (161 baseline + 6 new).

One pre-existing test was deliberately changed rather than worked around:
`test_stats_include_application_pace` had a fixture row that only satisfied its own assertion
*because* of the bug — a rejection dated this week was being counted as an application. The
assertion (`applications_this_week == 3`) is unchanged; the fixture now gives the interviewing job an
`applied_at`, so the same 3 are three real applications and the rejection no longer counts.

Both migrations were confirmed to apply cleanly against a real database, not only an empty test one.

**Caveat for TASK-85 (funnel analytics):** a job moved straight to `interview` without ever passing
through `applied` gets no `applied_at` and is correctly not counted as an application — which is
what AC2 asks for, but it means an interview-rate denominator can be smaller than its numerator for
such rows. Worth handling explicitly when the funnel rates are built.

### Historical cases that could not be backfilled

`applied_at` was backfilled only for jobs still sitting in `applied` with a `status_date`, because
for those rows the last transition *was* the application. Four classes cannot be recovered and were
left null rather than guessed:

1. **Jobs that already moved past applied** (interview, offer, accepted, rejected, withdrawn, or
   archived). Each later transition overwrote `status_date`, and there is no history table or audit
   trail anywhere in the schema — the original apply date is gone. `created_at` is when the lead was
   captured, not when it was applied to, so it is not a substitute.
2. **Jobs currently in `applied` with `status_date` null** (imported rows, or rows whose date was
   cleared). There is no date to copy.
3. **Jobs that went into `applied` and then back to a pre-applied status.** The serializer clears
   `status_date` on that transition, so nothing remains.
4. **Repeat applications to the same job.** Only the most recent is ever derivable; an earlier
   apply-reject-reapply cycle leaves no trace. Going forward `applied_at` records the *first* entry.

Practical effect: pace charts and `applications_sent` under-count any application that had already
progressed past `applied` before this migration. The field is writable through the jobs API
(`PATCH /api/jobs/<id>/ {"applied_at": "YYYY-MM-DD"}`), so those rows can be corrected by hand where
the date is remembered. There is no UI for that correction.
<!-- SECTION:NOTES:END -->
