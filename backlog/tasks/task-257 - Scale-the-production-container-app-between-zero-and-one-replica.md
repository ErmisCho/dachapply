---
id: TASK-257
title: Scale the production container app between zero and one replica
status: In Progress
assignee:
  - '@pi'
created_date: '2026-10-01 08:44'
updated_date: '2026-10-01 08:53'
labels:
  - infrastructure
  - cost
dependencies: []
modified_files:
  - .github/workflows/deploy-container-apps.yml
priority: high
type: chore
ordinal: 255000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-10-01: reduce the recurring Azure Container Apps charge by allowing DACHApply to scale to zero when idle, cap it at one replica, and keep that range persistent across every deployment. Cold starts after idle periods are accepted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The production DACHApply container app is configured with a minimum of zero replicas and a maximum of one replica
- [ ] #2 Every repository-driven deployment reapplies the zero-to-one replica range so later releases cannot restore an always-on replica
- [ ] #3 After deployment the public application wakes successfully from zero and returns a healthy database response
- [ ] #4 The merged deployment workflow completes successfully and the live Azure configuration reports the requested replica bounds
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Change the canonical deployment command to enforce minReplicas=0 and maxReplicas=1.
2. Add a lightweight repository check that pins both flags so the cost setting cannot regress silently.
3. Run the focused workflow check and repository quality gates, then merge and let the main deployment apply the live Azure setting.
4. Verify the deployed app wakes successfully and inspect Azure for the live zero-to-one replica bounds.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Changed the canonical deployment command from an always-on minimum of one replica to min 0 / max 1. Local verification: deployment-block assertion passed, backend suite 1,243 passed, frontend production build passed, and git diff check passed.
<!-- SECTION:NOTES:END -->
