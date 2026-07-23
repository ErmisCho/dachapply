---
id: TASK-43
title: Restore automatic ChatGPT response import
status: Done
assignee:
  - '@pi'
created_date: '2026-07-21 11:44'
updated_date: '2026-07-21 12:39'
labels: []
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - backend/jobradar/services/json_importer.py
  - backend/jobradar/tests/test_api.py
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ChatGPT can append citations and emit unescaped quotation marks inside otherwise structured JSON. DACHApply should repair this common output, import it automatically, and prompts should explicitly forbid citations and require JSON escaping.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Malformed content without a valid JSON object remains rejected
- [x] #2 Clipboard responses with trailing markdown citation definitions are automatically imported
- [x] #3 Manual API imports accept an otherwise valid JSON object surrounded by non-JSON ChatGPT text
- [x] #4 Unescaped quotes inside ChatGPT string values are repaired without changing valid JSON
- [x] #5 Default prompts forbid citations and require escaped parseable JSON
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Repair unescaped quotes in otherwise JSON-shaped clipboard/API input.
2. Strengthen generated prompts to forbid citations and require escaped, parseable JSON.
3. Extend the existing citation regression with the reported quoted-title shape; run focused tests and frontend build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
ChatGPT responses are now normalized to the first valid JSON object before import. The frontend strips surrounding markdown/citation definitions for automatic clipboard import; the backend uses Python JSONDecoder.raw_decode at the import boundary so manual imports receive the same tolerance. Malformed text without a JSON object remains rejected.

Validation: frontend npm build passed; focused pytest regression passed (with a pre-existing PostgreSQL teardown warning about another session); py_compile and git diff check passed.

Completed quote repair at both clipboard and backend import boundaries. Focused regressions passed (2 tests); frontend production build passed. Full backend test file was attempted but exceeded 5 minutes while PostgreSQL tests contended for the shared test database.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @pi
created: 2026-07-21 12:00
---
Root cause: ChatGPT now appends markdown reference definitions after the closing JSON brace, so both the frontend JSON.parse gate and backend json.loads reject the response.
---

author: @pi
created: 2026-07-21 12:11
---
The supplied response is not valid JSON because original_source_text contains unescaped double quotes around the job title. Citation stripping alone cannot parse it.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Restored automatic ChatGPT response import by extracting the JSON object, repairing common unescaped string quotes, and strengthening all default prompts against citations and invalid escaping. Verified with focused backend regressions and the frontend production build.
<!-- SECTION:FINAL_SUMMARY:END -->
