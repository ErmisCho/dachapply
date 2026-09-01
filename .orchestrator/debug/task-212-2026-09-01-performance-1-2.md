# TASK-212 focused-test environment setup failure

## Failure

`uv sync --frozen --extra dev` failed before tests with `Extra 'dev' is not defined in the project's optional-dependencies table`.

## Root cause

This repository puts the test dependencies in its normal frozen environment rather than a `dev` optional extra; the copied setup flag was invalid for this project.

## Resolution

Retry with the repository's existing `uv sync --frozen` contract, then run the unchanged focused pytest selection. No product change was warranted.
