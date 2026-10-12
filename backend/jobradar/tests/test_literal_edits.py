"""TASK-278: free-form literal readjustments -- deterministic parser, local-model translator, and the
reliability gate in front of both. Every refusal must leave the files untouched and run the normal
full optimization instead."""
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from jobradar.models import JobLead, UserProfile
from jobradar.services import cv_generator, cv_tasks, literal_edits
from jobradar.services.cv_generator import GenerationCancelled
from jobradar.services.literal_edits import NotLiteral, gate_literal_edits

FIXTURE = Path(__file__).parent/'fixtures'/'literal_edits'/'fictional_cv.tex'


@pytest.fixture
def owner(db):
    user=User.objects.create_user('owner', email='owner@example.test', password='pw')
    UserProfile.objects.create(user=user, candidate_profile='OWNER_FIXTURE_PROFILE backend engineer')
    return user


@pytest.fixture
def env(owner, tmp_path, monkeypatch, settings):
    """Endpoint + task thread with the real recompile and page-limit code, but a fake pdflatex.

    `env.pages` is what pdfinfo would report, `env.compile_ok` whether pdflatex succeeds, and
    `env.generated` records every full-optimization run (the fallback)."""
    settings.CODEX_CV_ENABLED=True
    settings.CODEX_CV_OWNER_EMAIL='owner@example.test'
    cache.clear()
    cv_tasks._tasks.clear()
    job=JobLead.objects.create(company='ACME', title='Python Engineer', raw_description='Python Django SQL', created_by=owner)
    source=tmp_path/'Jane-CV.tex'
    source.write_bytes(FIXTURE.read_bytes())
    pdf=source.with_suffix('.pdf'); pdf.write_bytes(b'%PDF-original')
    state=SimpleNamespace()
    state.job,state.source,state.pdf,state.original=job,source,pdf,source.read_bytes()
    state.pages,state.compile_ok,state.generated,state.model_calls=1,True,[],[]
    monkeypatch.setattr('jobradar.views.latest_generated_sources',lambda job,user,letter_key='':(str(source),None))
    monkeypatch.setattr('jobradar.views.latest_generated_artifacts',lambda job,user,letter_key='':{'cv_tex':str(source),'cv_pdf':str(pdf)})
    monkeypatch.setattr('jobradar.views.validate_model_capability',lambda *args,**kwargs:None)
    monkeypatch.setattr('jobradar.views.load_candidate_evidence',lambda *args:'profile')
    monkeypatch.setattr(cv_tasks.JobLead.objects,'get',lambda id: job)
    monkeypatch.setattr(cv_tasks,'_copy_to_clipboard',lambda text: True)
    monkeypatch.setattr(cv_tasks,'mark_ready_to_submit',lambda job_id: None)
    monkeypatch.setattr(cv_tasks,'_learn_application_preference',lambda *args: '')
    monkeypatch.setattr(cv_generator,'user_photo',lambda user: None)
    # The task thread cannot share the test transaction's sqlite connection; hand it the account.
    users=SimpleNamespace(objects=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(first=lambda: owner)))
    monkeypatch.setattr(cv_generator,'get_user_model',lambda: users)
    monkeypatch.setattr(cv_generator.shutil,'which',lambda name: name if name in ('pdflatex','pdfinfo') else None)

    def pdflatex(command, cancelled=None, cwd=None, **kwargs):
        name=command[-1]
        if state.compile_ok:
            (Path(cwd)/Path(name).with_suffix('.pdf')).write_bytes(b'%PDF-edited')
        return SimpleNamespace(returncode=0 if state.compile_ok else 1,stdout='',stderr='! Undefined control sequence.')
    monkeypatch.setattr(cv_generator,'_run_command',pdflatex)
    monkeypatch.setattr(cv_generator,'_pdf_pages',lambda pdf: state.pages)

    def generate(job, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, progress, source_cv=None, source_letter=None, revision_instructions='', create_cv=True, correction_image=None, **kwargs):
        state.generated.append(revision_instructions)
        return b'zip','application.zip',{'cv_tex':str(source),'report':{'changed_files':['Jane-CV.tex'],'main_changes':['Rewrote the CV.'],'unsupported_requirements_not_claimed':[]}}
    monkeypatch.setattr(cv_tasks,'generate_cv_package',generate)

    def no_model(*args,**kwargs):
        raise AssertionError('a model was called')
    monkeypatch.setattr(literal_edits,'run_structured_model',no_model)
    monkeypatch.setattr(cv_generator,'run_structured_model',no_model)

    client=APIClient(); client.force_authenticate(owner)

    def revise(instructions):
        response=client.post(f'/api/jobs/{job.id}/cv-generation/revise-latest/',{'instructions':instructions,'create_cv':True,'create_letter':False,'cv_template':'en','provider':'openai','model':'gpt','effort':'low'},format='json')
        assert response.status_code==202, response.data
        for _ in range(500):
            task=cv_tasks.get_cv_task(response.data['task_id'],owner.id)
            if task['status'] in ('ready','failed','cancelled'):
                return task
            time.sleep(.01)
        raise AssertionError(f'task did not finish: {task}')
    state.revise=revise

    def use_model(answer):
        """Enable the local-model route with a fake model answering `answer` (dict, or exception)."""
        settings.CODEX_CV_LITERAL_EDIT_MODEL='ollama:tiny-model'
        monkeypatch.setattr(literal_edits,'available_model_options',lambda: [{'provider':'ollama','key':'tiny-model'}])
        def run(prompt, schema, provider, model, *args, cancelled=None, **kwargs):
            state.model_calls.append((provider,model,prompt))
            if callable(answer):
                return answer(cancelled)
            if isinstance(answer,Exception):
                raise answer
            return answer
        monkeypatch.setattr(literal_edits,'run_structured_model',run)
    state.use_model=use_model
    return state


