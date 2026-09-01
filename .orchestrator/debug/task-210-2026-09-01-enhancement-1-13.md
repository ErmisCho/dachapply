# TASK-210 clean screenshot timeout

## Failure

After ending the synthetic account's onboarding tour, the browser command printed that both dialogs were closed and then timed out during a replacement screenshot.

## Root cause

The click correctly ended the onboarding overlay but also left no feedback dialog to capture. Screenshot capture on the minimized/background tab then hung until the tool timeout. The prior screenshot and direct DOM evidence were already captured; this is a verifier lifecycle/timing failure.

## Resolution

Do not use the timed-out screenshot as evidence. Reopen the feedback dialog only if another image is needed; direct DOM and request evidence remain authoritative. No product change is warranted.
