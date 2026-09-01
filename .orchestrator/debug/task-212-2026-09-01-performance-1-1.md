# TASK-212 Backlog task-creation option failure

## Failure

The first task-creation command used `--label` repeatedly and failed with `unknown option '--label'` before creating a task or changing repository files.

## Root cause

This Backlog CLI version accepts the plural `--labels` option with a comma-separated value.

## Resolution

Retried once with `--labels backend,cv,performance`; TASK-212 was created successfully. No product change was warranted.
