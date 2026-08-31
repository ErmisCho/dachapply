"""TASK-122 ACs 2, 3, 6, 7, 8: the multi-turn draft-revision conversation. Every test stubs the two
seams draft_chat.py exposes for exactly this purpose -- `_binary_for` (never touches the real PATH)
and `_run` (never spawns a real process) -- plus cv_generator.available_model_options where a test
needs a controlled machine-capability list. No test here invokes a real model or a real subprocess.
"""
import json
import subprocess

import pytest

from jobradar.services import cv_generator, draft_chat
from jobradar.services.draft_chat import ChatTurn, ChatTurnResult, run_chat_turn

CLAUDE_MODEL = {
    'provider': 'anthropic', 'key': 'sonnet', 'label': 'Claude Sonnet',
    'efforts': ['low', 'medium', 'high', 'xhigh', 'max'], 'default_effort': 'medium', 'fast_tier': 'fast',
}
OLLAMA_MODEL = {
    'provider': 'ollama', 'key': 'llama3.1:8b', 'label': 'llama3.1:8b',
    'efforts': ['default'], 'default_effort': 'default', 'fast_tier': '',
}
FAKE_MODELS = [CLAUDE_MODEL, OLLAMA_MODEL]


@pytest.fixture(autouse=True)
def _isolated_draft_chat_env(settings, monkeypatch):
    """Same isolation rationale as test_mailbox.py's _isolated_mailbox_env: a developer's own
    installed CLIs/configured guardrails must never leak into these tests.
    """
    settings.MAILBOX_SALARY_FLOOR_EUR = ''
    settings.MAILBOX_DO_NOT_DISCLOSE = []
    monkeypatch.delenv('LLM_TIMEOUT_SECONDS', raising=False)
    monkeypatch.setattr(cv_generator, 'available_model_options', lambda: FAKE_MODELS)


def _stdout_completed(command, payload_dict, returncode=0):
    stdout = json.dumps({'structured_output': payload_dict}) if payload_dict is not None else '{not json'
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr='')


def _fake_run_success(revised_text):
    def _run(command, **_kwargs):
        return _stdout_completed(command, {'revised_text': revised_text})
    return _run


def _refusing_run():
    def _run(*_args, **_kwargs):
        raise AssertionError('the model process must never be invoked once selection/validation already refused')
    return _run


# --- AC2: the transcript is re-fed, not just the latest message ----------------------------------

def test_build_chat_prompt_includes_the_original_draft_when_there_is_no_history_yet():
    prompt = draft_chat._build_chat_prompt('Dear X, thanks.', [], 'make it shorter')
    assert 'Dear X, thanks.' in prompt
    assert '(no earlier turns yet)' in prompt
    assert 'make it shorter' in prompt


def test_build_chat_prompt_includes_every_earlier_turn_so_a_later_instruction_can_reference_it():
    history = [ChatTurn(user_message='shorter', revised_text='Dear X, short version, meeting on Tuesday March 3.')]
    prompt = draft_chat._build_chat_prompt('Dear X, the long original.', history, 'actually keep the date I just added')
    assert 'shorter' in prompt
    assert 'Tuesday March 3' in prompt
    assert 'CURRENT DRAFT' in prompt
    # The current draft to revise from is the latest turn's output, not the original.
    assert prompt.index('Tuesday March 3') < prompt.rindex('CURRENT DRAFT')


def test_understand_prompt_names_the_exact_unsent_draft_and_keeps_answers_out_of_revision_state():
    history = [
        ChatTurn(user_message='make it warmer', revised_text='Dear X, warm current draft.'),
        ChatTurn(user_message='why is this stale?', revised_text='Because you replied later.', mode='understand'),
    ]

    explain = draft_chat._build_chat_prompt('Dear X, original.', history, 'What does this wording imply?', 'understand')
    revise = draft_chat._build_chat_prompt('Dear X, original.', history, 'make it shorter', 'revise')

    assert 'EXACT UNSENT DRAFT:\nDear X, warm current draft.' in explain
    assert 'QUESTION FROM THE CANDIDATE:\nWhat does this wording imply?' in explain
    assert 'do not rewrite it or claim it was sent' in explain
    assert 'CURRENT DRAFT (what you must revise from):\nDear X, warm current draft.' in revise
    assert 'CURRENT DRAFT (what you must revise from):\nBecause you replied later.' not in revise


