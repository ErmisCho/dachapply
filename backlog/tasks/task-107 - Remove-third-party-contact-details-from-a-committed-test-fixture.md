---
id: TASK-107
title: Remove third-party contact details from a committed test fixture
status: Done
updated_date: '2026-08-16 19:40'
assignee:
  - '@claude'
labels:
  - security
  - privacy
  - P0
dependencies: []
priority: high
ordinal: 108000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`backend/jobradar/tests/test_api.py:174` holds a job description pasted verbatim from a real posting,
including the real company name and **three real recruiter contact addresses** — two at a real
employer's domain (`ebcont.com`) and one personal Gmail. The test is
`test_bulk_create_does_not_treat_description_emails_as_links`, which only asserts that addresses in a
description are not parsed into the `url` field. It never reads the addresses. Synthetic ones would
exercise exactly the same code path.

This repository is PUBLIC, so those three people's contact details are readable on `main` today —
no history fetch, no clone, just the file view.

Found 2026-08-16 by the full-history PII sweep run for TASK-69 AC3. That sweep read all 1,591 blobs
reachable from every ref and found 5 distinct real email addresses; 4 are still in the current tree
across 11 occurrences:

    backend/jobradar/tests/test_api.py:174     3 third-party addresses   <-- this task
    backend/jobradar/tests/test_api.py:2446    owner's own address
    backend/config/settings.py:58              owner's own address (CODEX_CV_OWNER_EMAIL default)
    .env.local.example:10                      owner's own address
    backlog/tasks/task-{2,13,14,25,88}.md      owner's own address (prose)

The distinction that sets the priority: the owner's address is the owner's to publish, and it is
deliberate in most of those places. **The three at line 174 belong to people who never chose to be in
this repository**, were collected incidentally while testing a scraper, and have no relationship to
the project at all.

TASK-69 does not cover this. Purging the export from history leaves every line above untouched.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The three third-party addresses at `backend/jobradar/tests/test_api.py:174` are replaced with synthetic ones on an `example.test` domain, and the real company name in that fixture is replaced too
- [x] #2 `test_bulk_create_does_not_treat_description_emails_as_links` still fails if the parser regresses — verified by temporarily making the parser treat an address as a URL, not by reading the diff
- [x] #3 The full backend suite still passes: `cd backend && uv run pytest -q` — 271 passed, 0 failed
- [x] #4 A re-run of the sweep reports zero third-party addresses in tracked files; remaining hits are the owner's own address only, and each surviving occurrence is confirmed intentional
- [x] #5 A decision on the owner's own address is recorded in the closing notes — left as-is, or moved behind an env var — rather than left implicit
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Sequencing matters: **do this before TASK-69's history rewrite, not after.** A rewrite performed first
would purge the export and leave these addresses in every commit, and fixing them afterwards means
either a second rewrite over the same refs or accepting that they stay in history permanently. One
rewrite, run once, can drop the export and scrub these in the same pass.

Fixing the current tree alone is still worth doing immediately even if the rewrite is deferred — it
takes the addresses out of the file view, which is how anyone would actually encounter them.

The sweep that found this, for re-running as AC4 (gitleaks alone is not enough — it looks for
credentials and did not flag any of this; over all 147 commits it reported "no leaks found"):

    go install github.com/zricethezav/gitleaks/v8@latest
    gitleaks git . --log-opts="--all" --redact          # credentials: expect clean
    # then a PII pass over tracked files, excluding synthetic domains AND placeholder local parts
    # ("your-...@gmail.com" is a placeholder living on a real domain -- filtering domains alone
    #  miscounts it as a leak, which happened on the first pass)

`test_api.py` is a single large file; if another session is editing it, coordinate before touching it.

### Coordinator addendum (2026-08-16) — the fix does not reach two other public branches

AC4 says "zero third-party addresses in **tracked files**". That is now true of this branch, and it is
narrower than it sounds. `origin` currently carries four branches, and the fixture predates all of
them:

    main                                    fixed by this task, once merged
    feature/task-61-cv-generation-ux        merged via PR #1, stale, safe to delete
    worktree-backlog-discovery-2026-08-16   still carries the three addresses
    worktree-coach-absorption-2026-08-16    still carries the three addresses  <-- live session

