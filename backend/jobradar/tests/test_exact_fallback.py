"""TASK-386/388: an exact OLD/NEW edit that breaks the build (compile error or page limit) falls back
once to full optimization in the same task, with the failure appended to the instructions."""
from jobradar.services.cv_generator import RecoverableGenerationError
from jobradar.tests.test_literal_edits import env, owner  # noqa: F401 -- fixtures

EXACT = 'OLD:\nSenior Backend Engineer\\\\[2pt]\n\nNEW:\nStaff Backend Engineer\\\\[2pt]\n'


def test_exact_edit_that_compiles_makes_no_fallback_call(env):
    task=env.revise(EXACT)
    assert task['status']=='ready' and env.generated==[]


def test_compile_failure_falls_back_once_with_the_error_in_the_instructions(env):
    env.compile_ok=False
    task=env.revise(EXACT)
    assert task['status']=='ready', task
    [instructions]=env.generated
    assert instructions.startswith(EXACT.strip()) and 'exact replacements above were applied' in instructions and 'Undefined control sequence' in instructions


def test_page_limit_failure_falls_back_once_with_the_error_in_the_instructions(env):
    env.pages=9
    task=env.revise(EXACT)
    assert task['status']=='ready', task
    [instructions]=env.generated
    assert instructions.startswith(EXACT.strip()) and 'exceeds' in instructions and 'page limit' in instructions


def test_failing_fallback_fails_the_task_without_a_second_fallback(env, monkeypatch):
    env.compile_ok=False
    def generate(*args, **kwargs):
        env.generated.append(kwargs.get('revision_instructions'))
        raise RecoverableGenerationError('the fallback broke too')
    monkeypatch.setattr('jobradar.services.cv_tasks.generate_cv_package',generate)
    task=env.revise(EXACT)
    assert task['status']=='failed' and 'the fallback broke too' in task['error']
    assert len(env.generated)==1
