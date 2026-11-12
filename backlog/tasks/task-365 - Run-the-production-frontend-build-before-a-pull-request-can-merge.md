---
id: TASK-365
title: Run the production frontend build before a pull request can merge
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-11 14:46'
updated_date: '2026-11-12 09:17'
labels:
  - frontend
  - ci
dependencies: []
modified_files:
  - .github/workflows/deploy-container-apps.yml
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
- [ ] #1 The required pull-request check runs the real production frontend build from the committed lockfile, and a bundling failure fails that required check.
- [ ] #2 Existing frontend tests and TypeScript validation remain covered; avoid redundant separate typechecking if the canonical production build already performs it.
- [ ] #3 No deployment is triggered by opening/merging a PR and manual deployment gates remain intact.
- [ ] #4 A known-invalid bundling input is demonstrated to fail the check, while the normal project build passes; owner approval is obtained before merging any CI-gate change.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Replace the redundant standalone typecheck step with npm run build, which runs tsc and Vite after npm ci. Keep frontend tests and manual deploy conditions unchanged. Falsify with a missing HTML-entry module; submit a separate draft PR and obtain explicit owner approval before merge.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Normal npm ci + npm run build passed. Falsification: adding a missing module entry to index.html left tsc passing (exit 0), but the production build failed (exit 1); original index bytes restored and SHA-256 verified. Existing frontend tests and workflow_dispatch-only deploy condition are unchanged. Owner approval is still required before this CI-gate change can merge.
<!-- SECTION:NOTES:END -->
