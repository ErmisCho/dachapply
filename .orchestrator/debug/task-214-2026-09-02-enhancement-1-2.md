# TASK-214 compile-task regression failure

## Failure

The broader CV selection failed `test_cv_task_completes_and_is_user_scoped`:

`AssertionError: assert ('failed' == 'ready')`

The compile worker had converted the task to failed; the test's existing `recompile_generated_package` sentinel accepts the established arguments through `user_id` but not the newly added `source_updates` keyword.

## Root cause

`_run_compile` passed `source_updates={}` unconditionally, changing the call contract even for ordinary recompiles that do not use the new exact-edit route.

## Resolution

Preserved the old call shape for normal recompiles and pass `source_updates` only when the exact-edit plan is non-empty. The failed test passed on retry, followed by 28/28 broader CV/evidence tests and 1,053/1,053 full backend tests.
