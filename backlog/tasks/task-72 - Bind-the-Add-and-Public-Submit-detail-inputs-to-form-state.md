---
id: TASK-72
title: Bind the Add and Public-Submit detail inputs to form state
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 11:45'
labels:
  - frontend
  - bug
dependencies: []
priority: high
ordinal: 77000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In JobForm (frontend/src/App.tsx:107) the Company, Title, Location, Salary, Language, Source, and "Your name" inputs have `onChange` but no `value` binding — only the URL/description/reason textareas are bound. Verified 2026-08-16: the file contains one bound `placeholder="Company (optional)" value={job.company}` (EditableJobDetails) and one unbound `placeholder="Company (optional)" onChange=` (JobForm).

Consequence: when a draft is restored from localStorage or the bookmarklet prefills `title` (App.tsx:102), the form state carries values the inputs display as empty — the user submits data they cannot see or correct. Affects both /add and /public-submit, the flow friends use.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every JobForm input reflects the current form state: a prefilled or restored value is visible in its input and editable
- [x] #2 Bookmarklet prefill shows the title in the Title input
- [x] #3 Restoring a saved draft shows every restored field, not just the textareas
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Add `value={...}` per input; the state already exists and the textareas prove the pattern. No new state, no new components.

### Closing notes (2026-08-16)

Eight controls gained a `value` binding: Company, Title, Location, work-mode `<select>`, Salary info,
Language requirements, Source, and "Your name". With the three already-bound textareas and the
read-only quick-prompt textarea, every control in JobForm is now bound — a re-run of the
value/no-value scan over the JobForm line returns zero unbound controls.

AC1/AC3 measured in a real browser (Playwright against a local sqlite backend), not reasoned from
the code. A full draft was written to `dachapply_add_job_draft`, the page reloaded, and each input
read back:

    company="Draft Co" | title="Draft Title" | location="Graz" | salary_info="70k"
    language_requirements="German B2" | source="linkedin" | work_mode="remote"

and the same on `/public-submit` via `dachapply_public_submit_draft`, where "Your name"
(`submitted_by`) also restored correctly. The `Source` input is not rendered in public mode, which
is existing intended behaviour, not a missed binding.

The binding was then checked in the other direction — a bound `value` whose `onChange` does not
update state would be a worse bug than the original. Every input was typed into and read back:
all six on `/add` and all six present on `/public-submit` reported `editable`, none `FROZEN`.

AC2 measured by loading the exact URL the bookmarklet builds
(`/add?url=…&title=Senior+Platform+Engineer+%28m%2Fw%2Fd%29&selected_text=…`); the Title input read
back `"Senior Platform Engineer (m/w/d)"`.

Observation, not a defect: `/public-submit` does not honour the same query-string prefill (the Title
input stays empty there). The bookmarklet targets `/add` only, so no acceptance criterion depends on
it; noted here in case a future task wants friends to share prefilled links.
<!-- SECTION:NOTES:END -->
