---
id: TASK-19
title: Show full email in Added by tooltip
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-10 12:30'
updated_date: '2026-07-10 14:38'
labels:
  - frontend
  - backend
  - bug
dependencies: []
modified_files:
  - frontend/src/App.tsx
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Added by badges show compact names on the dashboard, but the hover tooltip can only show the username/name currently returned by the API. Registered submitters should expose their full email/username in the tooltip while keeping the cell compact.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Job API exposes creator email/username data needed for Added by tooltip
- [x] #2 Dashboard Added by cell displays a compact friendly name but uses the full email/username as title
- [x] #3 Frontend build and a backend regression check pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Compute duplicate Added by first names across visible dashboard rows.\n2. Show first name normally, or first name + last initial when that first name is duplicated.\n3. Keep full email in tooltip and run frontend build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
API now returns created_by_email/submitted_for_email using email with username fallback. Dashboard keeps compact Added by names but uses the email field for native title tooltips. Validation: frontend npm run build passed; backend pytest 98 passed.

User still sees only names on demo Added by hover. Root cause: seeded referral jobs store the demo user as created_by and only a name in submitted_by, so no referrer email reaches the tooltip. Reopening to seed demo referrals as real friend-submitted jobs.

Fixed seeded demo referrals to be real friend-submitted jobs: created_by is the referrer user and submitted_for is the demo user, so Added by tooltips receive anna/max/sophie email addresses instead of only submitted_by names. Updated demo leak tests to allow jobs submitted_for demo. Validation: backend pytest 98 passed; frontend build passed.

Follow-up UI regression: full friendly names like Sophie Recruiter overflow the narrow Added by column. Compact visible label to first name while keeping full email in tooltip.

Added by display now uses only the first friendly name and clips any unusually long value inside the cell; title still carries the full email. Validation: frontend npm run build passed.

Follow-up requested: disambiguate duplicate Added by first names without widening the column.

Duplicate Added by first names are now detected across visible dashboard rows. The badge stays first-name-only unless the same first name belongs to multiple distinct email/title values, then it shows first name + last initial. Full email remains in the tooltip. Validation: frontend npm run build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added by now uses first name by default, first name + initial only for duplicate visible first names, and keeps the full email tooltip. Verified frontend build passed.
<!-- SECTION:FINAL_SUMMARY:END -->
