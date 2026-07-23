---
id: TASK-46
title: Do not treat email addresses as job links
status: Done
assignee: []
created_date: '2026-07-23 14:26'
updated_date: '2026-07-23 14:29'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/views.py
  - backend/jobradar/serializers.py
  - backend/jobradar/tests/test_api.py
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The add-job bulk parser currently interprets email addresses found in a pasted job description as bare web domains. A details-only EBCONT (BMJ) listing therefore becomes three URL jobs instead of one listing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Email addresses in a job description do not create separate jobs
- [x] #2 A details-only listing containing email addresses creates exactly one job with the entered company and title
- [x] #3 Actual URLs in a job description can still create linked jobs
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Fix the shared link extractor to exclude email-address matches.
2. Add a regression test reproducing the EBCONT details-only submission while retaining URL extraction coverage.
3. Run backend tests and restart the local server.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The shared extractor now ignores email-address tokens while retaining actual URL extraction. Normal parentheses are preserved in company names, so EBCONT (BMJ) remains unchanged.

Data repair: consolidated erroneous jobs 709-711 into job 709 with company EBCONT (BMJ), title ElasticSearch Consultant, and no URL; the removed duplicates were identical and had no evaluations, notes, or follow-ups.

Validation: 123 backend tests passed on local SQLite; live extractor returned no links for the three emails and retained a real HTTPS URL; restarted localhost server and health returned 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed email addresses being parsed as job URLs, preserved parenthesized company names, and repaired the three erroneous EBCONT rows into one correct listing.
<!-- SECTION:FINAL_SUMMARY:END -->
