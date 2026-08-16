---
id: TASK-94
title: Surface the app's silent failures
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 11:45'
labels:
  - frontend
  - ux
dependencies: []
priority: low
ordinal: 99000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Several actions swallow their failures: acceptFriend has no try/catch, so a failed accept is an unhandled rejection and the request card just sits there (frontend/src/App.tsx:98); the Followups "Mark completed" button likewise awaits with no catch (App.tsx:136); copyPrompt in the prompt modal and the Prompts-page copy button await `navigator.clipboard.writeText` uncaught — a blocked clipboard means silent nothing (App.tsx:98, 129).

The app has good error affordances (ErrorBox/StatusMessage with role="alert"/role="status", App.tsx:53-54) and other copy paths use protective handling (App.tsx:56, 187) — these call sites just bypass them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Failed friend-accept, follow-up-complete, and the two clipboard-copy actions each show the existing error affordance
- [x] #2 A forced-failure test (offline or clipboard-denied) produces no unhandled promise rejections in the console from these paths
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Copy the handling App.tsx:56 already does — this is bringing four call sites in line with the app's own established pattern, not new design.

### Closing notes (2026-08-16)

All four call sites now route through the existing guarded helpers rather than awaiting bare
promises. An independent audit of the file confirms no unguarded clipboard write survives: all five
`navigator.clipboard.writeText` occurrences are inside a `try`/`catch` (two are the guarded helpers
themselves; the other three are pre-existing CV/TeX paths that already set an error affordance).

AC1 — forced failures driven in a real browser (Playwright, local sqlite backend), each read back
from the live `role="alert"`/`role="status"` nodes:

| Path | Forced failure | Affordance rendered |
|---|---|---|
| Friend accept | `POST /api/auth/friend-requests/` → 500 | `! forced failure` |
| Follow-up "Mark completed" | `PATCH /api/followups/…` → 500 (GET left working) | `! forced patch failure` |
| Prompts-page copy | `navigator.clipboard.writeText` rejects `NotAllowedError` | `! Clipboard access was blocked. Select the prompt below and copy it manually.` |

The fourth site — `copyPrompt` in the prompt modal — was **not** driven end to end in the browser,
and that is stated rather than glossed: the modal is only reachable through the analyze per-job
picker, which is `group-hover`-revealed and therefore not clickable without a pointer (exactly the
defect TASK-81 is filed to fix). It was verified structurally instead: `copyPrompt` awaits the same
`copyToClipboard` helper, sets `promptCopyFailed`, and renders the same `StatusMessage` component
whose failure path is measured above. Once TASK-81 makes that picker tap/keyboard reachable, this
last path can be driven directly.

**Update 2026-08-16, after TASK-81 shipped: the fourth site is now driven and it works.** The
analyze picker became a real button, so the prompt modal opens without a pointer-only hover. With
`navigator.clipboard.writeText` rejecting, the modal renders

    ! Clipboard access was blocked. Select the prompt below and copy it manually.

and `window.__unhandled` stayed empty, so AC2 holds for this path too. All four call sites are now
behaviourally verified rather than three-plus-an-inference.

Worth recording because it nearly produced a false negative: the first measurement showed *no new*
alert after clicking Copy. The modal auto-copies the prompt when it opens, so the failure message
was already on screen before the click — two `writeText` attempts, one affordance. Diffing alerts
before and after the click reported nothing changed; reading the dialog's actual contents showed the
message present. A before/after diff is the wrong instrument when the state can already be set.

AC2 — an `unhandledrejection` listener was installed before each forced failure and read back
afterwards. It was empty (`[]`) after every one of the three driven failures, and no `pageerror`
fired.
<!-- SECTION:NOTES:END -->
