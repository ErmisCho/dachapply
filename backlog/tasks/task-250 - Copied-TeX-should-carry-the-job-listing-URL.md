---
id: TASK-250
title: Copied TeX should carry the job listing URL
status: To Do
assignee: []
created_date: '2026-09-25 14:40'
updated_date: '2026-09-25 14:54'
labels:
  - backend
  - ux
dependencies: []
priority: medium
type: enhancement
ordinal: 249000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-09-25: after generating, the TeX is copied to the clipboard and pasted into ChatGPT for further work. ChatGPT then has the documents but not the posting they were written for, so the URL has to be found and pasted separately.

services/cv_tasks.py:232 _clipboard_contents builds that string from the artifact files alone: a single file is returned verbatim, and two files are joined under '% ===== <name> =====' headers. It receives only the artifacts dict, so the job - and therefore job.url - is not in scope at that call site; the three callers (generation, readjustment, recompile) each have the job available.

Note the field to read is job.url, the original listing link, not the internal /jobs/<id> page.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The clipboard contents produced after a generation, a readjustment and a recompile all begin with the job's listing URL, so pasting into ChatGPT carries the exact posting without the user fetching it
- [x] #2 The line is a LaTeX comment, so pasting the same clipboard into a .tex file still compiles
- [x] #3 A job with no stored URL produces the clipboard exactly as it does today - no empty label, no placeholder
- [x] #4 The single-file case gains the line too, not only the two-file case that already has a header
- [x] #5 Covered by a backend regression check asserting the URL is present for a job that has one and absent for a job that does not
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Shipped as a wrapper, and the brief was refused for a measured reason

The dispatch said to thread the job into _clipboard_contents. The agent refused and was right:
tests/test_api.py:1248 monkeypatches that helper with a single-positional lambda
(`lambda artifacts:''`). A two-argument signature would raise TypeError inside _run's blanket
`except Exception`, and since that test asserts only on an `order` list it would have stayed GREEN
while no longer exercising its connection-recycling regression at all. Verified by the coordinator by
reading line 1248 rather than taking the report's word.

So _clipboard_contents keeps its artifacts-only signature and a three-line _clipboard_payload
(artifacts, job_url) prepends the line. That also covers the single-file branch, which returns
contents verbatim and is the one AC4 is about.

## Call sites: three, covering four routes

    cv_tasks.py:323  _run           generation AND readjustment (revision re-enters start_cv_task)
    cv_tasks.py:347  _run_compile   recompile
    cv_tasks.py:373  start_cv_noop_task  the 'no further CV changes required' route

The third was not in the brief. It has only job_id, so it reads the URL with a single indexed
values_list query rather than changing a signature that would have pulled views.py into scope.

## LaTeX behaviour measured with a real pdflatex, not reasoned

Using https://jobs.example.com/apply?ref=a%20b&id=7_8#top against TeX Live 2025:

    as a % comment (what ships)   exit 0, PDF produced
    same URL as body text         exit 0 -- but the text silently truncates at the %, losing the link
    percent-free URL as body text exit 1, '! Missing $ inserted.', no PDF

So no escaping is wanted: inside a comment TeX discards to end of line, and escaping would corrupt
the URL the owner pastes into ChatGPT. The one real hazard is a newline inside the stored value,
which would close the comment; it is collapsed with the same idiom _learn_application_preference
already uses, and a test pins it.

## Verification

Agent: 1230 passed, and 4 of its 5 new tests fail against simulated pre-fix behaviour (the fifth is
the no-URL case, which must not change). Coordinator: call-site census re-run from source, the
monkeypatch at test_api.py:1248 read directly, helper body reviewed, full suite re-run.
<!-- SECTION:NOTES:END -->
