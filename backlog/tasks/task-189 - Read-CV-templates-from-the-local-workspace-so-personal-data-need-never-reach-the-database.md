---
id: TASK-189
title: Read CV templates from the local workspace so personal data need never reach the database
status: Done
assignee: []
labels:
  - backend
  - cv-generation
  - privacy
dependencies:
  - TASK-99a
priority: high
ordinal: 189000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-24, after being asked three times to approve importing their templates and photo into
production: *"well then if the CV generation is local, why upload the data in the cloud?"*

There is no good answer, and this task exists because the coordinator kept proposing one anyway.

**The regression, stated plainly.** TASK-99a replaced the `CODEX_CV_WORKSPACE` glob with per-account
`CvAsset` rows and gave `user_cv_assets()` no fallback of any kind — deliberately, and that
no-fallback property is correct and must survive this task. But the owner's local server reads the
**production** database, which has **0 `CvAsset` rows**, so CV generation is broken on the only
machine where it can run. The proposed remedy was `import_cv_assets --apply`, which writes the
owner's name, address, phone, profile links and a 1.23 MB photograph of their face into Neon and its
backups.

**Why that trade buys nothing.** Measured 2026-08-24: the container image installs no LaTeX (0
references to `texlive`/`pdflatex`/`latexmk` in the Dockerfile), and `CODEX_CV_ENABLED` defaults to
`DEBUG` and is never set by `deploy-container-apps.yml`, so it is `False` in production. Generation
therefore cannot run in the cloud, and storing the inputs there enables nothing. The only argument
left is pre-positioning for TASK-99b — which is blocked, and whose own notes record that "keep
generation local and say so honestly" is a legitimate outcome.

**So the source of a local-only capability should be local.** `CODEX_CV_WORKSPACE` is already
per-machine (the owner's `.env` pins `C:\latex`); it is not a hardcoded path and never was the thing
TASK-99a was fixing. What TASK-99a actually removed was the *hardcoded* `CVs/Picture.jpg` and the
implicit "whoever runs this owns these files" assumption. Reading a **configured, per-machine**
workspace for the account that owns that machine keeps both fixes intact.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With no `CvAsset` rows and a configured workspace, CV generation works on the owner's machine — proven by a real end-to-end run producing a real PDF, not a unit test
- [ ] #2 No personal data is written to any database by this path: after a full generation, `CvAsset.objects.count()` on the production database is still 0, measured and stated
- [ ] #3 `user_cv_assets()` keeps its no-fallback property between ACCOUNTS — the workspace is resolved for the requesting user only, and one account can never read another's templates, photo, or workspace. The TASK-99a widening test still fails when widened
- [ ] #4 Where a `CvAsset` row exists for a user, it WINS over the workspace — so TASK-99a's stored-asset path stays the primary one and this is a fallback, not a replacement
- [ ] #5 On a deployment with no workspace configured, behaviour is unchanged from today: a stated, non-crashing message naming what is missing
- [ ] #6 `import_cv_assets` still works and is still dry-run-by-default — this task removes the *need* to run it, not the option
- [ ] #7 The precedence rule is recorded where the next reader will find it, including why a local-only capability reads a local-only source
- [ ] #8 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do NOT restore the old module-level `TEMPLATES` dict or `latest_cv_template()`. Those resolved
templates with no user at all, which is the actual defect TASK-99a fixed. The fallback must be
per-user: this account, this account's configured workspace, nothing shared.

The photo needs the same treatment and the same care — `CVs/Picture.jpg` must not become hardcoded
again. It is "the photo in this user's workspace", not "the photo".

AC2 is the point of the whole task. If an implementation ends up writing rows as a side effect of
generating — caching parsed templates into `CvAsset`, for instance — it has failed, however
convenient that cache is.

TASK-99a's byte-identical result is the regression bar: the owner's own build of
`English - AI Engineer (base)_v_1.5.tex` is 1,357,973 bytes and `CVs/Picture.jpg` is 1,230,417 bytes.
A generation through this path must still produce that PDF.
<!-- SECTION:NOTES:END -->
