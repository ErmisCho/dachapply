# Default Task Workflow (Always-on)

Backlog work in this repo is done with **session-orchestrator agents in waves** and graded with the
**asian-dad-eval** skill. This is the default, not something to be asked for each time. It exists
because this session repeatedly found that unverified claims — from agents and from earlier passes —
were wrong in ways only measurement caught.

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

Production deploys on push to `main` and is the owner's call, not an agent's. Record the rollback
image before pushing, and verify the live health endpoint afterwards rather than trusting the
workflow's own check.
