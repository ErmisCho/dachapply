---
id: TASK-85
title: Add funnel conversion and source-effectiveness analytics
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 14:30'
labels:
  - product
  - analytics
  - backend
  - frontend
dependencies:
  - TASK-75
  - TASK-76
priority: medium
ordinal: 90000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The entire stats payload is status counts, average fit score, pace buckets, and a follow-up count (backend/jobradar/views.py:688-719). Nothing is cross-status and nothing is per-source: no applied→interview or interview→offer rates, no time-to-response, and the `source` field (models.py:50) is never aggregated.

The seeker can see how much they are applying but never what converts — which channels, which fit-score bands, which kinds of role actually produce interviews.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Stats include funnel conversion: applied→interview and interview→offer rates, over all time and a recent window
- [x] #2 Stats include per-source effectiveness: applications and interview rate grouped by source
- [x] #3 The dashboard renders both without a new page (a panel or an extension of the stats section)
- [x] #4 Backend tests pin the rate arithmetic on a small fixture
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Blocked by TASK-75 (offer status must exist) and TASK-76 (a permanent applied date — without it the denominators are wrong, which is precisely the bug TASK-76 fixes). Plain aggregation in the existing stats view; no charting library needed for v1 — numbers with small bars beat a chart dependency.

### Progress (2026-08-16) — backend landed in Wave 4, AC3 panel is Wave 5

Left **In Progress**: AC3 asks the dashboard to render this, and no frontend work has been done.

`/api/stats/` gained two top-level keys. Live payload from the verification stack:

    "funnel": {
      "recent_window_days": 90, "recent_window_start": "2026-05-18",
      "all_time": {"applications":5,"interviews":3,"offers":3,
                   "applied_to_interview_rate":60.0,"interview_to_offer_rate":100.0},
      "recent":   {…same shape…},
      "interviews_without_application": 3
    },
    "source_effectiveness": [{"source":"","applications":5,"interviews":3,"interview_rate":60.0}]

Three definition decisions, all of which change the numbers and none of which the ticket settled:

- **Denominator is the `applied_at` cohort, never current status.** A job now in `rejected` still
  applied. Using current status is precisely the bug TASK-76 existed to fix.
- **"Reached interview" is the journey, not the column**: `status in (interview, offer, accepted)`
  OR `interview_stage` set OR `interview_at` set. Counting only `status='interview'` would
  systematically undercount exactly the jobs that converted best — the ones that moved past it.
- **"Reached offer" is `status in (offer, accepted)`.** Known gap, recorded rather than hidden: a
  job rejected *after* an offer leaves no trace, so this undercounts. Closing it needs an `offer_at`
  stamped write-once the way `applied_at` is — a separate task, not silent invention.

`REACHED_OFFER` is a subset of `REACHED_INTERVIEW`, so `interview_to_offer_rate` cannot structurally
exceed 100%.

**The trap the brief called out is handled and measured.** A job whose status was set straight to
`interview` has no `applied_at`, and would otherwise produce a numerator larger than its
denominator. Such jobs are excluded from both and surfaced separately as
`funnel.interviews_without_application` — not dropped silently. The coordinator re-derived the live
numbers by hand against the seeded data: 5 applications, 3 reached interview (60%), 3 reached offer,
and exactly the 3 interview-only rows reported as `interviews_without_application`. Rates are `null`
rather than `0.0` when a denominator is zero, so "nothing to measure yet" cannot render as "you
convert nothing".

Note for whoever builds the panel: `funnel.offers` (3, jobs that *reached* offer) and the flat
`stats.offers` (2, jobs *currently* in offer) are different measures that share a word. Do not
render them as if they were the same number.

Wave 5 owes: a funnel panel in the existing stats section (no new page, no charting dependency),
a source table rendering `source: ""` as "Unknown source" since the backend emits it raw, a `null`
rate shown as "—" and never "0%", and a one-line hint when `interviews_without_application > 0` —
otherwise the funnel under-reports and the user has no way to know why.

### Closed 2026-08-16 - AC3 landed in Wave 5

Two panels in the existing panel grid: no new page, no charting dependency, both hideable and
reorderable through the Panels menu. Measured on the live board against the API they render:

    API  all_time {applications:5, interviews:3, offers:3, applied->interview 60%, interview->offer 100%}
    panel "CONVERSION FUNNEL | ALL TIME | 5 APPLICATIONS | 3 REACHED INTERVIEW | 3 REACHED OFFER
           | Applied -> interview: 60% | Interview -> offer: 100%
           | LAST 90 DAYS (SINCE 2026-05-18) | ...same shape...
           | 3 jobs reached interview with no application date, so they are left out of these
             rates. Set an application date on them to ..."

The tiles are labelled **"Reached interview" / "Reached offer"**, which is what stops
`funnel.offers` (3, jobs that reached offer) being read as the flat `stats.offers` (2, jobs
currently in offer) - the naming collision flagged when the backend landed.

The `interviews_without_application` hint renders, so the funnel cannot quietly under-report without
the user being told why.

Source table measured:

    SOURCE | APPLICATIONS | REACHED INTERVIEW | INTERVIEW RATE
    Unknown source | 5 | 3 | 60%

so the raw empty-string bucket the backend emits on purpose is labelled rather than shown as a blank
row, and the headers are real scoped table headers.

One thing verified by unit test rather than in the browser, and said plainly: a `null` rate must
render as an em dash and never "0%". The seeded data has no zero denominators, so there was no null
to render; `ratePercent` is covered by its own test instead.
<!-- SECTION:NOTES:END -->
