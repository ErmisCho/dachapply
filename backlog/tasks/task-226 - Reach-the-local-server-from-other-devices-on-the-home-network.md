---
id: TASK-226
title: Reach the local server from other devices on the home network
status: In Progress
assignee: []
created_date: '2026-09-10 11:48'
updated_date: '2026-09-11 06:12'
labels:
  - backend
  - infrastructure
dependencies: []
priority: high
ordinal: 225000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-09-10: other devices on the home network should be able to open this server.

Today they cannot. scripts/dachapply-local-runtime.cmd line 49 starts the backend as `python manage.py runserver 127.0.0.1:8000`, which binds loopback only, so nothing outside the host machine can reach it at all. Two settings would block it even after the bind is widened: ALLOWED_HOSTS defaults to `localhost,127.0.0.1,testserver` (settings.py:192) and CSRF_TRUSTED_ORIGINS to the localhost/127.0.0.1 forms (settings.py:193), so a request to `http://<lan-ip>:8000/` would be refused by host validation and a login POST would fail CSRF even if it were not.

This has a real exposure to state rather than gloss over: the local runtime runs with DEBUG=True and, unlike the deployed container, it points at the PRODUCTION database. Widening the bind puts the owner real board, real mailbox data and real CV workspace on the local network behind nothing but the Django login. Whatever is decided, the task should say what is now reachable and what is protecting it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A second physical device on the same network loads the board at http://<host-lan-ip>:8000/ and completes a login - verified from that device, not from a second browser on the host, and not inferred from a successful bind
- [x] #2 The bind address is configurable rather than hard-coded, and loopback-only stays the default for anyone who does not opt in
- [ ] #3 ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS accept the host LAN address, evidenced by a login POST succeeding from the second device rather than by reading the settings
- [ ] #4 Any host firewall rule the change needs is written down as the exact command that creates it, and the whole setup still works after a reboot of the host
- [x] #5 The task records what became reachable on the network and what protects it, given the local runtime runs DEBUG=True against the production database
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `task-226-lan-access`. Sealed rubric at `.claude/.asian-dad/task-226-rubric.json` (gitignored,
written before implementation per TW-001).

## There were THREE obstacles, not the two this task was filed with

The third is the one that would have made a correct-looking fix still serve nothing. The launcher runs
`npm run dev`, so `frontend/dist` does not exist in the runtime worktree, so `config/urls.py` takes its
`elif settings.DEBUG and settings.FRONTEND_URL` branch and redirects `/` to `FRONTEND_URL` --
`http://localhost:5173`. **A phone following that redirect resolves `localhost` to itself.** Bind and
ALLOWED_HOSTS could both be perfect and the device would still get nothing.

## The shape of the fix

One flag, `DACHAPPLY_LAN_ACCESS`, moves all three together, because any two without the third is a
setup that looks right and serves nothing:

1. `scripts/dachapply-local-runtime.cmd` binds `0.0.0.0:8000` instead of `127.0.0.1:8000`;
2. the launcher also runs `npm run build`, so `frontend/dist` exists and Django serves the SPA itself
   at `:8000` -- **the redirect is removed rather than fixed**, and the login POST becomes
   same-origin, so no CORS entry and no relaxed CSRF check is needed anywhere;
3. this host own private IPv4 addresses join `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

`DACHAPPLY_LAN_HOSTS` overrides detection when it is wrong. Unset, every line is inert.

## Address detection -- the non-obvious part, measured

`ipconfig` reports **three** IPv4 addresses on this machine, and `socket.gethostbyname_ex` returns them
**virtual-adapter first**:

    [172.22.48.1, 172.21.208.1, 192.168.8.130]

`192.168.8.130` -- the only one a phone can use -- is **last**. So taking `[0]`, which is the obvious
implementation, would have produced a configuration that looks correct and refuses the phone. Every
private address is enumerated and trusted instead; they are all this same host.

## Verified independently by the coordinator (TW-003)

| claim | result |
|---|---|
| flag unset -> today behaviour | `ALLOWED_HOSTS ["localhost","127.0.0.1","testserver"]`, CSRF unchanged |
| flag=1, DEBUG=1 | all three private addresses + their `http://<addr>:8000` origins added |
| **flag=1, DEBUG=0 (production)** | **`LAN_ACCESS False`, `ALLOWED_HOSTS ["example.com"]`** -- a stray env var cannot widen the deployed container |
| `DACHAPPLY_LAN_HOSTS=*` | raises `ImproperlyConfigured` |
| `DACHAPPLY_LAN_HOSTS=8.8.8.8` (public) | raises `ImproperlyConfigured` |
| launcher bind, run in real `cmd.exe` | unset -> `127.0.0.1:8000`; `1/true/TRUE/yes/on` -> `0.0.0.0:8000`; `0/false/banana` -> `127.0.0.1:8000` |
| launcher vs Django truthiness | `env_bool` is `(1,true,yes,on)` case-insensitive; the `.cmd` uses the same four with `/i`. They cannot disagree |
| backend suite | **1147 passed** (baseline 1127 + 20 new) |

## A portability trap this introduced, caught and closed

Opting in means putting `DACHAPPLY_LAN_ACCESS=1` in the repo-root `.env` -- which `config.settings`
reads at import, including under pytest. Reproduced rather than predicted: with the flag set,
`test_settings.py::test_local_root_redirects_to_vite_when_frontend_build_is_missing` returns **503
instead of 302** and fails on that machine only, while CI ships no `.env` and stays green. That is the
same shape as the untracked-personal-file dependency CI caught once before.

Closed in `config/settings_test.py` by blanking the variable **before** the star-import, next to
`DATABASE_URL` which is blanked for the same reason. Setting `LAN_ACCESS = False` after the import was
tried first and is **not** sufficient -- the two lists are already widened by then. Green with the flag
both set and unset.

## AC1, AC3, AC4 -- NOT checked

- **AC1** needs a second physical device completing a login. Neither an agent nor this session can do
  it. Every measurement above is this host addressing itself with a `Host:` header, which is not the
  same thing and is not offered as one.
- **AC3** the settings resolve correctly and a CSRF-accepted login POST from a LAN origin is covered by
  test, but the AC asks for the POST to come **from the device**. Same blocker as AC1.
- **AC4** the exact `netsh` add and delete commands are in README.md and a test asserts them verbatim,
  but the rule was **not created** (needs elevation) and nothing was rebooted. The rule is persistent
  by nature and the flag lives in `.env`, so both halves should survive; that is reasoning, not a
  measurement.

### To close them (owner, ~2 minutes)

1. Elevated `cmd`: run the `netsh ... add rule` line from README.md.
2. Put `DACHAPPLY_LAN_ACCESS=1` in the repo-root `.env` and restart the local runtime.
3. On a phone on the same Wi-Fi, open `http://192.168.8.130:8000/` and log in.

## AC5 -- what is now reachable, and what protects it

With the flag on, anything on the home LAN can reach the board on `:8000`. The local runtime runs
`DEBUG=True` **against the PRODUCTION database**, so that is the real board, the real mailbox data and
the real CV workspace. What protects it: the Django login, and nothing else. Hence opt-in rather than
default, hence `profile=private remoteip=localsubnet` on the firewall rule so it is scoped to the local
subnet and never public Wi-Fi, and hence the flag is gated on `DEBUG` so it can never widen the
deployed container. Recorded in README.md and in the `settings.py` comment as well as here.
<!-- SECTION:NOTES:END -->