def _edited(env, *pairs):
    text=env.original.decode('utf-8')
    for old,new in pairs:
        assert text.count(old)==1
        text=text.replace(old,new)
    return text.encode('utf-8')


def _assert_fell_back(env, task):
    assert task['status']=='ready', task
    assert env.source.read_bytes()==env.original and env.pdf.read_bytes()==b'%PDF-original'
    assert len(env.generated)==1
    assert task['report']['main_changes'][0]=='Rewrote the CV.'
    assert task['report']['main_changes'][-1].startswith('Route: full optimization (')


@pytest.mark.parametrize('instructions,pairs',[
    ('replace "Hamburg" with "Berlin"',[('Hamburg','Berlin')]),
    ('Change “Senior Backend Engineer” to “Staff Backend Engineer”',[('Senior Backend Engineer','Staff Backend Engineer')]),
    ('Kubernetes -> Kubernetes (CKA)',[('Kubernetes, Redis','Kubernetes (CKA), Redis')]),
    ('Redis → Valkey',[('Redis','Valkey')]),
    ('REPLACE Docker WITH Podman.',[('Docker','Podman')]),
    ("replace 'R&D' with 'research'",[('R\\&D','research')]),
    ('- change "German (C1)" to "German (C2)"\n- replace "Greek (native)" with "Greek (C2)"\nKeep everything else unchanged.',[('German (C1)','German (C2)'),('Greek (native)','Greek (C2)')]),
    ('replace "Docker" with "Podman"; change "University of Bremen" to "University of Hamburg"',[('Docker','Podman'),('University of Bremen','University of Hamburg')]),
])
def test_deterministic_phrasings_apply_without_any_model(env, instructions, pairs):
    task=env.revise(instructions)

    assert task['status']=='ready' and env.generated==[], (task['error'],task['diagnostics'][-800:])
    # Byte identity: the whole file is the source with only the requested spans replaced.
    assert env.source.read_bytes()==_edited(env,*pairs) and env.pdf.read_bytes()==b'%PDF-edited'
    assert task['report']['main_changes'][-1]=='Route: deterministic (no AI).'
    assert len(task['report']['main_changes'])==len(pairs)+1 and ' -> ' in task['report']['main_changes'][0]


def test_local_model_edit_is_applied_and_named_in_the_report(env):
    env.use_model({'literal':True,'edits':[{'old':'+49 170 1234567','new':'+49 151 7654321'}]})

    task=env.revise('My phone number is now +49 151 7654321')

    assert env.generated==[] and env.source.read_bytes()==_edited(env,('+49 170 1234567','+49 151 7654321'))
    assert task['report']['main_changes']==['+49 170 1234567 -> +49 151 7654321','Route: local model (tiny-model).']
    assert '"edits"' in env.model_calls[0][2] and 'jane.example@example.com' in env.model_calls[0][2]


def test_duplicate_match_writes_nothing_and_falls_back(env):
    task=env.revise('replace "Python" with "Go"')   # Python occurs twice in the fixture
    _assert_fell_back(env,task)
    assert 'does not occur exactly once' in task['report']['main_changes'][-1]


def test_compile_failure_writes_nothing_and_falls_back(env):
    env.compile_ok=False
    task=env.revise('replace "Hamburg" with "Berlin"')
    _assert_fell_back(env,task)
    assert 'compile check' in task['report']['main_changes'][-1]


