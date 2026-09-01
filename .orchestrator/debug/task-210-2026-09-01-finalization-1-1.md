# TASK-210 local-runtime launcher verification failure

## Failure

The first detached runtime-launch command failed with a PowerShell parser error (`Unexpected token ... dachapply-start.cmd`) and then its outer health loop timed out because no process had been launched.

## Root cause

A Bash-embedded PowerShell expression attempted to compose nested escaped quotes for `Start-Process -ArgumentList`. The resulting PowerShell source was syntactically invalid. This was launcher invocation quoting, before the repository launcher executed; it did not change or stop the existing runtime.

## Resolution

A tiny temporary `.ps1` with ordinary PowerShell quoting invoked the unchanged repository launcher successfully. The detached runtime synchronized to `41d30af1aa41a201e81c603fd65d25179276cc81`; backend port 8000 and frontend port 5173 both returned HTTP 200. No product change was warranted.
