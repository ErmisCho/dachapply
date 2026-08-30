# Debug session: Primary main diverged during housekeeping
Created: 2026-08-30T12:35:00Z
Session: task-203-2026-08-30-housekeeping-1

## Phase 1 — Root Cause

### Error

Exact command:

```text
git merge --ff-only origin/main
```

Exact result (exit 128):

```text
hint: Diverging branches can't be fast-forwarded, you need to either:
hint:
hint: 	git merge --no-ff
hint: or:
hint: 	git rebase
fatal: Not possible to fast-forward, aborting.
```

### Reproduction

```text
HEAD=7c6e0aac009cd4c1119f30a0d998c80a87fad28e
origin/main=c20e0f16662cff04f2701a95029ae5bdb4a542c5
merge-base=a7a2c29c49a8ee57c2fb4a13c6fb677efa6e40a9
git status: main...origin/main [ahead 1, behind 1]
```

Environment: Windows, shared Git repository with an isolated TASK-203 worktree and the primary project directory on local `main`. Reproduction frequency: always while the refs retain this topology.

### Suspect commits

- `7c6e0aa docs(rules): add TW-002a — never idle on a wait; dispatch or ask, but do not narrate` — locally committed directly to `main` at 2026-08-30 10:10:32 +0200 by another session after TASK-202 synchronized the primary directory.
- `c20e0f1 chore(repo): finish maintenance cleanup` — PR #103's remote-main merge; independent Backlog-only changes that exposed the existing divergence when fast-forward synchronization ran.

### Instrumentation data

- `git merge-base HEAD origin/main` is `a7a2c29`, proving neither tip contains the other.
- `7c6e0aa` changes only `.claude/rules/task-workflow.md` (28 added lines).
- `c20e0f1` changes only TASK-203/TASK-204/TASK-99 Backlog files.
- The two commits have no file overlap.
- The local commit has owner-authored policy content and must not be discarded.
- Current tracked dirt is append-only Session Orchestrator telemetry; `Feedback/` and zero-byte `NUL` are untracked and unrelated to the divergent commits.

### Hypothesized root cause

A concurrent session committed owner policy directly onto the shared local `main` after it was synchronized, so the later PR #103 merge created two non-ancestor tips and made `--ff-only` correctly refuse. · Confidence: high

## Phase 2 — Pattern

This is shared-ref concurrency, not a merge-content conflict: worktrees isolate files but all worktrees share branch refs, and the primary `main` remained writable by another session. The missing guard is process/workflow-level branch isolation for concurrent sessions; the fast-forward refusal is the safety mechanism that prevented silent loss.

## Phase 3 — Impact

Affected state:

- local `main` ref and primary project checkout
- unique commit `7c6e0aa` in `.claude/rules/task-workflow.md`
- TASK-203 release synchronization

Unaffected:

- `origin/main` and PR #103
- detached local runtime
- Azure deployment
- TASK-202 recovery archive and `Feedback/SixRobotics.MD`

## Phase 4 — Solution

Create a dedicated local branch at `7c6e0aa`, verify that branch resolves to the unique policy commit, then repoint local `main` to `origin/main` while on the preservation branch and switch the primary checkout back to `main`. This keeps the policy commit recoverable without manufacturing a merge commit or pushing unrelated work. Verify branch/ref hashes and primary/runtime health afterward.

## Resolution

Preserved `7c6e0aa` on local branch `preserve/task-workflow-no-idle-7c6e0aa`, repointed local `main` to `origin/main` at `c20e0f1` from the preservation branch, then switched the primary checkout back to `main`. Removed only the zero-byte `NUL` artifact created by shell redirection. Verification: local main equals origin/main, the preservation branch still resolves to `7c6e0aa`, the detached runtime resolves to `c20e0f1`, and API/frontend health checks return HTTP 200.
