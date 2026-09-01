# TASK-210 browser login retry timeout

## Failure

The post-cache-table login retry timed out.

## Root cause

The verifier printed the two form values before submitting and both were empty. The failed 500 response had cleared the controlled login fields, but the retry script clicked Login without re-entering credentials.

## Resolution

Refill the inspected login fields and submit once. This is a browser-driver lifecycle mistake, not an application defect.
