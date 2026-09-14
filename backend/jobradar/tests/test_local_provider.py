"""TASK-221: local providers bypass Codex and enforce structured output natively.

No provider is launched here; every HTTP call is stubbed.
"""
import base64
import json
import os
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from jobradar.services import cv_generator
from jobradar.services.cv_generator import (RecoverableGenerationError, available_model_options,
                                            validate_model_capability)


class FakeResponse:
    status = 200
    reason = 'OK'

    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload


class FakeConnection:
    sock = None

    def __init__(self, host, port, response):
        self.host = host
        self.port = port
        self.response = response
        self.request_data = None

    def request(self, method, path, body, headers):
        self.request_data = SimpleNamespace(
            method=method, full_url=f'http://{self.host}:{self.port}{path}', data=body, headers=headers)

    def getresponse(self):
        return self.response

    def close(self):
        pass


@pytest.fixture(autouse=True)
def clear_model_cache():
    cv_generator._model_options_cache.update(at=0.0, options=None)
    yield
    cv_generator._model_options_cache.update(at=0.0, options=None)


OLLAMA_LISTING = '''NAME                       ID              SIZE      MODIFIED
dolphin-mixtral:latest     4f76c28c0414    26 GB     2 months ago
gemma3:4b                  a2af6cc3eb7f    3.3 GB    5 months ago
qwen3-coder:latest         06c1097efce0    18 GB     7 months ago
gpt-oss:20b                17052f91a42e    13 GB     9 months ago
nomic-embed-text:latest    0a109f422b47    274 MB    10 months ago
'''


def test_ollama_only_marks_the_real_cv_verified_model_cv_capable():
    def fake_run(command, **kwargs):
        stdout=OLLAMA_LISTING if command[-1] == 'list' else '  Capabilities\n    completion\n' + ('    tools\n' if command[-1] in ('qwen3-coder:latest','gpt-oss:20b') else '')
        return type('R', (), {'returncode':0,'stdout':stdout,'stderr':''})()
    with patch('jobradar.services.cv_generator.codex_model_options', return_value=[]), \
         patch('jobradar.services.cv_generator.claude_model_options', return_value=[]), \
         patch('jobradar.services.cv_generator.shutil.which', side_effect=lambda name: '/usr/bin/ollama' if 'ollama' in name else None), \
         patch('jobradar.services.cv_generator.subprocess.run', side_effect=fake_run) as run:
        options=[option for option in available_model_options() if option['provider'] == 'ollama']
    assert [(option['key'],option['tools']) for option in options] == [
        ('dolphin-mixtral:latest',False),('gemma3:4b',False),('qwen3-coder:latest',True),('gpt-oss:20b',True)]
    assert [option['cv'] for option in options] == [False,False,True,False]
    assert options[1]['label'] == 'gemma3:4b (evaluation only)'
    assert options[3]['label'] == 'gpt-oss:20b (evaluation only)'
    assert run.call_count == 5


def test_failed_ollama_list_does_not_offer_models():
    completed=type('R', (), {'returncode':1,'stdout':OLLAMA_LISTING,'stderr':'not running'})()
    with patch('jobradar.services.cv_generator.codex_model_options', return_value=[]), \
         patch('jobradar.services.cv_generator.claude_model_options', return_value=[]), \
         patch('jobradar.services.cv_generator.shutil.which', side_effect=lambda name: '/usr/bin/ollama' if 'ollama' in name else None), \
         patch('jobradar.services.cv_generator.subprocess.run', return_value=completed):
        assert available_model_options() == []


def _run_with_http_response(tmp_path, body, provider='lmstudio', **kwargs):
    response={'choices':[{'message':{'content':body}}]} if provider == 'lmstudio' else {'message':{'content':body}}
    connection=FakeConnection('localhost', 1234 if provider == 'lmstudio' else 11434, FakeResponse(response))
    with patch('jobradar.services.cv_generator.http.client.HTTPConnection', return_value=connection), \
         patch('jobradar.services.cv_generator._run_command') as codex:
        result=cv_generator.run_structured_model('prompt', kwargs.pop('schema', {'type':'object'}),
                                                 provider, 'deepseek', workdir=tmp_path, **kwargs)
    return result,connection.request_data,codex.call_count