def test_run_chat_turn_second_turn_prompt_carries_the_first_turns_revision(monkeypatch):
    """AC2's own verification example: "shorter" then "actually keep the date I just added" only
    makes sense if the first turn's added date is still visible to the second call.
    """
    captured = {}

    def _run(command, **kwargs):
        captured['prompt'] = kwargs.get('input', '')
        return _stdout_completed(command, {'revised_text': 'Dear X, shorter version, keeping Tuesday March 3.'})

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)

    history = [ChatTurn(user_message='shorter', revised_text='Dear X, shorter version, meeting on Tuesday March 3.')]
    result = run_chat_turn('Dear X, the long original with no date.', history, 'actually keep the date I just added', 'anthropic', 'sonnet', 'medium')

    assert result.reason == ''
    assert 'Tuesday March 3' in captured['prompt'], 'second turn must still see the first turn\'s added date'
    assert 'shorter' in captured['prompt'], 'second turn must still see the first turn\'s own instruction'


def test_understand_turn_returns_an_answer_without_treating_it_as_an_accept_ready_draft(settings, monkeypatch):
    settings.MAILBOX_SALARY_FLOOR_EUR = '50000'
    captured = {}

    def _run(command, **kwargs):
        captured['prompt'] = kwargs.get('input', '')
        return _stdout_completed(command, {'revised_text': 'The draft mentions 40000 EUR only as context.'})

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)

    result = run_chat_turn('Exact unsent draft.', [], 'Explain the salary wording', 'anthropic', 'sonnet', 'medium', mode='understand')

    assert result == ChatTurnResult('The draft mentions 40000 EUR only as context.', '')
    assert 'Exact unsent draft.' in captured['prompt']
    assert 'QUESTION FROM THE CANDIDATE' in captured['prompt']


def test_run_chat_turn_rejects_unknown_help_mode_before_invoking_a_provider(monkeypatch):
    monkeypatch.setattr(draft_chat, '_run', _refusing_run())
    result = run_chat_turn('Exact unsent draft.', [], 'send it', 'anthropic', 'sonnet', 'medium', mode='send')
    assert result == ChatTurnResult('', 'mode must be revise or understand')


# --- AC3: model choice is validated against what the machine can actually run --------------------

def test_run_chat_turn_refuses_a_model_not_offered_by_available_model_options(monkeypatch):
    monkeypatch.setattr(draft_chat, '_run', _refusing_run())
    result = run_chat_turn('Dear X.', [], 'shorter', 'openai', 'gpt-5.6-sol', 'medium')
    assert result.revised_text == ''
    assert 'available model' in result.reason.lower()


def test_run_chat_turn_refuses_an_effort_the_selected_model_does_not_support(monkeypatch):
    monkeypatch.setattr(draft_chat, '_run', _refusing_run())
    result = run_chat_turn('Dear X.', [], 'shorter', 'ollama', 'llama3.1:8b', 'high')
    assert result.revised_text == ''
    assert 'effort' in result.reason.lower()


def test_run_chat_turn_valid_selection_reaches_the_provider(monkeypatch):
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _fake_run_success('Dear X, revised.'))
    result = run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium')
    assert result == ChatTurnResult('Dear X, revised.', '')


# --- AC7: every provider failure branch leaves the draft alone and says what happened ------------

def test_run_chat_turn_refuses_when_the_provider_binary_is_missing(monkeypatch):
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: None)
    monkeypatch.setattr(draft_chat, '_run', _refusing_run())
    result = run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium')
    assert result.revised_text == ''
    assert 'claude' in result.reason and 'not installed' in result.reason


def test_run_chat_turn_refuses_on_provider_timeout(monkeypatch):
    def _run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get('timeout'))

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)
    result = run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium', timeout_seconds=12)
    assert result.revised_text == ''
    assert '12s' in result.reason


def test_run_chat_turn_refuses_on_non_zero_exit(monkeypatch):
    def _run(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1, stdout='', stderr='claude: unknown flag')

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)
    result = run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium')
    assert result.revised_text == ''
    assert 'unknown flag' in result.reason


def test_run_chat_turn_refuses_on_malformed_json(monkeypatch):
    def _run(command, **_kwargs):
        return subprocess.CompletedProcess(command, 0, stdout='not valid json{{{', stderr='')

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)
    result = run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium')
    assert result.revised_text == ''
    assert result.reason


