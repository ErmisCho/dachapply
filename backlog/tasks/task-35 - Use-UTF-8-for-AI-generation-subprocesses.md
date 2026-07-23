---
id: TASK-35
title: Use UTF-8 for AI generation subprocesses
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 11:19'
updated_date: '2026-07-16 11:21'
labels:
  - backend
  - bug
  - ai
dependencies: []
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Windows generation fails before invoking the model when candidate evidence or job text contains emoji/non-CP1252 characters because subprocess text pipes inherit the charmap codec.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Model subprocess input and output use UTF-8 on Windows
- [x] #2 Candidate evidence containing emoji can reach generation
- [x] #3 Regression test verifies UTF-8 subprocess configuration
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Set encoding=utf-8 on the existing model subprocess calls; add no text sanitization because Unicode content is valid.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Set encoding=utf-8 on both Codex and Claude subprocess pipes so Windows no longer uses the system charmap for Unicode prompts. The generation regression test now sends 📌 through all model paths and asserts UTF-8 configuration. Focused test and Django check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
CV generation now passes Unicode candidate evidence and job text to AI CLIs using UTF-8, fixing Windows charmap failures.
<!-- SECTION:FINAL_SUMMARY:END -->
