# TASK-209 foreground launcher wrapper timeout

## Symptom

PowerShell's direct call operator executed `dachapply-start.cmd`, synchronized the runtime to `795996c`, installed dependencies, and started Vite/Django, but the tool timed out at 300 seconds; the timeout then removed those inherited child processes.

## Root cause

`scripts/dachapply-local-runtime.cmd` intentionally keeps `npm run dev` in the foreground while Django runs with `start /b`. Calling that launcher inside the tool left long-lived inherited handles attached, so a synchronous tool invocation cannot return while the local runtime stays alive.

## Resolution

Dispatch the launcher via an independent hidden `cmd.exe` using `Start-Process`, then poll ports separately. The dedicated runtime stayed correctly synchronized; no development worktree was reset.
