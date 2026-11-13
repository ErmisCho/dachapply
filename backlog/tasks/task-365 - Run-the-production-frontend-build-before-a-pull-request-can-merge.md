---
id: TASK-365
title: Run the production frontend build before a pull request can merge
status: Done
assignee: []
created_date: '2026-11-11 14:46'
labels:
  - frontend
  - ci
dependencies: []
priority: medium
type: chore
ordinal: 365000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The PR test job currently runs npm ci, npx tsc --noEmit and npm test, but not npm run build. Container builds run only on manual deployment. A bundling failure can therefore pass normal merge checks. Add production-build coverage to the existing required PR gate without weakening tests, changing deploy permissions or triggering deployments. Any CI-gate change requires owner approval before merge under CLAUDE.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The required pull-request check runs the real production frontend build from the committed lockfile, and a bundling failure fails that required check.
- [x] #2 Existing frontend tests and TypeScript validation remain covered; avoid redundant separate typechecking if the canonical production build already performs it.
- [x] #3 No deployment is triggered by opening/merging a PR and manual deployment gates remain intact.
- [x] #4 A known-invalid bundling input is demonstrated to fail the check, while the normal project build passes; owner approval is obtained before merging any CI-gate change.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-13 (coordinator): verified: PR CI runs npm run build; a throwaway missing-CSS import failed run 43229343068 at "Frontend production build", clean branch passed; deploy stays workflow_dispatch; owner approved before merge (PR 400).
<!-- SECTION:NOTES:END -->
