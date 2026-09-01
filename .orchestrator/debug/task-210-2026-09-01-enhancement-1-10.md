# TASK-210 Sponsorhive empty-modal wait timeout

## Failure

After programmatically clicking Sponsorhive's email button, the verifier did not observe the expected empty-conversation sentence within five seconds.

## Root cause

The backend recorded one successful `GET /api/jobs/1079/mailbox/` (200, 26 bytes). Immediate follow-up DOM inspection found the labelled dialog, the full expected no-conversation/no-recipient sentence, the labelled Gmail search link, and no alert. The minimized/background tab's five-second polling wait missed the state despite the completed request; this reproduces the earlier background-tab timing weakness.

## Resolution

Use request completion plus direct DOM inspection (and a longer bound only where polling is unavoidable). No product change is warranted.
