---
id: TASK-69
title: Purge the leaked personal data export from public git history
status: To Do
assignee: []
created_date: '2026-08-16 00:43'
labels:
  - security
  - privacy
  - P0
dependencies: []
priority: high
ordinal: 74000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Commit 912b853 (2026-05-22) added `dachapply-full-2026-05-22.json` — a complete account export (~59 KB) containing the owner's job-search history, application statuses, and two personal email addresses. Commit a08f5b8 removed and gitignored the file, but a deleted file stays permanently fetchable from history, and `gh repo view ErmisCho/dachapply --json visibility` returns PUBLIC.

Verified 2026-08-16: `git show 912b853:"dachapply-full-2026-05-22.json"` returns the full export including the personal email in the user record; `git log --all --diff-filter=A -- "*dachapply-full*"` confirms 912b853 is the adding commit.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The export blob is unreachable from every ref on GitHub (history rewritten with git-filter-repo or BFG; `git log --all -- "dachapply-full-2026-05-22.json"` is empty on a fresh clone)
- [ ] #2 The force push is performed by the owner personally, after coordinating any open branches (PSA-003 — agents never force-push)
- [ ] #3 A full-history secret/PII sweep (gitleaks or trufflehog over all refs) confirms no other personal exports or credentials remain reachable, with the command and result recorded in the task notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`git filter-repo --invert-paths --path "dachapply-full-2026-05-22.json"` on a fresh clone, then force-push all refs. Note the limits honestly when closing: existing forks/clones and GitHub's commit-view cache can retain the blob — GitHub support can be asked to run GC on cached views. The file contains no credentials, so this is exposure minimization, not rotation. Do this before TASK-70 stores any backup dumps anywhere near the repo.

### Investigation (2026-08-16) — AC3 executed; AC1 as written is not achievable by a force push

Worked on a `--mirror` clone in scratch space, never on the working repo. The rewrite itself was
**not run**: `git filter-repo` was refused by this session's command policy, and AC2 assigns the push
to the owner regardless. What follows is measured, not assumed.

**Blob identity, so the fix can be verified afterwards:**

    path    dachapply-full-2026-05-22.json
    blob    59fcfc77187f88491fd3b1c11a6d4d18453ef855
    size    59,109 bytes
    PII     2 distinct personal email addresses
    added   912b853 (the only commit that ever added it)

**Finding 1 — a force push cannot satisfy AC1, because `refs/pull/1/head` is public and unwritable.**
`git ls-remote` run anonymously against the public URL advertises six refs, one of which is
`refs/pull/1/head`. Every one of the four refs that existed at clone time reaches 912b853:

    REACHABLE: refs/heads/feature/task-61-cv-generation-ux
    REACHABLE: refs/heads/main
    REACHABLE: refs/heads/worktree-backlog-discovery-2026-08-16
    REACHABLE: refs/pull/1/head          <-- GitHub-managed, cannot be force-pushed or deleted

Rewriting and force-pushing every branch leaves `refs/pull/1/head` pointing at the pre-rewrite tip,
so `git fetch origin refs/pull/1/head` still retrieves the blob — from a public repository, with no
authentication. AC1's own stated test (`git log --all` on a fresh clone) would *pass*, because a
normal clone does not fetch `refs/pull/*`. That is the trap: the check the AC names would report
success while the data stayed downloadable.

**Closing AC1 therefore requires a GitHub Support request**, not just the push: ask them to purge the
pull-request ref and run GC on cached commit views. Do not check AC1 on the push alone.

