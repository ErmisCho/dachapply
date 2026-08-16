---
id: TASK-91
title: Paginate or slim the jobs list response
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 14:30'
labels:
  - backend
  - frontend
  - performance
dependencies: []
priority: low
ordinal: 96000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
No DEFAULT_PAGINATION_CLASS exists (backend/config/settings.py:130-144) and JobLeadViewSet sets none (views.py:295-328), so `/api/jobs/` returns every non-archived job — each row carrying full `raw_description`, `original_source_text`, and a complete nested evaluation (serializers.py:131-139, `fields='__all__'`). The dashboard then renders every row twice (mobile cards + table) in one un-memoized component, so each selection click re-renders all rows (App.tsx:98); Prompts loads all jobs too (App.tsx:129).

Fine at today's scale; after a year of active searching, the board's first paint grows in proportion to lifetime history. Low priority now, filed so the fix happens by choice rather than during an outage.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Either the list payload no longer carries raw_description/original_source_text per row (detail fetch keeps them), or the endpoint paginates and the frontend follows — one of the two closes this task
- [x] #2 The payload reduction is measured and recorded (bytes before/after for the same data set)
- [x] #3 Board behaviour (filters, selection, optimistic updates) is unchanged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Slimming the list serializer is the lazy fix — a dedicated list serializer without the two big text fields avoids touching frontend pagination entirely, and the detail view already fetches per-job. Pagination can wait until slimming measurably stops being enough.

### Closing notes (2026-08-16)

Took the slimming route, not pagination - pagination would have required frontend changes in a file
owned by a parallel agent, and the detail endpoint already serves per-job. `JobLeadListSerializer`
is wired only to `action == 'list'`; retrieve, create, update and the bulk/duplicate paths keep the
full serializer.

AC1 verified against the live API: list rows carry neither `raw_description` nor
`original_source_text`, while `/api/jobs/<id>/` still returns both.

AC2 measured on real data, all three numbers recorded because they say different things:

    26-row local snapshot (text fields ~35,700 chars each, all rows evaluated)
      before 356,464 bytes -> after 161,290 bytes   = -195,174 (-54.8%)
        of which dropping the two text fields   -20.4%
        of which slimming the nested evaluation -34.3%   <- the bigger half
    hermetic test fixture (12 seeded rows)
      135,074 -> 12,803 bytes = -90.5%
    coordinator's 14-row scratch DB (4-character descriptions)
      12,235 -> 10,791 bytes = -11.8%

The scratch-DB figure is included deliberately: the saving scales with how much text each row
carries, so a tiny fixture understates it. The 26-row snapshot is the representative one, and it is
the shape of data this task was filed to anticipate.

The nested evaluation turned out to be the larger win, almost entirely `structured_json_raw` - the
raw LLM reply, which no frontend file reads at all. Eleven evaluation fields are kept (the ones the
board, `MatchGapPopup` and `SkillLabels` actually render); `skill_statuses` is still computed
server-side, so it keeps covering nice-to-have skills even though that list is no longer sent.

**AC3 initially failed, and the agent that caused it said so rather than shipping the win.**
`BatchCvGenerator` rendered the source text from board list rows, so slimming turned every source
preview into "No source text stored." It was reported as NOT MET with the exact one-line fix, which
belonged to the frontend agent's file and was applied in the same wave. Verified afterwards:

    per-row detail fetches issued: /api/jobs/2/, /api/jobs/3/
    source preview text: "desc"   <- the real stored text, not the fallback

Also confirmed unchanged: `?search=` and `?skill=` still match on those columns (3, 1 and 3 rows on
the scratch data) because only the response omits them - the SQL still queries them; and PATCH
responses still return the full payload (20 evaluation fields against the list's 11), so the
optimistic-update path that swaps the response into the row is unaffected.

Flagged, not filed: `?skill=` and `?search=` do unindexed `icontains` scans over those same two big
columns. Irrelevant to payload size, but it is the next thing that will hurt at the scale this task
anticipates.
<!-- SECTION:NOTES:END -->
