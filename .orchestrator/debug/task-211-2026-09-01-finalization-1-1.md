# TASK-211 released-runtime fake-boundary verifier failure

## Failure

The first released-runtime verification piped a multiline script into interactive `manage.py shell`. The REPL parsed adjacent function definitions without the blank-line terminator it requires and emitted:

- `SyntaxError: invalid syntax` at `def read_only(...)`
- repeated `IndentationError: unexpected indent`
- final `SyntaxError` before the result print

The command did not reach the API view, model boundary, database guard, or any write.

## Root cause

Django's interactive shell consumes stdin through `InteractiveConsole`, which compiles blocks incrementally and requires REPL blank-line terminators; a normal Python module passed as raw stdin is not a reliable execution format.

## Resolution

A temporary `.py` module invoked through `manage.py shell -c "exec(open(...).read())"` exercised released SHA `25876651f9624fde69a8ed105ea46cb91401e975`. The owner CV endpoint returned 202, the fake task boundary received 120,577 characters beginning with the authoritative-evidence label, and the effective source path existed in the source checkout. A database execute guard measured 0 writes; fake boundaries measured 0 model and 0 Gmail calls. No product change beyond TASK-211 was warranted.
