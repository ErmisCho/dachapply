# TASK-209 post-deployment verifier defects

## Symptoms

1. The first final browser command failed to parse with `SyntaxError: missing ) after argument list`.
2. The corrected command found the released toggle/persisted state but asserted 5 rows while the feedback request was still loading and measured 0.

## Root causes

1. A ternary around `await page.evaluate(...)` omitted its closing parenthesis in the one-line verifier; no browser action ran.
2. Readiness checked only for the panel heading, which renders before its independent feedback API request settles. This was an early observation, not missing released rows.

## Resolution

Replaced the malformed ternary with an explicit `if`, then polled the panel's own Loading state/row count. The released HTTPS dashboard settled at 5 rows with `Hide upcoming`, `aria-pressed=true`, and stored `true`, confirming the prior full 5→1→reload→5 deployed interaction after the closure deployment.