**Finding 2 — coordinate four branches, one of which belongs to a live session.** AC2 says "after
coordinating any open branches". At the time of writing, origin carries:

    main                                        d8288a1
    feature/task-61-cv-generation-ux            4fe65c5   (merged via PR #1; deletable)
    worktree-backlog-discovery-2026-08-16       170e10b
    worktree-coach-absorption-2026-08-16        15b76e8   <-- appeared mid-session; TASK-104..106

`worktree-coach-absorption-2026-08-16` was pushed *during* this session by another session and is not
merged. All four contain 912b853. If it is rewritten while that session is mid-flight, the branch
either gets stranded or is re-pushed on the old history and reintroduces the blob. Delete the two
merged/abandoned branches first, and rewrite only once the coach-absorption work has landed.

**Finding 3 — AC3 ran, and did not come back clean.** AC3 stays unchecked for that reason.

    gitleaks git . --log-opts="--all" --redact
    -> 147 commits scanned, 5.08 MB, "no leaks found"

No credentials anywhere in history — that half of AC3 holds. But gitleaks looks for secrets, not for
personal data, so it cannot see the very file this task is about. A second sweep read all **1,591
blobs** reachable from every ref and matched email addresses, ignoring synthetic domains
(`example.test`, `dachapply.test`, `dachapply.com`):

    real addresses reachable from history:   5 distinct
    of those, still present in current main:  4 distinct, 11 occurrences

One earlier count of this was wrong and is worth recording, because the mistake is reusable: a
`your-…@gmail.com` placeholder in `.env.example` was first counted as real, since the filter excluded
synthetic *domains* and `gmail.com` is not one. Placeholders hide behind real domains — filter on the
local part too.

So purging the export does **not** end the exposure. See TASK-107 — the remaining addresses are in
live tracked files, including a third party's work address at a real employer's domain sitting in a
committed test file. Those are a bigger privacy problem than the export, because they belong to
someone who never chose to be in this repository, and because they are readable on `main` today
rather than requiring a history fetch.

**Order of operations, revised:** TASK-107 first (rewrite touches the same blobs, and a rewrite done
before the addresses are removed simply has to be done twice), then the branch cleanup in Finding 2,
then the rewrite, then GitHub Support.

**Prepared command sequence for the owner** — run from a scratch directory, not the working repo:

    pip install git-filter-repo
    git clone --mirror https://github.com/ErmisCho/dachapply.git repo.git
    cd repo.git
    git update-ref -d refs/pull/1/head              # unpushable; drop before the mirror push
    git filter-repo --invert-paths --path 'dachapply-full-2026-05-22.json' --force
    git cat-file -e 59fcfc77187f88491fd3b1c11a6d4d18453ef855 && echo "STILL PRESENT" || echo "purged"
    git push --force --mirror https://github.com/ErmisCho/dachapply.git

Then re-verify from a genuinely fresh clone, and separately confirm the ref that the AC's own test
misses:

    git clone https://github.com/ErmisCho/dachapply.git verify && cd verify
    git log --all -- "dachapply-full-2026-05-22.json"        # must be empty
    git fetch origin 'refs/pull/*:refs/pull/*' && git log --all -- "dachapply-full-2026-05-22.json"
    # ^ if this is non-empty, AC1 is not met yet -- open the GitHub Support request

### Update 2026-08-16 (evening) — scope grew, and the push is blocked on a live session

**Two blockers, one of them not mine to override.**

1. `git filter-repo` is refused by this session's command policy, and AC2 assigns the push to the
   owner personally regardless.
2. **A parallel session is mid-flight.** `worktree-coach-absorption-2026-08-16` committed at
   19:52 today (`aaeff70`, "reconcile with owner-checklist branch"), and its worktree is still
   checked out at `.claude/worktrees/coach-absorption-2026-08-16`. Rewriting history now would
   strand that checkout, or it would re-push the old history on top and reintroduce every blob this
   task exists to remove. AC2's "after coordinating any open branches" is the whole reason this is
   not a five-minute job. **Wait for that branch to land in `main`, then rewrite.**

**The rewrite now has to remove two different things, and only one of them is a file.** TASK-107
scrubbed three real recruiter addresses out of `backend/jobradar/tests/test_api.py`, but only on
`main` going forward — every commit before that still contains them, and they are inside a file that
must keep existing, so `--invert-paths --path` cannot touch them. That needs `--replace-text`.

Current state of `origin`, measured:

    main                                    export in history, fixture PII in history, tips clean
    feature/task-61-cv-generation-ux        fixture PII at tip -- merged via PR #1, safe to delete
    worktree-backlog-discovery-2026-08-16   fixture PII at tip -- 79 files behind main, safe to delete
    worktree-coach-absorption-2026-08-16    fixture PII at tip -- LIVE, do not touch

Delete the two stale branches before rewriting; every branch that survives is one more ref that has
to be rewritten and force-pushed consistently.

**Revised sequence.** The replacements file is *generated from git* rather than typed, so the real
addresses never get written into a file in this public repo:

    pip install git-filter-repo
    git clone --mirror https://github.com/ErmisCho/dachapply.git repo.git
    cd repo.git
    git update-ref -d refs/pull/1/head          # GitHub-managed, unpushable; drop before mirror push

    # Build the replacement expressions straight out of the pre-fix blob.
    git log --all --format=%H -- backend/jobradar/tests/test_api.py | while read sha; do
      git show "$sha:backend/jobradar/tests/test_api.py" 2>/dev/null
    done | grep -ohE '[A-Za-z0-9._%+-]+@ebcont\.com' | sort -u         | sed 's|$|==>redacted@example.test|' > ../replacements.txt
    echo 'EBCONT (BMJ)==>Acme Corp (Example)' >> ../replacements.txt
    wc -l ../replacements.txt        # expect 3 (two addresses + the company name)

    git filter-repo --invert-paths --path 'dachapply-full-2026-05-22.json'                     --replace-text ../replacements.txt --force

    git cat-file -e 59fcfc77187f88491fd3b1c11a6d4d18453ef855 && echo "STILL PRESENT" || echo "purged"
    git push --force --mirror https://github.com/ErmisCho/dachapply.git

Then verify from a genuinely fresh clone, including the ref AC1's own test does not fetch:

    git clone https://github.com/ErmisCho/dachapply.git verify && cd verify
    git log --all -- "dachapply-full-2026-05-22.json"        # must be empty
    git grep -c ebcont $(git rev-list --all) -- backend/jobradar/tests/test_api.py   # must be empty
    git fetch origin 'refs/pull/*:refs/pull/*' && git log --all -- "dachapply-full-2026-05-22.json"

If that last command is non-empty, AC1 is not met and the support request below is what closes it.

### Draft GitHub Support request (AC1's remaining half)

Send at https://support.github.com/request — the pull-request ref cannot be deleted or force-pushed
by a repository owner, so this is the only route.

> **Subject:** Purge cached pull-request refs and commit views after a history rewrite (PII)
>
> Repository: ErmisCho/dachapply (public).
>
> I have rewritten this repository's history with git-filter-repo and force-pushed all branches, to
> remove a file that contained personal data (a full account export including personal email
> addresses) and to redact third-party contact details that had been committed into a test fixture.
>
> The rewritten history is no longer reachable from any branch, but the old commits are still served
> from `refs/pull/1/head`, which I cannot delete or force-push as the repository owner. I have
> confirmed this ref is advertised to anonymous clients via `git ls-remote`.
>
> Please could you: (1) purge the pull-request refs for this repository so the pre-rewrite commits are
> no longer fetchable, and (2) run garbage collection so the old commits are not served from cached
> commit views.
>
> Affected blob for reference: `59fcfc77187f88491fd3b1c11a6d4d18453ef855`
> (`dachapply-full-2026-05-22.json`, added in commit `912b853`).
>
> Thank you.

Say honestly, when closing this, that forks and existing clones cannot be reached by any of the above.

<!-- SECTION:NOTES:END -->