def test_ollama_uses_native_schema_current_tex_context_and_documented_images_without_codex(tmp_path):
    schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
    tex=tmp_path/'candidate.tex'
    tex.write_text('CURRENT TEX', encoding='utf-8')
    image=tmp_path/'correction.png'
    image.write_bytes(b'correction image bytes')
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('OLLAMA_HOST', None)
        os.environ.pop('OLLAMA_NUM_CTX', None)
        result,request,codex_calls=_run_with_http_response(
            tmp_path, '{"answer":"ok"}', provider='ollama', schema=schema, tex_files=[tex], image_path=image)
    payload=json.loads(request.data)
    assert request.full_url == 'http://localhost:11434/api/chat'
    assert payload['format'] == schema and payload['stream'] is False
    assert payload['options'] == {'num_ctx':32768}
    assert 'CURRENT TEX' in payload['messages'][0]['content']
    assert payload['messages'][0]['images'] == [base64.b64encode(image.read_bytes()).decode()]
    assert 'response_format' not in payload
    assert result == {'answer':'ok'} and codex_calls == 0


@pytest.mark.parametrize('host', ['https://remote.example', 'http://192.0.2.10:11434', 'https://localhost:11434'])
def test_ollama_rejects_any_non_http_loopback_host_before_sending_private_prompt(tmp_path, monkeypatch, host):
    monkeypatch.setenv('OLLAMA_HOST', host)
    with patch('jobradar.services.cv_generator.http.client.HTTPConnection') as connection, pytest.raises(ValueError) as exc:
        cv_generator.run_structured_model('PRIVATE CANDIDATE EVIDENCE', {'type':'object'}, 'ollama', 'qwen', workdir=tmp_path)
    assert 'HTTP loopback' in str(exc.value)
    connection.assert_not_called()


def test_local_http_ignores_environment_proxies(tmp_path, monkeypatch):
    monkeypatch.setenv('HTTP_PROXY', 'http://remote.example:8080')
    result,request,_=_run_with_http_response(tmp_path, '{"answer":"ok"}', provider='ollama')
    assert request.full_url == 'http://localhost:11434/api/chat'
    assert result == {'answer':'ok'}


def test_ollama_rereads_current_tex_for_each_repair_attempt(tmp_path):
    tex=tmp_path/'candidate.tex'
    tex.write_text('ORIGINAL TEX', encoding='utf-8')
    _,first,_=_run_with_http_response(tmp_path, '{"answer":"first"}', provider='ollama', tex_files=[tex])
    tex.write_text('FAILING TEX FROM ATTEMPT ONE', encoding='utf-8')
    _,repair,_=_run_with_http_response(tmp_path, '{"answer":"fixed"}', provider='ollama', tex_files=[tex])
    first_prompt=json.loads(first.data)['messages'][0]['content']
    repair_prompt=json.loads(repair.data)['messages'][0]['content']
    assert 'ORIGINAL TEX' in first_prompt
    assert 'FAILING TEX FROM ATTEMPT ONE' in repair_prompt and 'ORIGINAL TEX' not in repair_prompt


