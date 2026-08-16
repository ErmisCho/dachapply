---
id: TASK-77
title: Let users create and act on follow-ups from the UI
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 12:40'
labels:
  - product
  - frontend
dependencies: []
priority: high
ordinal: 82000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The FollowUp model, the POST endpoint (backend/jobradar/views.py:373-376, plus FollowUpViewSet at 397-400), and the /followups list page (frontend/src/App.tsx:136) all exist — but no frontend code ever POSTs a follow-up. Grep across frontend/src finds only the GET and the `PATCH {completed:true}`; the only creator in the codebase is the demo seeder (services/demo_data.py:92).

So for real accounts, follow-ups can only be born through Django admin: the "Due follow-ups" dashboard panel is a dead number, and the panel itself renders a scalar with no link to the jobs behind it (App.tsx:41-42) — the dashboard says *that* something is due, never *what*.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A follow-up (due date + note) can be created from the job detail page
- [x] #2 The dashboard "Due follow-ups" panel links to the due items (the /followups page or a filtered list), not just a count
- [x] #3 Completing a follow-up continues to work as today
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Backend is done — this is a small form on job detail POSTing to the existing endpoint, plus wrapping the panel number in a Link. No new endpoints, no new models.

### Closing notes (2026-08-16)

A `JobFollowUps({jobId})` component modelled on the adjacent `JobNotes`, mounted in `Detail` right
after it. It GETs `/jobs/<id>/followups/` and POSTs `{follow_up_date, reason}` to the same existing
action — no new endpoint, no new model. Submit stays disabled until both fields are filled, the
note is capped at `maxLength={250}` to match `FollowUp.reason`, and a failed create runs through
`catch(error){setErr(error)}` into the existing `ErrorBox`, so this does not reintroduce the silent
failure class TASK-94 had just cleared out.

AC1 measured end to end in a browser against a local backend: filling the date and note enabled the
button, clicking it issued exactly `POST /api/jobs/2/followups/`, and the page rendered
`✓ Follow-up added.` with no unhandled rejection.

AC2 measured: the dashboard panel count is now a `Link` to `/followups`, and clicking it navigated
to `/followups`. The panel keeps its drag-to-reorder behaviour because the anchor is
`draggable={false}` — without that the anchor captures the drag.

The link's tap target was measured rather than assumed, and the first attempt failed: `min-h` alone
gave a **10×44px** target, since the anchor wraps only the digit. Adding `min-w-[2.75rem]` and
`justify-center` brings it to **44×44px at both 1400px and 375px**, which is the rule TASK-68
established. (`index.css` only auto-sizes `button/input/select`, not `a`.)

AC3: the `Followups` page itself is untouched — the diff contains only the new component, the panel
link, and the mount.

Not done, deliberately: no automated test. vitest here runs in plain node with no jsdom and no
testing-library, so a component test would mean a new dependency; and the alternative — exporting
the component from App.tsx — is banned because it costs Fast Refresh for the whole app (measured in
Wave 1). The browser evidence above stands in its place.
<!-- SECTION:NOTES:END -->
