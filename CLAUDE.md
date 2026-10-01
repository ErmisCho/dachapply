# CLAUDE.md

Instructions for Claude Code in this repository. `AGENTS.md` covers the backlog tooling and session
config; this file covers how work is done.

## Always use session-orchestrator agents and the asian-dad-eval skill

Owner instruction, stated 2026-08-18 and repeated 2026-08-21 with "remember that, put it as part of
CLAUDE.md". It is a standing default, not something to ask about per task and not a heavyweight mode
reserved for large features.

**Whenever the owner asks for something to be done:**

1. File it as a task in `backlog/tasks/` with acceptance criteria sharp enough to fail.
2. Write the asian-dad rubric from those criteria **before any implementation exists**, and keep it
   out of the implementers' reach.
3. Dispatch **session-orchestrator** agents, one per file territory, never two in the same file.
4. Verify the agents' load-bearing claims yourself, against the real thing.
5. Grade against the sealed rubric and report the verdict.

The trigger is the owner asking for work, not the size of the work. The only exemptions are a
question that is answered rather than built, and a change so small that filing it would cost more
than doing it — and even then, name which exemption was used rather than skipping silently.

`.claude/rules/task-workflow.md` is the full version of this (TW-000 through TW-006) and is the
authority when the two disagree. `.claude/rules/parallel-sessions.md` governs sharing the repo with
other sessions.

## Verify against reality, not against a green suite

This is the rule the rest of the workflow exists to serve, and this repo has paid for it repeatedly.
Recorded examples, each an implementation that passed every available check and was still wrong:

- **TASK-163** — 830 backend tests, 109 frontend tests, clean typecheck. Against production it fired
  on 8 of 321 messages and 2 of 5 suggestions were wrong. Three more rounds were needed.
- **TASK-162** — 839 tests green. Its dry-run wanted to demote 26 genuine messages, including a real
  interview thread and 17 ATS confirmations, to `not_job_related`.
- **TASK-165** — the planned fix, derived from a correctly-read stylesheet, would have made the bug
  worse; measuring the boxes showed the header was never sticky at all.
- **TASK-134** — parked for sessions on "the rig drops mousedown", which was never measured and was
  false. The real cause was a product bug.

Practical consequences:

- A bulk data change gets a **dry-run-by-default management command**, never a migration, so a human
  can inspect what would change before anything is written.
- Numbers in a report are measured or they are not stated. An agent with no production access says so
  rather than estimating.
- A coordinator estimate is not evidence. TASK-163's task file predicted ~117 matches from an ad-hoc
  tokenizer; the real answer was 5, and the estimate's looseness was itself the bug being fixed.

## Finish on the owner's machine

Owner instruction, 2026-08-21: *"always make sure that localhost works when you complete a task."*

Before calling anything done: `cd frontend && npm run build` **in the owner's checkout**, confirm the
served bundle hash matches `frontend/dist/index.html`, and load the page to assert it rendered — a
200 is not enough. A worktree build never reaches them, and a `git pull` advances the backend while
the compiled bundle stays put, which has white-screened their board more than once.
