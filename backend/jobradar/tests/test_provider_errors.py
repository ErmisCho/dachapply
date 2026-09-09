"""TASK-222: what the owner is shown when a provider run fails.

The failure detail used to be `(stderr or stdout)[-6000:]`. Two real runs on the owner's machine
showed what that costs, and both are reproduced here as fakes:

1. ollama answered `ERROR: ... does not support tools` and the dialog showed a slab of the
   evaluation prompt's own "job matching rules" section instead.
2. CV generation through lmstudio / deepseek-r1-distill-qwen-7b failed with `Engine protocol predict
   request returned 400: request (40654 tokens) exceeds the available context size (32768 tokens)`,
   and Technical details showed the same rules section, cut mid-word -- because the model echoed the
   prompt back AFTER the error line, so the tail window held nothing else.

No provider is launched here: `_run_command` is a stand-in and no subprocess is started.
"""
from unittest.mock import patch

import pytest

from jobradar.services import cv_generator
from jobradar.services.cv_generator import RecoverableGenerationError


# A prompt of this project's real order of magnitude (~42k characters, seven times the detail
# budget), so an echo of it cannot fit in the window and the tail slice has to lose something.
RULES_PROMPT = 'JOB MATCHING RULES:\n' + '\n'.join(
    f'- Rule {n}: weigh ingestion and search reliability, evaluating retrieval quality honestly.' for n in range(500))
LMSTUDIO_CAUSE = ('Engine protocol predict request returned 400: request (40654 tokens) exceeds the '
                  'available context size (32768 tokens)')
OLLAMA_CAUSE = 'ERROR: gemma3:4b does not support tools'


def _failed_run(tmp_path, prompt, stdout='', stderr='', provider='lmstudio'):
    """A CLI that exits non-zero and writes no result file, which is what a failed run leaves behind."""
    def fake_run(command, cancelled=None, **kwargs):
        return type('R', (), {'returncode': 1, 'stdout': stdout, 'stderr': stderr})()

    with patch('jobradar.services.cv_generator.shutil.which', return_value='/usr/bin/codex'), \
         patch('jobradar.services.cv_generator._run_command', side_effect=fake_run), \
         pytest.raises(RecoverableGenerationError) as exc:
        cv_generator.run_structured_model(prompt, {'type': 'object'}, provider, 'deepseek', workdir=tmp_path)
    return exc.value.diagnostics


def test_the_cause_survives_an_echo_that_arrives_after_it(tmp_path):
    """Reproduction 2, the one the old tail slice could not survive: error first, then 42k of echo."""
    detail = _failed_run(tmp_path, RULES_PROMPT, stdout=f'Loading model...\n{LMSTUDIO_CAUSE}\n{RULES_PROMPT}')
    assert LMSTUDIO_CAUSE in detail


def test_the_echoed_prompt_is_not_shown_as_the_models_answer(tmp_path):
    """Reproduction 1: the cause is short and last, and the rules section is what filled the window."""
    detail = _failed_run(tmp_path, RULES_PROMPT, stdout=f'{RULES_PROMPT}\n{OLLAMA_CAUSE}')
    assert OLLAMA_CAUSE in detail
    assert 'Rule 499' not in detail and 'JOB MATCHING RULES' not in detail


def test_removed_echo_is_counted_where_the_owner_can_see_it(tmp_path):
    detail = _failed_run(tmp_path, RULES_PROMPT, stdout=f'Loading model...\n{LMSTUDIO_CAUSE}\n{RULES_PROMPT}')
    assert f'[{len(RULES_PROMPT.splitlines())} line(s) of echoed prompt removed]' in detail


def test_an_output_that_is_nothing_but_the_echo_says_so(tmp_path):
    """Removing all of it would leave an empty dialog, so it is kept and labelled for what it is."""
    detail = _failed_run(tmp_path, RULES_PROMPT, stdout=RULES_PROMPT)
    assert 'is the prompt echoed back, not the model' in detail
    assert 'character(s) omitted' in detail and len(detail) <= 6000


def test_output_over_the_budget_keeps_both_ends_and_counts_what_it_dropped(tmp_path):
    """A cause has no reason to sit at the end, so the head is no longer thrown away unannounced."""
    noise = '\n'.join(f'provider log line {n}: streaming tokens' for n in range(1000))
    detail = _failed_run(tmp_path, 'a short prompt', stdout=f'START: launching runtime\n{noise}\nFINAL: exit status 1')
    assert 'START: launching runtime' in detail and 'FINAL: exit status 1' in detail
    assert 'character(s) omitted' in detail and len(detail) <= 6000


def test_a_cause_on_the_other_stream_is_not_dropped(tmp_path):
    """`stderr or stdout` showed one stream only; a short stderr used to hide everything stdout said."""
    detail = _failed_run(tmp_path, RULES_PROMPT, stderr='exit status 1', stdout=f'{RULES_PROMPT}\n{OLLAMA_CAUSE}')
    assert OLLAMA_CAUSE in detail and 'exit status 1' in detail


def test_the_claude_path_is_treated_the_same_way(tmp_path):
    """The defect is not one provider's: whatever the CLI, the echo is recognised by what we sent it."""
    detail = _failed_run(tmp_path, RULES_PROMPT, stderr=f'{RULES_PROMPT}\nAPI Error: 400 context length exceeded',
                         provider='anthropic')
    assert 'API Error: 400 context length exceeded' in detail and 'Rule 499' not in detail


def test_a_repeated_cause_the_repair_prompt_quotes_is_reported_at_least_once(tmp_path):
    """The known limit of comparing against the prompt, pinned rather than left to be discovered.

    CV generation retries twice and quotes the previous failure into the next prompt, so on attempt 2
    the recurring cause IS a line of the prompt and is filtered with the echo around it. The owner
    still reads it, because the loop joins every attempt and attempt 1's block carries it -- but the
    attempt-2 block does not, and that is what this pins.
    """
    repair_prompt = f'{RULES_PROMPT}\n\nFAILURE TO FIX:\nThe selected model could not complete the request.\n{LMSTUDIO_CAUSE}'
    first = _failed_run(tmp_path, RULES_PROMPT, stdout=f'Loading model...\n{LMSTUDIO_CAUSE}\n{RULES_PROMPT}')
    second = _failed_run(tmp_path, repair_prompt, stdout=f'Loading model...\n{LMSTUDIO_CAUSE}\n{RULES_PROMPT}')
    assert LMSTUDIO_CAUSE in first
    assert LMSTUDIO_CAUSE not in second and 'echoed prompt removed' in second


def test_a_run_that_said_nothing_at_all_still_says_that(tmp_path):
    assert _failed_run(tmp_path, RULES_PROMPT) == 'No model output was returned.'


def test_a_successful_run_is_untouched(tmp_path):
    """Every model path in the project goes through this function; only the failure path changed."""
    def fake_run(command, cancelled=None, **kwargs):
        (tmp_path / 'model-result.json').write_text('{"answer": "ok"}', encoding='utf-8')
        return type('R', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()

    with patch('jobradar.services.cv_generator.shutil.which', return_value='/usr/bin/codex'), \
         patch('jobradar.services.cv_generator._run_command', side_effect=fake_run):
        assert cv_generator.run_structured_model(RULES_PROMPT, {'type': 'object'}, 'lmstudio', 'deepseek',
                                                 workdir=tmp_path) == {'answer': 'ok'}
