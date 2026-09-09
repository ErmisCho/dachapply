"""TASK-221: the free local provider path.

Two defects, both measured on the owner's machine before being fixed here:

1. codex-cli 0.146.0 asks ollama for its models over the OpenAI-compatible /v1/models route and then
   decodes the reply with the native /api/tags schema. Ollama 0.32.9 answers with a `data` array, so
   codex reports `missing field models` and ABORTS the run. Every ollama model in the picker was a
   guaranteed failure arriving after a long wait.
2. A local model honours `--output-schema` loosely: deepseek-r1-distill-qwen-7b through lmstudio
   returns valid JSON wrapped in a ```json fence, which the bare json.loads rejected.

No provider is launched here -- the probe is a stubbed HTTP call and the runner reads a file.
"""
import json
from unittest.mock import patch

import pytest

from jobradar.services import cv_generator
from jobradar.services.cv_generator import RecoverableGenerationError, _codex_can_enumerate_ollama, available_model_options


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def clear_model_cache():
    cv_generator._model_options_cache.update(at=0.0, options=None)
    yield
    cv_generator._model_options_cache.update(at=0.0, options=None)


# The exact body ollama 0.32.9 returns on /v1/models, and the one codex expects instead.
OPENAI_SHAPE = {'object': 'list', 'data': [{'id': 'gemma3:4b', 'object': 'model'}]}
NATIVE_SHAPE = {'models': [{'name': 'gemma3:4b'}]}


def test_probe_is_false_for_the_openai_shaped_list_codex_cannot_decode():
    with patch('urllib.request.urlopen', return_value=FakeResponse(OPENAI_SHAPE)):
        assert _codex_can_enumerate_ollama() is False


def test_probe_is_true_once_the_response_carries_the_field_codex_wants():
    """Not hard-coded to 'ollama is broken' -- the models come back on their own when a build agrees."""
    with patch('urllib.request.urlopen', return_value=FakeResponse(NATIVE_SHAPE)):
        assert _codex_can_enumerate_ollama() is True


def test_probe_is_false_when_ollama_is_not_answering_at_all():
    with patch('urllib.request.urlopen', side_effect=OSError('connection refused')):
        assert _codex_can_enumerate_ollama() is False


def test_ollama_models_are_not_offered_while_codex_cannot_reach_them():
    """The point: an unusable model must not cost the owner a long wait before failing."""
    with patch('jobradar.services.cv_generator._codex_can_enumerate_ollama', return_value=False):
        assert [option for option in available_model_options() if option['provider'] == 'ollama'] == []


def test_ollama_models_come_back_when_the_probe_says_codex_can_read_them():
    """The guard is a live probe, not a permanent verdict on ollama."""
    listing = 'NAME\tID\tSIZE\ngemma3:4b\tabc\t3.3 GB\n'
    completed = type('R', (), {'returncode': 0, 'stdout': listing, 'stderr': ''})()
    with patch('jobradar.services.cv_generator._codex_can_enumerate_ollama', return_value=True), \
         patch('jobradar.services.cv_generator.shutil.which', side_effect=lambda name: '/usr/bin/ollama' if 'ollama' in name else None), \
         patch('jobradar.services.cv_generator.subprocess.run', return_value=completed):
        keys = [option['key'] for option in available_model_options() if option['provider'] == 'ollama']
    assert keys == ['gemma3:4b']


def _run_with_result_file(tmp_path, body):
    """The runner unlinks the result file before running, so the stand-in writes it as the run."""
    def fake_run(command, cancelled=None, **kwargs):
        (tmp_path / 'model-result.json').write_text(body, encoding='utf-8')
        return type('R', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()

    with patch('jobradar.services.cv_generator.shutil.which', return_value='/usr/bin/codex'), \
         patch('jobradar.services.cv_generator._run_command', side_effect=fake_run):
        return cv_generator.run_structured_model('prompt', {'type': 'object'}, 'lmstudio', 'deepseek', workdir=tmp_path)


def test_a_fenced_json_answer_from_a_local_model_is_accepted(tmp_path):
    """Measured against deepseek-r1-distill-qwen-7b, which returns exactly this."""
    assert _run_with_result_file(tmp_path, '\n\n```json\n{"answer": "ok"}\n```\n') == {'answer': 'ok'}


def test_a_plain_json_answer_still_works(tmp_path):
    assert _run_with_result_file(tmp_path, '{"answer": "ok"}') == {'answer': 'ok'}


def test_an_answer_with_no_json_at_all_is_still_a_recoverable_error(tmp_path):
    """Tolerating fences must not turn 'the model refused' into a silent success."""
    with pytest.raises(RecoverableGenerationError):
        _run_with_result_file(tmp_path, 'I cannot help with that.')
