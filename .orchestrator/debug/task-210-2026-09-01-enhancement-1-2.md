# TASK-210 focused frontend test failure

## Failure

`feedbackDueControls.test.tsx` expected rendered conversation HTML to contain the literal text `Reply in Gmail`.

## Root cause

The reused conversation renders compact icon controls. Its exact-Gmail control is labelled `Open this message in Gmail — <timestamp>` and its reply control is labelled `Reply to this message from <sender>`. The product rendered both requested controls correctly; the new assertion guessed a visible label from a different UI path instead of asserting the existing component's accessible contract.

## Resolution

Change only the synthetic test assertion to the existing `Open this message in Gmail` accessible label. No product change is warranted.
