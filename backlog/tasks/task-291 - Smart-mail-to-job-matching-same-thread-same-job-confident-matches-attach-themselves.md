---
id: TASK-291
title: >-
  Smart mail-to-job matching: same thread, same job; confident matches attach
  themselves
status: Done
assignee: []
created_date: '2026-10-14 09:01'
updated_date: '2026-10-15 09:34'
labels: []
dependencies: []
ordinal: 292000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): the Salesforce interview invitation (2026-09-24, from a recruiter) was captured but left unmatched although the app suggested the right job (suggested_job=Salesforce — Forward Deployed Engineer); 56 captured emails wait for manual attachment, 16 with a suggested job. Mail in a Gmail thread that already belongs to a job, and mail with a confident single suggestion (company/domain/role/ATS sender like myworkday), should attach to that job by itself.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A message whose Gmail thread already has a message attached to a job is attached to the same job automatically
- [x] #2 A message with exactly one confident suggested job (rule documented in code: e.g. company name or careers domain plus role keywords, ATS senders such as myworkday) is attached automatically; ambiguous ones stay for the owner
- [x] #3 Already-captured unmatched mail is re-evaluated once, so the Salesforce invitation lands on the Salesforce job
- [x] #4 Auto-attached mail is marked as such and can be detached in one click
- [x] #5 Tests cover thread inheritance, confident vs ambiguous suggestions and the one-off re-evaluation; each fails when its logic is removed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-15: #254, #257, #258. In-app re-check (dry run then apply) attached the Salesforce 09-24 invitation and the EBCONT thread; auto-attached badge + Detach seen in the Salesforce popup.
<!-- SECTION:NOTES:END -->
