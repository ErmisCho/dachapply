---
id: TASK-402
title: Prompt rules for profile opener and skills order
status: To Do
assignee: []
created_date: '2026-11-21 09:16'
labels: []
dependencies: []
priority: high
ordinal: 403000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner rewrites profile/headline (14 edits) and skills keyword order (12 edits); e.g. downgrading 'Senior Software Engineer' to 'Software Engineer'. Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Generation prompt states: no 'Senior' title unless the posting asks for senior level; headline/profile names at least two of the posting's key requirements the evidence supports; skills categories lead with the posting's terms (prompt test)
- [ ] #2 Existing prompt tests still pass
<!-- AC:END -->
