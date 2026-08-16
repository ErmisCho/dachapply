---
id: TASK-71
title: Enforce password validation and make auth rate limits real
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 12:40'
labels:
  - security
  - backend
dependencies: []
priority: high
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Three related gaps in the auth hardening, all verified 2026-08-16:

1. `AUTH_PASSWORD_VALIDATORS` is configured (backend/config/settings.py:122) but `validate_password` is never called anywhere in backend (grep: zero matches). Register, change-password, and reset-confirm hand-roll `len(password) < 6` (backend/jobradar/views.py:104, 128, 243), so "123456" currently guards a user's entire job-search history.
2. `password_reset_confirm` is AllowAny with no throttle_classes (views.py:233-235) — the only unthrottled anonymous credential endpoint; login/register/reset-request/public-submit all have IP throttles (views.py:85, 99, 174, 442).
3. No CACHES setting exists, so SimpleRateThrottle counters live in per-process LocMemCache while Gunicorn runs `--workers 2` (scripts/start-container.sh:8): every configured limit is effectively doubled and resets on each revision swap.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Register, change-password, and password-reset-confirm run the configured Django password validators and surface their messages — "123456" is rejected on all three paths
- [x] #2 password_reset_confirm has an IP throttle following the existing IPThrottle pattern
- [x] #3 Throttle counters use a cache shared across workers (e.g. DatabaseCache + createcachetable) so a limit of N per IP holds at N, not N × workers, and survives a deploy
- [x] #4 Backend tests cover #1 (weak password rejected on each endpoint) and #2 (throttle kicks in)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
#1 is one `validate_password()` call per endpoint plus error mapping. #3: DatabaseCache is the lazy correct shared store — no Redis to operate; add `createcachetable` to the container start script next to migrate (scripts/start-container.sh).

### Closing notes (2026-08-16)

A single `password_rejection()` chokepoint calls `validate_password`, and all three endpoints go
through it, so a future fourth password endpoint cannot quietly skip the validators the way these
three did. The error shape stays `{'detail': '<joined messages>'}` because `api/client.ts` throws
the parsed body and the UI renders `e.detail` — a DRF-style `{'password': [...]}` would have
rendered as nothing, which is how a "fixed" validator can still look broken to a user.
`UserAttributeSimilarityValidator` is live too: the helper receives the user (an unsaved
`User(username=email, email=email)` on register, the real user elsewhere).

AC1 re-verified by the coordinator against a running server over real HTTP, not only in tests —
`"123456"` on each endpoint:

    POST /api/auth/register/              -> 400 {"detail":"This password is too short. It must
                                                  contain at least 8 characters. This password is
                                                  too common. This password is entirely numeric."}
    POST /api/auth/change-password/       -> 400 (same message)
    POST /api/auth/password-reset/confirm/-> 400 (same message)

AC2 re-verified by driving the previously unthrottled endpoint 22 times in a row against the
DEBUG limit of 20/hour:

    400 400 400 400 400 400 400 400 400 400 400 400 400 400 400 400 400 400 400 429 429 429

It is a separate scope (`password_reset_confirm_ip`) from `password_reset_ip` on purpose: burning
the request budget must not lock a user out of *completing* a reset they already asked for.
Production limit is 5/hour via `RATE_LIMIT_PASSWORD_RESET_CONFIRM_IP`.

AC3 is the part that could only be settled by measurement, and it was — twice, in both directions.
The implementing agent ran the same one-request-per-process experiment against the old LocMemCache
and the new DatabaseCache with `RATE_LIMIT_LOGIN_IP=1/minute`:

    old LocMemCache:  pid A -> 400 , pid B -> 400     (1/minute allowed two requests: the bug)
    new DatabaseCache: pid A -> 400 , pid B -> 429     (second process correctly refused)

The coordinator then confirmed the durable half independently: after driving the running server,
a **separate** shell process read the counter rows straight out of the cache table —

    :1:throttle_register_ip_127.0.0.1
    :1:throttle_password_reset_confirm_ip_127.0.0.1

which is the same property that makes the counters survive a revision swap.

Table `dachapply_cache` (overridable via `CACHE_TABLE`), created by `manage.py createcachetable` in
`scripts/start-container.sh` — the container CMD and the only production entry point. No migration:
Django's `create_test_db` creates the table for tests automatically. `createcachetable` was checked
to be idempotent for real (second run prints "already exists", exit 0), and the start script's
`set -e` and `exec gunicorn` failure behaviour are untouched.

**Follow-through the implementing agent could not do from its territory, done at close:** without
the cache table, every throttled endpoint 500s with `OperationalError: no such table:
dachapply_cache`. Production is covered by the start script, but a human following the docs was
not — `manage.py createcachetable` has been added next to `migrate` in `README.md` (both the local
and the build-and-serve path) and in `docs/production-readiness.md`.

**Owner action, one time:** run `cd backend && DATABASE_URL= uv run manage.py createcachetable`
against the local dev sqlite DB after pulling this change, or local logins will 500.

Suite: **172 passed** (167 baseline + 5 new), run twice with an identical result — no throttle or
cache cross-test flakiness. Two pre-existing register-throttle tests used 7-character passwords and
were updated, because those passwords are now correctly rejected.
<!-- SECTION:NOTES:END -->
