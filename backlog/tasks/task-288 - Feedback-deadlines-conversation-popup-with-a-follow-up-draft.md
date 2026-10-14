---
id: TASK-288
title: 'Feedback deadlines: conversation popup with a follow-up draft'
status: In Progress
assignee: []
created_date: '2026-10-14 08:05'
updated_date: '2026-10-14 12:48'
labels: []
dependencies: []
ordinal: 289000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): each feedback-deadline row gets a button that opens a popup with all of that job's email conversations as bubbles (both sides) and a ready follow-up email draft written to maximise the chance of getting the job (uses the job posting, evaluation, the conversation so far and the owner's profile). Depends on TASK-287 (no mail has been captured since late August). Drafting uses the local Codex CLI like CV generation (LLM_PROVIDER is unset, so the heuristic templates are the fallback).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each feedback-deadline row has a button that opens a popup showing every email of that job as conversation bubbles, both directions, oldest to newest
- [x] #2 The popup shows a follow-up draft (recipient, subject, body) generated from the posting, evaluation, conversation and owner profile; it can be regenerated, edited and copied or sent to Gmail as a draft through the existing draft path
- [x] #3 Without Codex available the popup still opens and says why no draft was generated
- [ ] #4 Verified in the browser on localhost with the owner's data, desktop and phone width
- [x] #5 vitest, tsc and backend suite pass; tests fail when the draft input omits the conversation or the posting
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: #247. Localhost: BEKO popup shows 6 bubbles both sides and a German follow-up draft to the recruiter. Open: phone width.
<!-- SECTION:NOTES:END -->
