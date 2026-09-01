# TASK-210 browser login third wait timeout

## Failure

Submitting the fixture username still did not reach the dashboard.

## Root cause

The disposable user is active, `check_password` is true, and `authenticate(username='task210', ...)` succeeds against the same database. A request-level probe then showed both controlled input values were still empty immediately after Puppeteer's `ElementHandle.type`; the POST correctly returned `Invalid credentials` for those empty values. Keyboard typing into this minimized/background grouped tab did not mutate the controlled inputs.

## Resolution

Set each input through its native value setter and dispatch an `input` event before submitting, then verify the values before the request. This is a background-browser driver limitation, not an application defect.
