
<!-- BACKLOG.MD GUIDELINES START -->
<CRITICAL_INSTRUCTION>

## Backlog.md Workflow

This project uses Backlog.md for task and project management.

**For every user request in this project, run `backlog instructions overview` before answering or taking action.**

Use the overview to decide whether to search, read, create, or update Backlog tasks.

Use the detailed guides when needed:
- `backlog instructions task-creation` for creating or splitting tasks
- `backlog instructions task-execution` for planning and implementation workflow
- `backlog instructions task-finalization` for completion and handoff

Use `backlog <command> --help` before running unfamiliar commands. Help shows options, fields, and examples.

Do not edit Backlog task, draft, document, decision, or milestone markdown files directly. Use the `backlog` CLI so metadata, relationships, and history stay consistent.

</CRITICAL_INSTRUCTION>
<!-- BACKLOG.MD GUIDELINES END -->

## Task Completion Policy

- Treat “go on” and “do this” as instructions to carry assigned work through implementation, verification, evaluation, commit, push, and squash merge without waiting for a separate close request.
- A task is complete only after its required tests pass, Asian Dad returns PERFECT, its changes are committed and pushed, and its implementation branch is squash-merged into the default branch.
- Keep Backlog tasks In Progress while merge is pending. Mark them Done in a post-merge completion change, then squash-merge that administrative change too.

## Session Config

project-name: dachapply
vcs: github
persistence: true
enforcement: warn
waves: 5
agents-per-wave: 6
test-command: cd backend && uv run pytest -q
typecheck-command: cd frontend && npm run build
lint-command: skip
recent-commits: 20
stale-branch-days: 7
issue-limit: 50
