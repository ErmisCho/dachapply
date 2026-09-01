# TASK-209 local launcher cmd quoting failure

## Symptom

`cmd.exe /c "C:\...\dachapply-start.cmd"` printed a bare command prompt and returned success, but the dedicated runtime remained on the old SHA with the old listeners.

## Root cause

The command crossed Bash and `cmd.exe` quoting layers; the outer quotes were consumed such that `cmd.exe` started without executing the spaced script path. The unchanged runtime/listener measurements proved the launcher had not run.

## Resolution

Invoke the batch file through PowerShell's call operator or dispatch a separately quoted `cmd.exe` process. No runtime or development worktree changed during the failed invocation.