def test_invalid_initial_output_keeps_full_context_then_compile_failure_uses_compact_repair(db, tmp_path, monkeypatch, settings, cv_assets):
    from django.contrib.auth.models import User
    from jobradar.models import JobLead

    settings.CODEX_CV_WORKSPACE=str(tmp_path)
    settings.CODEX_CV_CACHE=False
    settings.CODEX_CV_OPEN_OUTPUT_FOLDER=False
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda command: command)
    monkeypatch.setattr(cv_generator, 'available_model_options', lambda: [
        {'provider':'ollama','key':'qwen3-coder:latest','label':'qwen3-coder:latest','efforts':['default'],'default_effort':'default','fast_tier':''},
    ])
    user=User.objects.create_user('repair-owner')
    cv_assets(user, cv_source='\\documentclass{article}\\begin{document}ORIGINAL TEX\\end{document}')
    job=JobLead.objects.create(company='Firma', title='Engineer', raw_description='We need an engineer with Python experience.', created_by=user)
    large_facts='UNIQUE LARGE CANDIDATE FACTS ' * 2000
    failed_tex='\\documentclass{article}\\begin{document}CURRENT FAILED TEX\\end{document}'
    fixed_tex='\\documentclass{article}\\begin{document}FIXED TEX\\end{document}'
    confirmations={key:True for key in ('cv_max_2_pages','letter_max_1_page','no_orphaned_employer_headings','no_text_overlap','nothing_after_end_document','links_work','photo_loads_if_used','no_invented_tools_or_overclaims')}
    prompts=[]

    class RepairConnection:
        sock = None
        def __init__(self, host, port): pass
        def request(self, method, path, body, headers):
            prompts.append(json.loads(body)['messages'][0]['content'])
        def getresponse(self):
            tex=['INVALID TEX', failed_tex, fixed_tex][len(prompts)-1]
            generated={'cv_tex':tex,'changed_files':['cv.tex'],'main_changes':['Tailored'],
                       'unsupported_requirements_not_claimed':[],'confirmations':confirmations}
            return FakeResponse({'message':{'content':json.dumps(generated)}})
        def close(self): pass

    compile_calls=[]
    def fake_run(command, **kwargs):
        if command[0] == 'pdfinfo':
            return type('R', (), {'returncode':0,'stdout':'Pages: 1\n','stderr':''})()
        compile_calls.append(command)
        output=kwargs['cwd']
        target=output / command[-1]
        if len(compile_calls) == 1:
            target.with_suffix('.log').write_text('Undefined control sequence on line 42', encoding='utf-8')
            return type('R', (), {'returncode':1,'stdout':'compile failed','stderr':''})()
        target.with_suffix('.pdf').write_bytes(b'pdf')
        return type('R', (), {'returncode':0,'stdout':'ok','stderr':''})()

    monkeypatch.setattr(cv_generator.http.client, 'HTTPConnection', RepairConnection)
    monkeypatch.setattr(cv_generator.subprocess, 'run', fake_run)
    cv_generator.generate_cv_package(job, large_facts, 'en', '', False, 'ollama', 'qwen3-coder:latest', 'default', user_id=user.id)

    assert len(prompts) == 3
    assert large_facts in prompts[0] and large_facts in prompts[1]
    assert 'The selected model returned invalid application documents.' in prompts[1]
    assert large_facts not in prompts[2] and 'CANDIDATE FACTS AND RULES:' not in prompts[2]
    assert 'LaTeX could not compile the CV.' in prompts[2]
    assert 'Undefined control sequence on line 42' in prompts[2] and failed_tex in prompts[2]


def test_ollama_http_failures_keep_the_provider_diagnostic(tmp_path):
    response=FakeResponse({'error':'model requires more memory'})
    response.status=500
    response.reason='Internal Server Error'
    connection=FakeConnection('localhost', 11434, response)
    with patch('jobradar.services.cv_generator.http.client.HTTPConnection', return_value=connection), \
         pytest.raises(RecoverableGenerationError) as exc:
        cv_generator.run_structured_model('prompt', {'type':'object'}, 'ollama', 'qwen', workdir=tmp_path)
    assert 'model requires more memory' in exc.value.diagnostics


