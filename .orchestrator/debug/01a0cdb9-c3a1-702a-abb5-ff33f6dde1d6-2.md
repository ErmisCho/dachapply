# Debug session: prompt copy fails on CAREN HTTP hostname
Created: 2026-09-23T10:11:00Z
Session: 01a0cdb9-c3a1-702a-abb5-ff33f6dde1d6

## Phase 1 — Root Cause

### Error
UI, verbatim: `Clipboard access was blocked. Select the prompt below and copy it manually.`

No stack trace is emitted; `copyToClipboard` catches the failure and returns `false`.

### Reproduction
1. Open `http://caren:8000` (the URL shown in the supplied screenshot).
2. Click `Analyze 1 new job`.
3. Observe the warning above the generated prompt.

Focused code-path check:
`cd frontend && npm test -- --run src/appUtils.test.ts`

Environment: Chrome on Windows 10; plain HTTP non-loopback hostname; `navigator.clipboard` unavailable outside a secure context.
Frequency: always on the reported CAREN HTTP URL.

### Suspect commits
No recent regression was found. `copyToClipboard` was introduced as a shared helper but intentionally returns `false` when `navigator.clipboard` is missing; it has no fallback for the supported LAN URL.

### Instrumentation data
- The screenshot shows `Not secure` and `caren:8000`.
- `Dashboard.openPrompt` and `Dashboard.copyPrompt` both route through `copyToClipboard`.
- `frontend/src/appUtils.ts` returns `false` immediately when `navigator.clipboard` is absent.
- The focused test confirms that missing clipboard support currently resolves to `false`.
- `document.execCommand('copy')` is the browser-native fallback available to HTTP pages and needs no dependency.

### Hypothesized root cause
The shared copy helper only uses the secure-context Clipboard API, so the supported plain-HTTP CAREN hostname has no copy implementation and is reported as blocked. · Confidence: high

## Phase 2 — Pattern

This is a platform-capability fallback gap, not a permission-dialog bug. Multiple copy controls already route through the shared helper, so the fix belongs there. A missing test for fallback success allowed the helper's missing-clipboard case to be treated as permanent failure.

## Phase 3 — Impact

Affected files:
- `frontend/src/appUtils.ts`
- `frontend/src/appUtils.test.ts`

Callers include the dashboard ChatGPT prompt modal, prompt page, intake prompt, bookmarklet, invite codes, and path-copy controls. Direct clipboard calls elsewhere are outside the reported prompt workflow.

## Phase 4 — Solution

Keep `navigator.clipboard.writeText` as the first choice, then use a temporary textarea plus `document.execCommand('copy')` when it is unavailable or denied. Always remove the temporary textarea and return `false` if both methods fail. Add focused tests for fallback success and total failure.

## Resolution

PR #177 squash-merged as `8dda72d`, changing the shared copy helper and focused tests. Verification: Chrome on insecure `http://caren` returned `true` and captured the complete text; all 296 frontend tests, the production build, deploy run 35849727904, local runtime sync, and health checks passed.
