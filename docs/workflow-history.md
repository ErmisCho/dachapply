# Workflow history

Why the rules in `CLAUDE.md` exist. Moved out of `CLAUDE.md` on 2026-11-11 so it stays short; not loaded
into every session.

## Green suites that were still wrong

Each of these passed every available check and was still wrong:

- **TASK-163** — 830 backend tests, 109 frontend tests, clean typecheck. Against production it fired
  on 8 of 321 messages and 2 of 5 suggestions were wrong. Three more rounds were needed. Its task file
  predicted ~117 matches from an ad-hoc tokenizer; the real answer was 5, and the estimate's looseness
  was itself the bug being fixed.
- **TASK-162** — 839 tests green. Its dry-run wanted to demote 26 genuine messages, including a real
  interview thread and 17 ATS confirmations, to `not_job_related`.
- **TASK-165** — the planned fix, derived from a correctly-read stylesheet, would have made the bug
  worse; measuring the boxes showed the header was never sticky at all.
- **TASK-134** — parked for sessions on "the rig drops mousedown", which was never measured and was
  false. The real cause was a product bug.

## Localhost white screens

A `git pull` advances the backend while the compiled frontend bundle stays put, which has
white-screened the owner's board more than once. Hence the rebuild-and-check step before "done".

## Migrations and the live board

A migration reaches production on the next deploy, and committing one has broken the live board,
because localhost runs against the production database. Hence migrations always need the owner's
go-ahead before merging.

## The workflow tiers

From 2026-08-18 to 2026-11-11 every request ran the full workflow: task file, sealed rubric,
session-orchestrator waves, verification, grading. Tokens ran out quickly, because every subagent
starts cold and re-reads its context. On 2026-11-11 the owner chose to tier it (Inline / Standard /
Full) and run mechanical agents on cheaper models, keeping verification against reality in every tier.
