---
id: TASK-5
title: Improve onboarding and empty states
status: Done
assignee:
  - '@claude'
created_date: '2026-06-20 09:50'
updated_date: '2026-06-20 09:54'
labels:
  - P1
  - frontend
  - ux
  - onboarding
  - phase-2
milestone: m-2
dependencies:
  - TASK-1
  - TASK-3
priority: medium
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
New users should immediately understand how to add job leads, generate prompts, and import evaluations.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1 and AC2 were ALREADY MET before this task and were deliberately left alone rather than rewritten
for the sake of activity. DashboardEmptyState in App.tsx already renders a "Start here" label, an
"Add your first job" heading and a paragraph describing the full add -> analyze -> import -> track
workflow, and it is genuinely wired up: Dashboard() renders it only when
jobs.length===0 && stats.total_jobs===0. Its primary CTA already branches correctly between /add and
/public-submit via isFriendSubmitter.

AC3 was the real gap and is now done. The Prompts page previously said "then import JSON results"
with no link and no import UI on that page, leaving a first-time user stranded mid-workflow. It now
reads as an explicit four-step sequence and links to /import. The Import page gained matching
guidance plus the example JSON shape from TASK-6, so both ends of the paste-into-ChatGPT loop
explain themselves.
<!-- SECTION:NOTES:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Empty dashboard explains the recommended first action
- [x] #2 Primary CTA points to add job/public submit/prompt workflow
- [x] #3 Prompt and import pages include short guidance for first-time users
<!-- AC:END -->
