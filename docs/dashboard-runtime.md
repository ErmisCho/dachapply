# Local dashboard runtime (TEMP-83)

The existing localhost dashboard controls `manage.py dashboard_runtime`, rather than the
update/reset launcher. The companion dashboard patch is delivered separately because the
existing Caddy files have no dedicated repository. Install both changes together after review.

The application keeps its existing Django authentication and configured LAN access. The control
channel always binds loopback, requires a random per-launch bearer token, checks Host, and refuses
browser Origins. The dashboard adapter keeps that token on the server; it never sends it to a browser.
Only the fixed Dachapply application and lifecycle actions are accepted.

Start is serialized across threads/controllers and adopts only a matching authenticated launch
nonce. Windows virtualenv launcher PIDs can differ from the serving Python PID. Occupied ports
alone never prove ownership and never authorize termination. An unmanaged instance stays unmanaged.
Neither the controller nor the supervisor invokes a shell, fetches, installs dependencies, resets a
checkout, freezes an OS process, or kills a process.

Pause stops admission and lets already admitted safe units finish. Status says `pausing` until those
units finish, then `paused`; the app and control/log channels remain usable. Resume admits pending
units. Stop sets `stopping`, drains admitted units and existing HTTP requests, then shuts down its own
WSGI server. New mutating HTTP requests are refused while draining. A subsequent Start restores work
paused; Resume is explicit. There is no forced timeout that discards an active unit.

Document generation/compile/literal tasks, requirements analysis, pipelines, daily document work,
daily scheduling, and mailbox entrypoints use the same gate. Pending descriptors are stored before
worker launch in the local control SQLite database. Document sidecars remain the durable automatic
document queue; restored task IDs/callbacks prevent a second sidecar admission. Manual mailbox work
uses the existing database-backed MailboxCheckRequest and result link. Standalone CLI processes must
inherit `DACHAPPLY_CONTROL_DB` to join the same gate; cloud/manual processes without it retain their
existing behavior.

On an abrupt crash, previously running work is marked interrupted and requires review/retry; it is
never blindly replayed after potentially committing an external side effect. Queued work survives.
Cancellation is written to the durable document unit before HTTP acknowledges it. A recovered
cancel request restores its Event and cancelling status; Resume finalizes cancellation without
entering a compiler/model handler. Cancelled units are counted separately from completed/failed work.
Do not downgrade a control database with pending cancellation flags to a revision that ignores
them. Finalize pending cancellations with the fixed runtime before rollback, or defer the downgrade.
The UI reports real running/remaining counts and retained completed/failed/interrupted history. An
open queue has no total, percentage or ETA. Terminal history is bounded to 500 records; terminal
payloads are removed. Pending document descriptors can contain private candidate text and image
data: keep the state directory private, never publish it or place it under the web root.

Logs are bounded structured execution events, including failures, not raw stdout/tracebacks.
The runtime retains two files of at most 256 KB each. The browser gets at most the last 300 safe
events from 200 KB; enumerated event/kind fields are validated again. Candidate/mail text,
credentials, URLs, cookies, connection strings, arbitrary messages and tracebacks are excluded by
construction. Use the authenticated app's existing task details for task-specific diagnostics.

The supervisor starts document recovery and the mailbox/daily pipeline loop. It does not start the
unrelated demo-seeding/follow-up scheduler. It is a local threaded WSGI runner, not a production
internet-facing server. Disable the old force-relaunch watchdog before transitioning an existing
runtime; the companion replacement honors intentional Stop and has no unsafe fallback.

Verification uses the companion `verify_runtime.py`, disposable SQLite/workspaces, real Django and
pdflatex, and headless Chrome. Mail credentials/outbound loops are disabled. The sole runtime test
adapter suppresses clipboard writes; it does not mock the compiler or supervisor. A missing-job
document checks failure reporting; real compilation checks saved output and draining. Live Gmail,
paid model generation, production database access, installation and deployment are not exercised.
`test_processing_cancellation_lifecycle.py` also drives real authenticated HTTP cancellation across
graceful Stop/Start/Resume and verifies that no cancelled PDF is produced or counted completed.
