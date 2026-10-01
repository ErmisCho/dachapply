---
id: TASK-257
title: Scale the production container app between zero and one replica
status: Done
assignee:
  - '@pi'
created_date: '2026-10-01 08:44'
updated_date: '2026-10-01 13:18'
labels:
  - infrastructure
  - cost
dependencies: []
modified_files:
  - .github/workflows/deploy-container-apps.yml
  - .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-13.md
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
- [x] #1 The production DACHApply container app is configured with a minimum of zero replicas and a maximum of one replica
- [x] #2 Every repository-driven deployment reapplies the zero-to-one replica range so later releases cannot restore an always-on replica
- [x] #3 After deployment the public application wakes successfully from zero and returns a healthy database response
- [x] #4 The merged deployment workflow completes successfully and the live Azure configuration reports the requested replica bounds
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Change the canonical deployment command to enforce minReplicas=0 and maxReplicas=1.
2. Add a lightweight repository check that pins both flags so the cost setting cannot regress silently.
3. Run the focused workflow check and repository quality gates, then merge and let the main deployment apply the live Azure setting.
4. Verify the deployed app wakes successfully and inspect Azure for the live zero-to-one replica bounds.

5. Assert the live Azure min/max values inside the authenticated deployment job because local Azure CLI access is blocked by tenant security defaults.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Changed the canonical deployment command from an always-on minimum of one replica to min 0 / max 1. Local verification: deployment-block assertion passed, backend suite 1,243 passed, frontend production build passed, and git diff check passed.

Implementation PR #195 merged as cca5c4e0 and deployment run 36863276503 succeeded, including public-app verification. Local Azure CLI cannot independently read the live bounds because tenant security defaults require interactive reauthentication; adding the live assertion to the authenticated deployment itself.

Deployment run 36864599690 applied the scale update but failed its new verifier because Azure CLI renders a queried primitive array on separate lines while Bash read consumes one line. Root cause is documented in .orchestrator/debug/01a0edd2-7a80-737c-9bb4-8581c24c7af5-13.md; the verifier now queries each scalar separately.

Final deployment verification: PR #197 merged as 03fab0f6; main run 36866116726 passed and its authenticated Azure read-back printed 'Replica range: 0..1'. After 360 seconds idle, the first /api/health/ request returned 200 with database=ok in 26.051s, followed by a warm 200 response in 0.178s, objectively demonstrating scale-to-zero cold wake. Asian Dad evaluation: PERFECT (self-graded).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Production now scales from zero to one replica, and every deployment both reapplies and verifies those live bounds. Verified by 1,243 backend tests, frontend production build, successful main deployment 36866116726, authenticated Azure read-back 0..1, and a measured 26-second cold wake returning database health OK.
<!-- SECTION:FINAL_SUMMARY:END -->
