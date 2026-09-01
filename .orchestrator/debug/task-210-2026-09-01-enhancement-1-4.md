# TASK-210 browser login driver failure

## Failure

The browser setup attempted to type into `input[type=email]` after selecting “I already have an account” and received `TypeError: Cannot read properties of null (reading 'click')`.

## Root cause

The driver assumed the account-creation form's email input would remain the login identity field. The login form uses a different input shape, so the selector no longer matched after the mode switch. This is a browser-driver assumption, not product behavior.

## Resolution

Inspect the visible login form after switching modes, then target its actual accessible labels/types. No application change is warranted.
