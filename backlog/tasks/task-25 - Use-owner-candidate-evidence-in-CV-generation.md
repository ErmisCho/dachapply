---
id: TASK-25
title: Use owner candidate evidence in CV generation
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:40'
updated_date: '2026-07-15 15:43'
labels:
  - ai
  - privacy
  - backend
dependencies: []
priority: high
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
For the owner account ermis.chorinopoulos@gmail.com, CV generation must load the private local Ermis-Chorinopoulos-Candidate-Evidence.md file as the factual and tailoring source of truth. The file remains untracked and unavailable to other users.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Owner generation includes the configured candidate evidence file in model instructions
- [x] #2 Missing or unreadable evidence fails clearly instead of silently using weaker context
- [x] #3 Other users and exports cannot access the private evidence
- [x] #4 Tests verify owner evidence loading and prompt inclusion
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a local evidence path setting. 2. Load it only in owner CV generation. 3. Include it as the authoritative prompt section. 4. Add focused tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a local candidate evidence path setting defaulting to the untracked project-root file in DEBUG mode. Owner generation requires and loads the entire UTF-8 evidence file as authoritative context before DACHApply profile notes. Missing/empty evidence returns a clear error. No API or export exposes the file. Three focused tests and Django checks passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Owner CV generation now uses the private Candidate Evidence file as its factual source of truth and fails safely when unavailable.
<!-- SECTION:FINAL_SUMMARY:END -->
