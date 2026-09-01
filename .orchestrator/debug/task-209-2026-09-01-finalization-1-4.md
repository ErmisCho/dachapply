# TASK-209 deployed browser readiness case mismatch

## Symptom

The deployed demo-login verifier reached `/` but exited after polling `innerText.includes('Feedback deadlines')` for 60 seconds.

## Root cause

The heading has CSS uppercase transformation, and Chromium's `innerText` reflected it as `FEEDBACK DEADLINES`; the case-sensitive mixed-case predicate could never pass. DOM inspection showed the released panel and `Hide upcoming` button were already present.

## Resolution

The final deployed verifier located the heading by its source `textContent`, then passed the full interaction and HTTPS reload: 5 rows shown, 1 overdue retained when upcoming was hidden, stored false survived reload, and 5 rows returned after restore.
