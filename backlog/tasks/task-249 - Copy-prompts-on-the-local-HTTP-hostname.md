---
id: TASK-249
title: Copy prompts on the local HTTP hostname
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-23 10:10'
updated_date: '2026-09-23 10:31'
labels:
  - frontend
  - ux
dependencies: []
modified_files:
  - frontend/src/appUtils.ts
  - frontend/src/appUtils.test.ts
priority: high
type: bug
ordinal: 248000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard is intentionally used at http://caren:8000. That is not a secure browser context, so navigator.clipboard is unavailable and opening the ChatGPT workflow immediately shows 'Clipboard access was blocked' even though the user asked the app to copy the prompt. Use the existing shared copy helper to provide a browser-native fallback rather than leaving every copy control broken on the supported LAN URL.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Clicking Copy prompt on http://caren:8000 copies the complete prompt and shows success instead of the blocked warning
- [x] #2 The shared helper still uses navigator.clipboard when available and returns false when both copy methods fail
- [x] #3 A focused test covers the fallback used when navigator.clipboard is unavailable
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add an execCommand fallback to the existing shared copy helper for browsers where navigator.clipboard is unavailable or denied on the supported HTTP hostname.
2. Extend the focused helper tests for fallback success and total failure.
3. Run the frontend tests and production build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Validation 2026-09-23: Chrome on http://caren:5175 measured isSecureContext=false and navigator.clipboard absent; clicking the test control returned true and the copy event captured the complete text. All 296 frontend tests and the production build passed. Asian Dad: PERFECT.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added the browser-native copy fallback to the shared helper. Verified in Chrome on an insecure CAREN origin, with focused fallback/secure-path/failure tests, all 296 frontend tests, and the production build; merge remains pending.
<!-- SECTION:FINAL_SUMMARY:END -->
