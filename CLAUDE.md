# CLAUDE.md

Instructions for Claude Code in this repository. `AGENTS.md` covers the backlog tooling and session
config. The incidents behind these rules are in `docs/workflow-history.md`.

## Match the process to the task

Owner instruction, 2026-11-11 (replaces "orchestrate every request" from 2026-08-18). Pick a tier for
each request and name it in the reply:

- **Inline** — a question, a config tweak, or a change of a few lines. Just do it, then verify it.
- **Standard** — a normal feature or fix. Task in `backlog/tasks/` with acceptance criteria sharp
  enough to fail, asian-dad rubric written before any code, implemented directly or by **one** agent,
  verified, graded.
- **Full** — migrations, production data, several file territories, or risky/unclear work. The
  Standard steps plus session-orchestrator waves, one agent per file territory.

When torn, take the higher tier. Verification against reality applies to every tier.

Dispatch agents with an explicit `model`: `sonnet` for implementers, test-writers and docs, `haiku`
for read-only sweeps. Opus stays the coordinator and grader. Brief agents with exact files and known
facts so they do not re-derive them.

`.claude/rules/task-workflow.md` (TW-000 to TW-006) is the authority when the two disagree;
`.claude/rules/parallel-sessions.md` governs sharing the repo with other sessions.

## Verify against reality, not against a green suite

Implementations here have passed every test and still been wrong in production (TASK-162, 163, 165,
134; details in `docs/workflow-history.md`).

- A bulk data change gets a **dry-run-by-default management command**, never a migration.
- Numbers in a report are measured or not stated. An agent without production access says so.
- A coordinator estimate is not evidence.

## Finish on the owner's machine

Owner instruction, 2026-08-21: *"always make sure that localhost works when you complete a task."*
Before calling anything done: `cd frontend && npm run build` **in the owner's checkout**, confirm the
served bundle hash matches `frontend/dist/index.html`, and load the page to assert it rendered — a
200 is not enough. A worktree build never reaches the owner.

## Merge without asking, unless it is destructive or irreversible

Owner instruction, 2026-11-09. Once CI is green and review findings are fixed, squash-merge
(`gh pr merge --squash`, never `--delete-branch`; TW-00A orders the rest) without asking.

Ask first, with options, when the PR:
- adds or changes a migration, or runs a data-changing command against production;
- deletes or rewrites owner data or files (CV workspace, evidence file, sidecars);
- needs a force-push or history rewrite, or touches secrets, auth or CI gates.

Merging does not deploy (TASK-275). Owner instruction, 2026-11-12: agents may deploy without asking
(`gh workflow run deploy-container-apps.yml --ref main`), recording the rollback image first and
verifying production afterwards (TW-006).

## Use Codex to spare Claude tokens

Owner instruction, 2026-11-09. Use Codex CLI for work that does not need Claude's judgment:
- **PR review:** `codex review` on each PR before merging; Claude applies and verifies the fixes.
- **Read-only sweeps:** `codex exec` for broad greps, audits and "where is X used" questions.

Codex output is evidence, not proof: TW-003 applies to it as to any agent.

## Session Config

The full Session Config is in `AGENTS.md`. This key is repeated here because the session-orchestrator hooks read only CLAUDE.md under Claude Code (owner decision 2026-11-12).

allow-destructive-ops: true