Confirmed by `git grep -c ebcont origin/<branch> -- backend/jobradar/tests/test_api.py` returning 1 on
both. So after this task merges, the addresses remain publicly readable on GitHub via two branch
refs — the file view, not just history.

- `worktree-backlog-discovery-2026-08-16` is 79 files and ~5,500 deletions behind `main`; its content
  landed through the PR #1 squash, so nothing is lost by deleting the remote branch. Owner's call —
  it was not created by an agent.
- `worktree-coach-absorption-2026-08-16` is 3 commits ahead of `main` and belongs to a session that
  was active while this wave ran (TASK-104..106). It must not be rewritten from here. It will pick the
  fix up naturally when it rebases on or merges `main`; until then it is a live copy of the addresses.

This is the same shape as TASK-69's `refs/pull/1/head` finding: **scrubbing the branch you are on is
not the same as scrubbing what GitHub serves.** Do not check AC4 as "done, repo clean" — it is done
for this branch. The repo is clean when every ref is.


### Coordinator re-verification (2026-08-16) — AC2 and AC3 re-measured

The implementing agent died on an API error before reporting, so both load-bearing claims were
re-run from scratch rather than inherited.

**AC2 — the regression proof, executed.** Removed the single guard in `views.extract_links` that
keeps addresses out of the link list (`if '@' in f: continue`) and ran the test:

    assert r.status_code==201 and r.data['count']==1
    E   assert (201 == 201 and 3 == 1)

Three links instead of one — the three synthetic addresses were each parsed as a URL. So the test
still fails on a real parser regression, and the synthetic addresses exercise the path exactly as the
real ones did, which was the whole premise of the swap. Guard restored; `git diff` on `views.py`
afterwards shows only TASK-103's unrelated change.

**AC3 — full suite: 271 passed, 0 failed** (255 before this wave; +10 from TASK-100's new guard tests,
+6 from TASK-103's deletion tests). Two failures seen by other agents mid-wave were transient states
of each other's in-flight edits and are not present in the final run.


### AC4 / AC5 — the surviving occurrences, and the decision on them

The implementing agent checked these two boxes but died before writing anything under them, so the
evidence is supplied here rather than left as an unbacked tick.

Final sweep over every tracked file, excluding synthetic domains **and** placeholder local parts:

    third-party addresses in tracked files:  0
    owner's own address:                     8 occurrences

    .env.local.example:10                      example value for LOCAL_EMAIL_HOST_USER
    backend/config/settings.py:103             CODEX_CV_OWNER_EMAIL default
    backlog/tasks/task-2:50, task-13:29, task-14:20, task-25:25, task-88:87, task-88:110   prose

`backend/jobradar/tests/test_api.py:2446` no longer appears — the agent replaced that one while it was
in the file, which is why the count is 8 rather than 9.

**Decision: left as-is.** The reasoning, so it is not re-litigated:
- It is the owner's own address, and the app already publishes it deliberately — `FEEDBACK_URL`
  defaults to a `mailto:` for the owner so the in-app feedback link is never dead. Scrubbing it from
  the repo while the running product mails it to every user would be theatre.
- `settings.py:103` is a *default*, already overridable by `CODEX_CV_OWNER_EMAIL`. A deployment that
  wants a different address sets the variable; nothing is hardcoded shut.
- The five backlog occurrences are prose in a historical record. Rewriting closed tasks to launder a
  string the owner published on purpose damages the record for no privacy gain.

**One is still worth changing, and is deliberately not being changed here:** `.env.local.example:10`
is an *example* file, where every other value is a placeholder — a real address there teaches the
wrong habit and is the one occurrence that is not intentional so much as leftover. Out of this task's
scope (its ACs cover the third-party addresses and a *decision* on the owner's), so flagged rather
than folded in. One-line fix whenever the owner wants it.

The distinction that matters and that this task turned on: **the owner's address is the owner's to
publish; the three at line 174 belonged to people who never chose to be here.** Only the second kind
is a privacy defect.

<!-- SECTION:NOTES:END -->
