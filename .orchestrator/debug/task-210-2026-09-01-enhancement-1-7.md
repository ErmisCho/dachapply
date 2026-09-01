# TASK-210 browser login second wait timeout

## Failure

Login with refilled synthetic credentials still did not reach the dashboard within 15 seconds.

## Root cause

The visible error was `Invalid credentials` and the backend returned 400. Normal registration sets both username and email to the entered email address, while the synthetic fixture had `username='task210'` and `email='task210@example.test'`. Login authenticates the submitted identity as Django's username, so entering the fixture's email could not match.

## Resolution

Use the fixture's actual username (`task210`) for this disposable login. This is fixture shape drift, not an application defect.
