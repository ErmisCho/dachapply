---
id: TASK-89
title: Set per-route browser tab titles
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 11:45'
labels:
  - frontend
  - ux
dependencies: []
priority: medium
ordinal: 94000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The tab always says "DACHApply" (frontend/index.html:8); no `document.title` write exists anywhere in frontend/src. The app's core workflow is constant tab-switching with ChatGPT (copy prompt → paste → copy response → import), so a wall of identical tabs costs real time many times a day.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each route sets a distinct title (e.g. "Board — DACHApply", "{company}: {title} — DACHApply" on job detail, "Import — DACHApply")
- [x] #2 The title updates on client-side navigation, including to job detail once the job has loaded
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A five-line useTitle hook (set on mount, restore nothing) called per page, or a route-table map in one place. No library.

### Closing notes (2026-08-16)

Implemented as the route-table variant: a `routeTitles` map, a four-line `useTitle` hook writing
`document.title`, and a `<RouteTitle/>` component mounted once in `App()` above `<Routes>`. Job
detail calls `useTitle` itself so it can override the generic "Job" once the job has loaded. No
dependency was added.

AC1 measured in a browser across seven routes — every one distinct:

    /              Board — DACHApply
    /add           Add job — DACHApply
    /import        Import — DACHApply
    /prompts       Prompts — DACHApply
    /followups     Follow-ups — DACHApply
    /export        Export — DACHApply
    /public-submit Submit a job lead — DACHApply
    /login         Sign in — DACHApply

AC2 measured two ways rather than assumed. First, a marker was set on `window`, an in-app link was
clicked, and both the title change and the marker's survival were read back: `"Board — DACHApply"` →
`"Export — DACHApply"` with the JS context preserved, which is what distinguishes a client-side
route change from a full document load. Second, clicking through to a job produced
`"Globex AG: Platform Engineer — DACHApply"` — the company and title come from the fetched job, so
the title demonstrably updated *after* the job loaded, not from the route alone.
<!-- SECTION:NOTES:END -->