def test_lmstudio_uses_direct_strict_schema_http_and_preserves_the_correction_image(tmp_path):
    schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
    image=tmp_path/'correction.png'
    image.write_bytes(b'correction image bytes')
    result,request,codex_calls=_run_with_http_response(tmp_path, '```json\n{"answer":"ok"}\n```',
                                                       schema=schema, image_path=image)
    payload=json.loads(request.data)
    assert request.full_url == 'http://localhost:1234/v1/chat/completions'
    assert payload['response_format'] == {'type':'json_schema','json_schema':{'name':'structured_response','strict':True,'schema':schema}}
    assert payload['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert result == {'answer':'ok'} and codex_calls == 0


def test_lmstudio_rereads_current_tex_for_each_repair_attempt(tmp_path):
    tex=tmp_path/'candidate.tex'
    tex.write_text('ORIGINAL TEX', encoding='utf-8')
    _,first,_=_run_with_http_response(tmp_path, '{"answer":"first"}', tex_files=[tex])
    tex.write_text('FAILING TEX FROM ATTEMPT ONE', encoding='utf-8')
    _,repair,_=_run_with_http_response(tmp_path, '{"answer":"fixed"}', tex_files=[tex])
    first_prompt=json.loads(first.data)['messages'][0]['content']
    repair_prompt=json.loads(repair.data)['messages'][0]['content']
    assert 'ORIGINAL TEX' in first_prompt
    assert 'FAILING TEX FROM ATTEMPT ONE' in repair_prompt and 'ORIGINAL TEX' not in repair_prompt


def test_an_answer_with_no_json_at_all_is_still_a_recoverable_error(tmp_path):
    with pytest.raises(RecoverableGenerationError):
        _run_with_http_response(tmp_path, 'I cannot help with that.')


# `lms ls --llm --json` reports trainedForToolUse false for the measured local model. AC4 no longer
# makes that a CV-generation blocker because current TeX is sent inline rather than read via Codex.
LMS_LISTING = json.dumps([
    {'modelKey': 'deepseek-r1-distill-qwen-7b', 'displayName': 'DeepSeek R1 Distill Qwen 7B', 'trainedForToolUse': False},
    {'modelKey': 'qwen3-coder-tool-capable', 'displayName': 'Qwen3 Coder', 'trainedForToolUse': True},
])


def _with_lmstudio_models():
    completed = type('R', (), {'returncode': 0, 'stdout': LMS_LISTING, 'stderr': ''})()
    return patch('jobradar.services.cv_generator.shutil.which', side_effect=lambda name: '/usr/bin/lms' if 'lms' in name else None), \
        patch('jobradar.services.cv_generator.subprocess.run', return_value=completed)


@pytest.mark.parametrize('phase', ['headers','body'])
def test_cancellation_closes_an_in_flight_socket_and_stops_its_worker(tmp_path, phase):
    blocked=Event()
    stopped=Event()

    class BlockingResponse:
        status = 200
        reason = 'OK'
        def read(self):
            blocked.set()
            stopped.wait(2)
            raise OSError('closed')
        def close(self): stopped.set()

    class BlockingConnection:
        def __init__(self, host, port): self.sock=self
        def request(self, method, path, body, headers): pass
        def getresponse(self):
            if phase == 'headers':
                blocked.set()
                stopped.wait(2)
                raise OSError('closed')
            return BlockingResponse()
        def shutdown(self, how): stopped.set()
        def close(self): pass

    with patch('jobradar.services.cv_generator.http.client.HTTPConnection', BlockingConnection), \
         pytest.raises(cv_generator.GenerationCancelled):
        cv_generator.run_structured_model('prompt', {'type':'object'}, 'lmstudio', 'deepseek',
                                          workdir=tmp_path, cancelled=blocked.is_set)
    assert stopped.is_set()


def test_lmstudio_http_failures_keep_the_provider_diagnostic(tmp_path):
    class FailingConnection(FakeConnection):
        def request(self, method, path, body, headers):
            raise OSError('connection refused')
    connection=FailingConnection('localhost', 1234, None)
    with patch('jobradar.services.cv_generator.http.client.HTTPConnection', return_value=connection), \
         pytest.raises(RecoverableGenerationError) as exc:
        cv_generator.run_structured_model('prompt', {'type':'object'}, 'lmstudio', 'deepseek', workdir=tmp_path)
    assert 'connection refused' in exc.value.diagnostics


def test_cv_generation_refuses_models_labelled_evaluation_only_before_calling_them():
    which, run = _with_lmstudio_models()
    with which, run, pytest.raises(ValueError, match='job evaluation only'):
        validate_model_capability('lmstudio', 'deepseek-r1-distill-qwen-7b', 'default', 'normal', needs_tools=True)


def test_the_same_model_is_still_allowed_for_evaluation():
    """The discriminator, not a blanket ban: evaluation needs no tools and measurably works."""
    which, run = _with_lmstudio_models()
    with which, run:
        assert validate_model_capability('lmstudio', 'deepseek-r1-distill-qwen-7b', 'default', 'normal')['key'] == 'deepseek-r1-distill-qwen-7b'


def test_a_model_option_with_no_capability_reported_is_treated_as_capable():
    """Cloud providers report nothing here; absent metadata must not lock the owner out of Claude."""
    with patch('jobradar.services.cv_generator.available_model_options',
               return_value=[{'provider': 'anthropic', 'key': 'sonnet', 'label': 'Claude Sonnet', 'efforts': ['default'], 'default_effort': 'default', 'fast_tier': ''}]):
        assert validate_model_capability('anthropic', 'sonnet', 'default', 'normal', needs_tools=True)['key'] == 'sonnet'
