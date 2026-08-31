# Debug session: TASK-208 Backlog plan shell quoting
Created: 2026-08-31T14:18:00Z
Session: task-208-2026-08-31-enhancement-1

## Phase 1 — Root Cause

### Error

```text
/usr/bin/bash: line 1: patchJob: command not found
```

### Reproduction

Pass a double-quoted `backlog task edit --plan` value containing Markdown backticks around `patchJob` through Bash. Frequency: 1/1.

### Suspect commits

None; task-metadata command only.

### Instrumentation data

Bash executed the text inside backticks as command substitution before Backlog received the plan. The task plan was written with the identifier omitted.

### Hypothesized root cause

An unescaped Markdown code span was placed inside a double-quoted Bash argument, so the shell treated `patchJob` as command substitution. · Confidence: high

## Phase 2 — Pattern

The Backlog creation guide explicitly requires single-quoted arguments for literal backticks.

## Phase 3 — Impact

No product code changed. Only TASK-208's plan text lost one identifier and must be replaced through the Backlog CLI.

## Phase 4 — Solution

Replace the plan using a single-quoted argument with no shell interpolation, then read it back.

## Resolution

Replaced the plan through the Backlog CLI with shell-safe quoting and then read it back; the intended owner-scoped update wording is present. Replaced the notes to remove the malformed first copy.