def test_run_chat_turn_refuses_on_a_missing_revised_text_field(monkeypatch):
    def _run(command, **_kwargs):
        return _stdout_completed(command, {'something_else': 'oops'})

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)
    result = run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium')
    assert result.revised_text == ''
    assert 'empty or invalid' in result.reason


def test_run_chat_turn_refuses_when_the_process_itself_raises(monkeypatch):
    """Broad enough to also catch what a vanished-mid-flight binary looks like in practice
    (FileNotFoundError, an OSError subclass) -- not just the pre-flight _binary_for check.
    """
    def _run(*_args, **_kwargs):
        raise FileNotFoundError('claude executable disappeared')

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)
    result = run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium')
    assert result.revised_text == ''
    assert result.reason


def test_run_chat_turn_codex_dispatch_for_a_non_anthropic_provider_uses_oss_local_provider(monkeypatch):
    """Provider dispatch coverage for the non-anthropic (codex --oss --local-provider) path."""
    captured = {}

    def _run(command, **kwargs):
        captured['command'] = command
        index = command.index('--output-last-message')
        from pathlib import Path
        Path(command[index + 1]).write_text(json.dumps({'revised_text': 'Dear X, revised via ollama.'}), encoding='utf-8')
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\codex.cmd')
    monkeypatch.setattr(draft_chat, '_run', _run)
    result = run_chat_turn('Dear X.', [], 'shorter', 'ollama', 'llama3.1:8b', 'default')
    assert result == ChatTurnResult('Dear X, revised via ollama.', '')
    assert '--oss' in captured['command'] and '--local-provider' in captured['command']
    assert 'ollama' in captured['command']


# --- AC8: an explicit timeout always reaches the subprocess call ---------------------------------

def test_run_chat_turn_passes_the_given_timeout_explicitly(monkeypatch):
    captured = {}

    def _run(command, **kwargs):
        captured['timeout'] = kwargs.get('timeout')
        return _stdout_completed(command, {'revised_text': 'Dear X, revised.'})

    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)
    run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium', timeout_seconds=7.5)
    assert captured['timeout'] == 7.5


def test_run_chat_turn_defaults_the_timeout_from_llm_timeout_seconds_env(monkeypatch):
    captured = {}

    def _run(command, **kwargs):
        captured['timeout'] = kwargs.get('timeout')
        return _stdout_completed(command, {'revised_text': 'Dear X, revised.'})

    monkeypatch.setenv('LLM_TIMEOUT_SECONDS', '33')
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _run)
    run_chat_turn('Dear X.', [], 'shorter', 'anthropic', 'sonnet', 'medium')
    assert captured['timeout'] == 33.0


# --- AC6: guardrails re-run on model-revised text before it can be reported accept-ready ----------

def test_run_chat_turn_blocks_a_revision_below_the_salary_floor(monkeypatch, settings):
    settings.MAILBOX_SALARY_FLOOR_EUR = 60000
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _fake_run_success('Sure, 40000 EUR works for me.'))
    result = run_chat_turn('Dear X.', [], 'accept their number', 'anthropic', 'sonnet', 'medium')
    assert result.revised_text == 'Sure, 40000 EUR works for me.', 'the produced text is still returned for display'
    assert 'below the configured floor' in result.reason


def test_run_chat_turn_blocks_a_revision_containing_a_do_not_disclose_phrase(monkeypatch, settings):
    settings.MAILBOX_DO_NOT_DISCLOSE = ['internal roadmap']
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _fake_run_success('Happy to share our internal roadmap for Q3.'))
    result = run_chat_turn('Dear X.', [], 'tell them about our plans', 'anthropic', 'sonnet', 'medium')
    assert 'internal roadmap' in result.reason


def test_run_chat_turn_allows_a_clean_revision_through_guardrails(settings, monkeypatch):
    settings.MAILBOX_SALARY_FLOOR_EUR = 60000
    settings.MAILBOX_DO_NOT_DISCLOSE = ['internal roadmap']
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'C:\\fake\\claude.exe')
    monkeypatch.setattr(draft_chat, '_run', _fake_run_success('Thank you, Tuesday works for me.'))
    result = run_chat_turn('Dear X.', [], 'confirm Tuesday', 'anthropic', 'sonnet', 'medium')
    assert result == ChatTurnResult('Thank you, Tuesday works for me.', '')
