# TASK-212 Salesforce artifact inspection argument failure

## Failure

A read-only shell inspection called `latest_generated_sources(j.id, user)` and failed with `AttributeError: 'int' object has no attribute 'title'`. It performed no write, model call, or external submission.

## Root cause

`latest_generated_sources` accepts the `JobLead` object, not its integer ID; the caller misread the helper signature.

## Resolution

Retry the same read-only metadata inspection with `latest_generated_sources(j, user)`. No product change was warranted.
