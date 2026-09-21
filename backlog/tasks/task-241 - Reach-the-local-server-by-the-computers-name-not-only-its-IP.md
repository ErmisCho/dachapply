---
id: TASK-241
title: 'Reach the local server by the computer''s name, not only its IP'
status: Done
assignee:
  - '@pi'
created_date: '2026-09-21 07:26'
updated_date: '2026-09-21 12:14'
labels:
  - backend
  - infrastructure
dependencies: []
priority: medium
type: enhancement
ordinal: 240000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-09-21, immediately after verifying TASK-226 from a phone: reaching http://192.168.8.130:8000/ works, and they want http://<computer name>:8000/ to work as well. An IP has to be looked up and changes with DHCP; the name does not.

Measured before filing. This host is 'Caren' (socket.gethostname()), FQDN 'Caren.lan'. config/settings.py lan_addresses() (line 226) enumerates private IPv4 literals ONLY -- every candidate is parsed with ipaddress.IPv4Address and anything that is not an IPv4 literal is dropped -- and lan_widened() (line 269) appends those addresses plus their http://<address>:8000 origins. So a request arriving with Host: Caren:8000 is not in ALLOWED_HOSTS and Django answers 400 DisallowedHost, and a login POST from that origin would fail CSRF even if it were.

Note the part no server change can fix: whether a phone resolves the name at all is client-side. Windows answers mDNS for <hostname>.local and NetBIOS/LLMNR for the bare name; iOS resolves .local, Android's support has historically been uneven. That is why AC1 asks for the check from the device rather than from the host, and why AC5 asks for the limitation to be written down rather than papered over.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With LAN access on, a second physical device loads the board and completes a login using the host's NAME rather than its IP address - verified from that device, not from the host and not inferred from settings
- [x] #2 The names trusted are derived from this host (its hostname, its FQDN, and the .local mDNS form phones actually use), never hardcoded, and DACHAPPLY_LAN_HOSTS still overrides detection outright
- [x] #3 With the flag unset the behaviour is byte-identical to today, and DEBUG=False is never widened by any of this
- [x] #4 A name that is not this host's is refused - no wildcard, no suffix match, no 'any .local'
- [x] #5 Which name forms work is written in the README, including what to do when a given phone cannot resolve .local, since that is a client-side limitation no server change can fix
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## AC1 closed 2026-09-21 from the owner's laptop

The owner confirmed the board opens by name from their laptop on the same network. Reported as
"now it works" in answer to a request that named both halves -- load the board AND complete a login
-- so both are taken as done. One structural reason to believe the login half specifically: a session
cookie set at http://192.168.8.130:8000 does not travel to http://caren:8000, different host, so the
board could not have rendered at the name without authenticating at that origin.

Recorded rather than glossed: the login was not reported as a separate observation. If it turns out
only the login PAGE was seen, AC1 reopens and the fix would be in CSRF_TRUSTED_ORIGINS, not in host
validation.

## Two rounds, and the first one failed for a reason worth keeping

Round 1: the branch was checked out in the runtime worktree, the host confirmed http://caren:8000/
-> 200, and the owner was asked to test. They got **400 DisallowedHost** on the laptop.

The 400 was correct, and from the OLD code. `scripts/dachapply-local-runtime.cmd` line 16 runs
`git reset --hard origin/main` on every launcher start, so the runtime worktree had been re-pinned to
main between the check and the test, taking this branch's settings.py with it. Branch code cannot be
tested on the runtime at all -- not 'is not visible by default', cannot, because the launcher
actively resets it.

Round 2: merged to main first (CI green), moved the runtime to merged main, then re-probed:

    http://caren:8000/          200
    http://caren.local:8000/    200
    http://192.168.8.130:8000/  200    (the IP path, unregressed)
    http://caren.local:8000/api/health/  {"status":"ok","database":"ok"}

Merging before the physical check was safe here specifically because the mechanism is gated on
DEBUG: with DACHAPPLY_LAN_ACCESS=1, DACHAPPLY_LAN_HOSTS set and DEBUG=0 the deployed lists stay
['dachapply.example']. Verified before merging, not after. Production redeployed on the merge and
/api/health/ still answers {"status":"ok","database":"ok"}.

## Coordinator's independent verification (TW-003)

Not taken from the implementing agent:

| check | result |
|---|---|
| flag unset | ALLOWED_HOSTS ['localhost','127.0.0.1','testserver'] -- identical to before |
| flag on | + caren, caren.lan, caren.local and their http://<name>:8000 origins |
| flag on + override + DEBUG=0 | ['dachapply.example'] -- production cannot be widened |
| accepted Host headers | caren, Caren, CAREN.LOCAL, caren.local, caren.local., caren.lan, 192.168.8.130 -> 200 |
| refused Host headers | notcaren.local, evil.caren.local, caren.local.attacker.example, phone.local, caren.evil, 192.168.8.99, 8.8.8.8 -> 400 |
| wildcard in ALLOWED_HOSTS | none |
| hostname literal in the diff | none -- names are derived at runtime |
| backend suite | 1222 passed (baseline 1203, +19) |

The agent's own finding, and the one that would have produced a feature that looks right and refuses
the login: ALLOWED_HOSTS matching is case-insensitive, but CSRF_TRUSTED_ORIGINS is an exact,
case-SENSITIVE membership test against the Origin header, which browsers send lowercased. Stored as
'Caren' the board would load and the login POST would fail.
<!-- SECTION:NOTES:END -->
