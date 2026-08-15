---
id: TASK-6
title: Improve JSON import error messages
status: Done
assignee:
  - '@claude'
created_date: '2026-06-20 09:50'
updated_date: '2026-06-20 09:54'
labels:
  - P1
  - backend
  - frontend
  - ux
  - phase-2
milestone: m-2
dependencies:
  - TASK-1
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ChatGPT JSON import is central to the workflow, so validation errors should be easy to fix.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1: format_json_decode_error() in json_importer.py turns a JSONDecodeError into
"Invalid JSON on line {lineno}, column {colno}: {msg}", called from both import_any_json and
import_evaluations so every caller benefits rather than one route.

Fixing that surfaced a real bug worth recording. parse_json_object recovers from chatty ChatGPT
replies by skipping to the first '{' and then attempting a quote repair. When that recovery still
failed, the raised error's line and column were relative to the truncated candidate, not the text
the user actually pasted - so a reply with two lines of preamble reported line 3 for an error that
was really on line 6. The position is now remapped onto the full text. A ponytail comment records
the residual limitation honestly: quote repair can insert characters ahead of the error, so on that
last-resort path the column may drift slightly, though the line is right.

AC2 was ALREADY MET before this task and was not rewritten: validate_eval computes
`required - set(ev.keys())` and joins every missing key into one sorted message, and the importers
accumulate errors across all records instead of stopping at the first bad one. Covered now by
test_reject_invalid_evaluation_lists_every_missing_field, which asserts all 17 required fields
appear in a single message.

AC3: the Import page renders a collapsible "Example JSON shape (evaluations)" block using the
existing details/summary pattern already used elsewhere in App.tsx.

Also fixed while here: messageText now falls back to an errors[] array, so import failures render
as readable text instead of raw JSON.

Tests: test_invalid_json_import_reports_line_and_column,
test_invalid_json_import_reports_line_relative_to_full_pasted_text (the regression above), and
test_reject_invalid_evaluation_lists_every_missing_field.
<!-- SECTION:NOTES:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Invalid JSON shows line/parse-friendly error when possible
- [x] #2 Missing required fields are listed clearly
- [x] #3 Import page shows an example of the expected JSON shape
<!-- AC:END -->
