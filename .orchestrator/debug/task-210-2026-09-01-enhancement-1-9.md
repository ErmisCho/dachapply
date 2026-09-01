# TASK-210 post-login dashboard wait timeout

## Failure

The login request returned HTTP 200, but the verifier's combined wait for pathname `/` and body text `Private job intelligence` timed out.

## Root cause

The page was already at `/` with title `Board — DACHApply`, heading `Job command center`, both feedback rows, and no alerts. All dashboard APIs returned 200. The wait was case-sensitive for `Private job intelligence`, while CSS/text rendering exposed `PRIVATE JOB INTELLIGENCE` in `innerText`.

## Resolution

Use stable pathname/heading/accessible-control evidence rather than case-sensitive decorative copy. No application change is warranted.
