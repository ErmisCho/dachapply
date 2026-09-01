# TASK-209 local readiness poll timeout budget

## Symptom

The first detached-runtime readiness poll timed out at the tool's 120-second limit, but follow-up ownership checks found the exact main-runtime Vite and Django processes and both ports subsequently returned HTTP 200.

## Root cause

The loop allowed 60 iterations, each with an HTTP timeout up to 2 seconds plus a 1-second sleep: its worst-case runtime was about 180 seconds, exceeding the wrapper's 120-second timeout. Dependency setup/startup was still progressing independently and succeeded.

## Resolution

Verified runtime HEAD `795996ca7074cd42f81958b48f08a9d6db6d2ce7`, clean detached worktree, port 5173 HTTP 200, port 8000 API/root HTTP 200, and command lines rooted only in the dedicated runtime. No process needed termination.
