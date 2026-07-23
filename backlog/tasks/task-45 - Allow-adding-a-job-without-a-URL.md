---
id: TASK-45
title: Allow adding a job without a URL
status: Done
assignee: []
created_date: '2026-07-23 14:15'
updated_date: '2026-07-23 14:18'
labels: []
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Users need to save manually entered job listings when no source URL is available. The add-job form should clearly support details-only submissions while preserving existing link capture.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The add-job form clearly presents URL as optional
- [x] #2 A job can be saved with no URL when company, title, or description is provided
- [x] #3 Submitting with neither a URL nor listing details still shows a validation error
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Make the private add-job form explicitly support details-only entry and show those fields by default.
2. Add API coverage for details-only and empty submissions.
3. Run focused backend tests and the frontend build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The existing model and serializer already allowed blank URLs. Updated the private form to expose details by default and made the URL explicitly optional. Added an empty-input guard to bulk creation.

Validation: 122 backend tests passed using local SQLite; frontend npm run build passed. The first PostgreSQL test attempt was blocked by an existing test_neondb session.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Users can now clearly add a job without a URL by entering a company, title, or description. Empty submissions are rejected, and API regression tests cover all supported details-only inputs.
<!-- SECTION:FINAL_SUMMARY:END -->
