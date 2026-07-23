---
id: TASK-25
title: Use owner candidate evidence in CV generation
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:40'
updated_date: '2026-07-17 06:37'
labels:
  - ai
  - privacy
  - backend
dependencies: []
modified_files:
  - job-application-adaptation-rules.md
  - backend/config/settings.py
  - .env.local.example
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
- [x] #5 Every initial generation and readjustment includes job-application-adaptation-rules.md
- [x] #6 Missing or empty adaptation rules fail clearly
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Load both the private candidate evidence and tracked application adaptation rules for owner generation. Fail clearly if either source is unavailable, then include both as mandatory prompt sections for initial generation and readjustment.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a local candidate evidence path setting defaulting to the untracked project-root file in DEBUG mode. Owner generation requires and loads the entire UTF-8 evidence file as authoritative context before DACHApply profile notes. Missing/empty evidence returns a clear error. No API or export exposes the file. Three focused tests and Django checks passed.

Follow-up: automatically load the reusable adaptation rules alongside candidate evidence for every generation and revision.

Added CODEX_APPLICATION_RULES_PATH, defaulting to the tracked project-root job-application-adaptation-rules.md. load_candidate_evidence now requires and UTF-8-loads both documents, placing mandatory adaptation rules after authoritative candidate evidence and before profile notes. Because every initial generation and persisted revision uses this shared loader, all CV/letter model calls receive the rules automatically. Three focused tests, Django check, migration drift check, and whitespace check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Owner generation and every readjustment now automatically combine candidate evidence, mandatory reusable adaptation rules, profile notes, and original job text.
<!-- SECTION:FINAL_SUMMARY:END -->
