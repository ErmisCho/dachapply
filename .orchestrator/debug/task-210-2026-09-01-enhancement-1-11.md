# TASK-210 synthetic conversation label assertion miss

## Failure

The browser result reported `conversation: false` while all message bodies, chronological sender order, reply controls, exact-Gmail controls, draft controls, and pending decisions were present.

## Root cause

Direct inspection found `FULL CONVERSATION (2 MESSAGES CAPTURED)` and exactly two message-list items. The uppercase CSS class makes browser `innerText` expose uppercase rendered text while the check searched for title case, the same case-sensitive verifier mistake seen on the dashboard hero.

## Resolution

Treat the direct heading/count inspection as passing evidence and use case-insensitive checks if repeated. No product change is warranted.
