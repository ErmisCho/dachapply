---
id: TASK-111
title: Serve the local app against the remote database by default
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 22:20'
labels:
  - backend
  - dev-experience
dependencies: []
priority: high
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-08-16 (verbatim intent: "the local version should also point to the remote db
— both should be pointing at the same remote db"). TASK-100's guard, as shipped, blocked ALL local
manage.py commands from a .env-sourced DATABASE_URL, which made plain local `runserver` refuse to
start against Neon — but running the local app against the same data as the deployed site is the
owner's actual daily workflow.

This task amends TASK-100's AC1 through its own paper trail rather than silently relaxing it
(house rule, cf. TASK-64/66): serving commands are exempted from the guard; every other command
keeps the protection that motivated TASK-100 in the first place (a habitual local `migrate` or
`flush` reaching production).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `manage.py runserver` and `manage.py check_mailbox` start against a .env-sourced DATABASE_URL with no flag — the local app and the deployed site share the remote database
- [x] #2 All other manage.py commands (migrate, flush, dbshell, shell, loaddata, …) keep TASK-100's behaviour: refused unless DACHAPPLY_ALLOW_PROD_DB=1 is set for that command
- [x] #3 The guard's tests cover the exemption and the still-blocked cases; the full suite passes
- [x] #4 The README local-workflow section and the guard's error message describe the new split
<!-- AC:END -->

## Outcome (2026-08-16)

`LOCAL_PROD_DB_SERVING_COMMANDS = {'runserver', 'check_mailbox'}` in config/settings.py;
`local_db_guard_blocks()` gains an argv parameter (defaults to sys.argv) and returns False for
serving commands before any other check. check_mailbox is a "server" here deliberately: its whole
purpose is writing suggestions where the website can show them, and this also removes the
DACHAPPLY_ALLOW_PROD_DB=1 prefix from the owner's TASK-109 checklist step. 4 new tests
(exempt runserver, exempt check_mailbox, migrate still blocked, bare invocation still blocked);
guard file 14/14; full suite re-run by the coordinator before merge. TASK-100's container/CI
reasoning is untouched — no .env ships there, so the guard never fired for them anyway.
