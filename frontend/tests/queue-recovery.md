<!-- TASK-366 -->
Run from `frontend` with the project's Python environment and npm dependencies installed:

```sh
npx playwright install chromium
npm run test:recovery
npm run test:recovery
```

Windows uses installed Chrome, matching the existing board tests. Linux uses Playwright Chromium;
on a clean Linux runner provision its system libraries with `npx playwright install --with-deps chromium`.
The same npm command is intended for a future Linux CI gate. CI wiring is deferred until owner approval
after TASK-365; no workflow files are changed here. Host and CI repeatability still need a successful
pair of runs; do not infer that evidence from syntax checks.

The script owns ports 4396/8396 (both must be free), a temporary Vite configuration/cache,
a disposable SQLite database, synthetic user/templates/evidence and a CV workspace under the system
temp directory. It uses Django's test settings with a file database so request/worker threads share data.
The fixture is a standalone subprocess, never an application setting or public testing endpoint.
The normal frontend API proxy is untouched. Login, profile saves, queue actions, generation polling
and cancellation use real Django routes. Only model discovery/evaluation and document generation
are replaced at service boundaries. External backend connections and subprocesses are denied;
the browser blocks requests outside its local origin. No real providers or owner data are required.

The first analysis waits in model discovery until one-time cloud retry stops it. A synthetic provider
limit passes through the real error sanitizer and scheduler: reset plus one minute is accelerated
to twelve seconds. The second generation attempt blocks cooperatively until the panel cancels it.
Its complete generator inputs, excluding progress/cancellation callbacks, must match the first attempt.
Assertions cover profile persistence, elapsed discovery, the unchanged cloud-only preference,
sanitized limit text, the same task becoming running automatically, and cancellation reaching cancelled.
Changing those UI labels, disabling cloud retry, suppressing the scheduler or dropping the cancel
request causes a timeout/assertion failure rather than a successful smoke result.

Every exit closes the browser and stops owned servers, with a bounded force-stop fallback.
The backend releases its discovery gate, cancels tasks/timer and joins workers on graceful shutdown.
Successful runs remove their temporary directory. Failures retain `failure.txt` (exception plus bounded
server output) and `failure.png` when a page exists, and print the directory for collection as a CI artifact.
Missing dependencies can fail before a browser is available; their diagnostic contains the exception.
