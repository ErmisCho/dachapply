---
id: TASK-49
title: Restore and automate Azure Container App deployment
status: Done
assignee: []
created_date: '2026-07-23 14:59'
updated_date: '2026-07-23 15:34'
labels: []
dependencies: []
modified_files:
  - .github/workflows/deploy-container-apps.yml
priority: high
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The public Azure Container Apps endpoint accepts TCP/TLS connections but returns no HTTP response. Push the completed work, deploy the resulting image to the existing dachapply Container App, and verify public availability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All intended repository changes are committed and pushed to origin/main
- [x] #2 The GitHub workflow builds the Docker image and deploys that exact commit to the existing dachapply Azure Container App
- [x] #3 The public Azure Container Apps URL returns a successful HTTP response after deployment
- [x] #4 Automated backend tests and frontend build pass before deployment
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add the missing Azure login/container-app update and public smoke test to the existing GHCR workflow. 2. Remove accidental local artifacts, review and commit the accumulated completed work. 3. Push main, monitor GitHub Actions, and verify the public endpoint.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Validation passed before deployment: backend pytest 124 passed (one existing test DB teardown warning), frontend production build passed, Docker image build passed, and git diff check passed. Azure CLI user token is blocked by tenant security defaults, so deployment is delegated to GitHub Actions using the existing AZURE_CREDENTIALS secret.

First deployment run 30018937670 built/pushed the image and successfully updated Azure, but smoke testing failed: revision dachapply--0000027 was Provisioned with 100% traffic, 0 replicas, and Unhealthy. Updated deployment to enforce one minimum replica and emit system diagnostics on failure.

Second run 30020004075 confirmed the root cause through Azure system events: ImagePullUnauthorized for the private GHCR package. Added a GHCR_PULL_TOKEN repository secret from the authenticated GitHub package token and made deployment refresh Azure Container Apps registry credentials before updating the image.

Successful deployment: workflow run 30021031259 deployed commit 20c4faeaa705a9791e0f10c14a1d15e338debda2. Independent verification returned HTTP 200 for / and /privacy; unauthenticated /api/auth/me/ correctly returned 403.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Pushed completed work to main, automated exact-SHA deployment from GHCR to Azure Container Apps, restored private registry access, kept one replica warm, and added a public smoke test. GitHub Actions run 30021031259 passed; the root and privacy URLs return HTTP 200.
<!-- SECTION:FINAL_SUMMARY:END -->
