---
id: TASK-241
title: 'Reach the local server by the computer''s name, not only its IP'
status: To Do
assignee: []
created_date: '2026-09-21 07:26'
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
- [ ] #1 With LAN access on, a second physical device loads the board and completes a login using the host's NAME rather than its IP address - verified from that device, not from the host and not inferred from settings
- [ ] #2 The names trusted are derived from this host (its hostname, its FQDN, and the .local mDNS form phones actually use), never hardcoded, and DACHAPPLY_LAN_HOSTS still overrides detection outright
- [ ] #3 With the flag unset the behaviour is byte-identical to today, and DEBUG=False is never widened by any of this
- [ ] #4 A name that is not this host's is refused - no wildcard, no suffix match, no 'any .local'
- [ ] #5 Which name forms work is written in the README, including what to do when a given phone cannot resolve .local, since that is a client-side limitation no server change can fix
<!-- AC:END -->
