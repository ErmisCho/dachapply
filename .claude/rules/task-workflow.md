# Default Task Workflow (Always-on)

Backlog work in this repo is graded with the **asian-dad-eval** skill, and Full-tier work (TW-000)
runs as **session-orchestrator agents in waves**. This is the default, not something to be asked for each time. It exists
because this session repeatedly found that unverified claims — from agents and from earlier passes —
were wrong in ways only measurement caught.

## TW-000: Every request gets a tier; only the Full tier runs waves

Owner instruction, 2026-11-11, replacing the 2026-08-18 "orchestrate every request" rule to spend
fewer tokens without losing effectiveness. Pick a tier for each request and name it in the reply:

- **Inline** — a question, a config tweak, or a change of a few lines. Just do it, then verify it.
- **Standard** — a normal feature or fix. File a task in `backlog/tasks/` with acceptance criteria
  sharp enough to fail, write the asian-dad rubric before any code (TW-001), implement directly or
  with **one** agent, verify (TW-003, TW-004), grade, report.
- **Full** — migrations, production data, several file territories at once, or risky/unclear work.
  The Standard steps plus session-orchestrator agents in waves, one per file territory (TW-002).

When torn between two tiers, take the higher. Verification against reality (TW-004, TW-00A step 3)
applies to every tier: it is what catches bugs, and it is not the overhead this rule removes.

Dispatch agents with an explicit `model`: `sonnet` for implementers, test-writers and docs, `haiku`
for read-only sweeps; Opus stays the coordinator and grader. Brief each agent with the exact files and
the facts already established, so it does not re-derive them.

## TW-00A: What "Done" means

Owner instruction, 2026-08-18. A task is Done only when **all** of these are true. Anything less is
In Progress, whatever the code looks like:

1. **Committed** — the change is in a commit, staged file by file (TW-002), not left in the working
   tree.
2. **Pushed — all of it.** `git log <branch> --not origin/<branch>` must print nothing before the
   PR is merged. A branch can be "pushed" and still be behind its local HEAD, and GitHub merges what
   **it** has, not what you have.
3. **Working** — verified in the real thing, not argued from the code (TW-004). Tests green, and the
   browser/CLI measurement done for anything user-facing.
4. **Squash-merged to `main`** — via a PR, with CI green before the merge.
5. **Branch deleted — remote and local, and only after step 6.** Never with
   `gh pr merge --delete-branch`: that flag deletes at *merge* time, which is before production has
   been verified, so it inverts steps 5 and 6. Merge with `--squash` alone, verify, then delete.
6. **Production verified** — the deploy finished, the health endpoint answers, and the *specific*
   change is observable in what production serves. A green workflow is not that check.

Consequences worth stating, because they have already bitten in this repo:

- A stacked PR whose base branch is deleted gets **auto-closed by GitHub** and cannot be reopened or
  retargeted. Rebase the child onto `main`, force-push with `--force-with-lease`, and open a
  replacement PR referencing the closed one.
- Merging to `main` does NOT deploy (TASK-275). Deploys are manual and the owner's call:
  `gh workflow run deploy-container-apps.yml --ref main`. `scripts/start-container.sh` runs
  `migrate --noinput` under `set -e`, so that deploy is the moment any migration reaches the
  production database, and a live 200 afterwards is what proves the migration applied. Record the
  rollback image before deploying (TW-006).
- A task with an unverifiable criterion does NOT get marked Done to tidy the board. Leave it In
  Progress and name the blocker (TW-005).

- **This cost a fix on 2026-08-24.** Wave 4's PR #79 was merged with `--delete-branch` while commit
  `a86b8e5` (TASK-185, the mailbox alert that had emailed the owner 83 times) had never been pushed.
  The merge silently shipped three of the four tasks, and deleting the branch orphaned the fourth —
  recoverable only because the object was still in the local object database. Both halves of that are
  now steps 2 and 5 above. The tell was available and unread: `gh pr merge` printed an 8-file diff
  for a wave that touched twelve.

## TW-001: Rubric before work, never after

Write the asian-dad rubric **before** any implementation exists, derived from the task's acceptance
criteria, one criterion per AC plus any genuine minimum-functioning floors. Store it at
`.claude/.asian-dad/<slug>-rubric.json` (gitignored) and do not show it to implementing agents.

A rubric written after seeing the output grades the output, not the brief.

## TW-002: Dispatch in waves, not all at once

- One agent per **file territory**, never two agents editing the same file. Two agents were pointed
  at `App.tsx` simultaneously in this session; it happened to survive because both made targeted
  string edits, but that was luck, not design.
- Coupled tasks go to **one** agent (TASK-67/68 shipped together because fixing the nav without the
  tap targets would have added more tiny targets).
- Independent tasks run in parallel.
- Agents never `git commit`, `git push`, `git reset`, `git checkout --`, or `git stash`. The
  coordinator stages and commits, so partial agent work is never swept in.

## TW-003: Verify agent claims independently

Read the diff and re-check the load-bearing claim yourself. Agents in this session were mostly
honest — two correctly reported "already implemented, I verified instead of rebuilding", and one
refused to claim an AC it could not measure — but their verdicts are evidence, not proof.

Where an agent lacks a capability (subagents here have **no browser tools**), the coordinator does
that verification.

## TW-004: Measure, do not assert

If an AC says "verified at 360px and 430px", produce numbers. Reasoning from CSS or code is a
hypothesis.

Known-good techniques in this repo:
- Window resizing did **not** change the page viewport on this display. Measure responsive behaviour
  with a **same-origin iframe** at the target width and read `getBoundingClientRect()`.
- Backend: `cd backend && uv run pytest -q`. Tests are hermetic — sqlite `:memory:` via
  `config/settings_test.py`, fixture candidate-evidence files via `tests/conftest.py`. They never
  touch production Neon or the real CV workspace.
- Frontend: `npx tsc --noEmit` and `npm test`.

## TW-005: A checked box must be true

- Never check an AC on partial work. Leave it unchecked and **name the blocker** in the notes,
  including the exact command or credential needed to close it.
- An AC that no implementation can satisfy gets **reworded through its own filed task**, never
  silently relaxed — see TASK-64 (untestable "open action") and TASK-66 (a 30s target that was
  impossible because the provider round-trip alone is 50-160s). Weakening a criterion needs a paper
  trail more than clarifying one does.
- Record what was *already* done rather than rewriting it for the sake of activity. TASK-9 and
  TASK-5 AC1/AC2 were already satisfied by earlier commits and were verified, not rebuilt.

## TW-006: Nothing ships unverified

CI (`.github/workflows/deploy-container-apps.yml`) runs backend tests, frontend tests and typecheck,
and the deploy job depends on it. Do not weaken or bypass that gate. Its first run caught that the
suite had never been portable — several tests depended on an untracked personal file and passed only
on the author's machine.

Production deploys only when the owner runs `gh workflow run deploy-container-apps.yml --ref main`
(TASK-275); pushing to `main` runs tests only. It is the owner's call, not an agent's. Record the
rollback image before deploying, and verify the live health endpoint afterwards rather than trusting the
workflow's own check.