def test_page_overflow_writes_nothing_and_falls_back(env):
    env.pages=3
    task=env.revise('replace "Hamburg" with "Berlin"')
    _assert_fell_back(env,task)
    assert '2-page limit' in task['report']['main_changes'][-1]


def test_model_proposing_an_unrequested_word_is_refused(env):
    # The instruction gives the new title; the model also slips in "Principal".
    env.use_model({'literal':True,'edits':[{'old':'Senior Backend Engineer','new':'Principal Staff Backend Engineer'}]})
    task=env.revise('Use Staff Backend Engineer as my title instead of the current one.')
    _assert_fell_back(env,task)
    assert 'principal' in task['report']['main_changes'][-1]


def test_mixed_instruction_never_applies_the_literal_part_alone(env):
    instruction='replace "Hamburg" with "Berlin" and make the summary more concise'
    assert literal_edits.deterministic_edit_pairs(instruction) is None
    # Measured with gemma3:4b: the model claims literal=true and returns only the literal part.
    env.use_model({'literal':True,'edits':[{'old':'Hamburg','new':'Berlin'}]})
    task=env.revise(instruction)
    _assert_fell_back(env,task)
    assert 'more than these edits' in task['report']['main_changes'][-1]


def test_model_saying_not_literal_falls_back(env):
    env.use_model({'literal':False,'edits':[]})
    _assert_fell_back(env,env.revise('Make the summary more concise.'))


def test_model_error_falls_back(env):
    env.use_model(cv_generator.RecoverableGenerationError('The selected model could not complete the request.','connection refused'))
    _assert_fell_back(env,env.revise('swap Docker for Podman'))


def test_model_timeout_falls_back(env, settings):
    settings.CODEX_CV_LITERAL_EDIT_TIMEOUT=.2
    def hang(cancelled):
        while not cancelled():
            time.sleep(.01)
        raise GenerationCancelled
    env.use_model(hang)
    task=env.revise('swap Docker for Podman')
    _assert_fell_back(env,task)
    assert 'did not answer within 0.2s' in task['report']['main_changes'][-1]


def test_no_installed_model_goes_straight_to_full_optimization(env, monkeypatch, settings):
    settings.CODEX_CV_LITERAL_EDIT_MODEL='ollama:not-installed'
    monkeypatch.setattr(literal_edits,'available_model_options',lambda: [{'provider':'ollama','key':'other'}])
    started=[]
    monkeypatch.setattr('jobradar.views.start_cv_task',lambda *args,**kwargs: started.append(kwargs) or 'full-task')
    response=APIClient()
    response.force_authenticate(env.job.created_by)
    reply=response.post(f'/api/jobs/{env.job.id}/cv-generation/revise-latest/',{'instructions':'swap Docker for Podman','provider':'openai','model':'gpt','effort':'low'},format='json')
    assert reply.status_code==202 and reply.data['task_id']=='full-task' and started[0]['revision_instructions']=='swap Docker for Podman'


def test_gate_splices_only_the_matched_spans_and_checks_the_rest():
    source='a\r\nHamburg | +49 170\r\nR\\&D guild\r\n'
    updates,edits=gate_literal_edits({'cv.tex':source},'replace Hamburg with Berlin; replace "R&D" with "research"',[('Hamburg','Berlin'),('R&D','research')])
    assert updates=={'cv.tex':'a\r\nBerlin | +49 170\r\nresearch guild\r\n'} and edits==[('Hamburg','Berlin'),('R\\&D','research')]
    assert not literal_edits._outside_spans_identical(source,'a\r\nBerlin | +49 171\r\nresearch guild\r\n',[(3,10,'Berlin'),(21,25,'research')])
    with pytest.raises(NotLiteral,match='overlap'):
        gate_literal_edits({'cv.tex':'Senior Backend Engineer'},'replace "Senior Backend" with "Staff"; replace "Backend Engineer" with "Developer"',[('Senior Backend','Staff'),('Backend Engineer','Developer')])
    with pytest.raises(NotLiteral,match='exactly once'):   # already applied is not a match
        gate_literal_edits({'cv.tex':'Berlin'},'replace Hamburg with Berlin',[('Hamburg','Berlin')])


@pytest.mark.parametrize('instructions',[
    'change Summary to be shorter',
    'replace "a" with "b" and make it shorter',
    'replace a with b and make it shorter',
    'replace a with b with c',
    "replace 'a' with 'b' and 'c' with 'd'",
    'replace "a" with "b"\nalso tidy the layout',
    'the summary -> make it punchier',
    'Make the summary more concise.',
])
def test_parser_never_claims_mixed_or_ambiguous_wording(instructions):
    assert literal_edits.deterministic_edit_pairs(instructions) is None
