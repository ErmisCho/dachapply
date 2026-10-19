"""TASK-322: a posting is checked for tasks, requirements, salary and company description -- by a keyword
rule after the fetch (posting_fetch.missing_parts), a headless re-read when a part is missing, and the
evaluation's own missing_parts once the job is analysed -- and a job still lacking a part holds its
documents in the Queue until the owner pastes the full posting or continues anyway.

Hermetic: the network and Playwright are test_posting_fetch's fakes, the model runner is patched, and
documents start through test_application_prep_queue's `tasks`, which runs nothing.
"""
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from jobradar.models import JobLead, UserProfile
from jobradar.services import application_prep, job_evaluator, json_importer, posting_fetch, prompt_builder
from jobradar.services.posting_fetch import missing_parts, posting_missing
from jobradar.tests.test_application_prep import _job, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import ACTION, _items, tasks  # noqa: F401 -- fixtures
from jobradar.tests.test_job_evaluator import OLLAMA_OPTION, evaluation_for
from jobradar.tests.test_posting_fetch import JOB_URL, PUBLIC_IP, _fake_playwright, net  # noqa: F401 -- fixtures

GERMAN = {
    'company': 'Über uns\nWir sind ein Wiener Softwarehaus mit 80 Mitarbeiter:innen und entwickeln Logistiksoftware für den DACH-Raum.',
    'tasks': 'Deine Aufgaben\n- Du entwickelst Django-Services und betreibst sie auf Kubernetes.\n- Du verantwortest das Postgres-Schema.',
    'requirements': 'Dein Profil\n- Mindestens drei Jahre Erfahrung mit Python.\n- Sehr gute Deutschkenntnisse.',
    'salary': 'Gehalt\nBruttojahresgehalt ab 52.000 € laut Kollektivvertrag IT, Überzahlung je nach Erfahrung.',
}
ENGLISH = {
    'company': 'About us\nWe build route planning software for 300 logistics companies across Europe.',
    'tasks': 'What you’ll do\nDesign and run Django services on Kubernetes.',
    'requirements': 'What you bring\nFive years of professional Python and solid Postgres skills.',
    'salary': 'Compensation\nThe annual salary range for this role is EUR 65,000 - 80,000.',
}
# Measured: the headless render of a Workday job link was the career-site search page, not the ad.
NVIDIA_SEARCH_PAGE = 'Skip to main content\nCAREERS AT NVIDIA\nSign In\nSearch for Jobs'
REASON = 'Posting incomplete: missing {}. Paste the full posting on the job page, or Continue anyway.'


def _ad(sections, without=()):
    return '\n\n'.join(['Backend Entwickler:in (m/w/d) – Wien', *(text for part, text in sections.items() if part not in without)])


def _html(text):
    return '<html><body>' + ''.join(f'<p>{line}</p>' for line in text.splitlines()) + '</body></html>'


# --- AC1: the keyword rule -----------------------------------------------------------------------

@pytest.mark.parametrize('spelling', [{}, {'Ü': 'Ue', 'ü': 'ue', 'ä': 'ae'}, {'Ü': 'U', 'ü': 'u', 'ä': 'a'}], ids=['umlaut', 'ascii', 'dropped'])
def test_task322_a_german_ad_has_every_part_however_its_umlauts_are_typed(spelling):
    text = _ad(GERMAN)
    for umlaut, plain in spelling.items():
        text = text.replace(umlaut, plain)
    assert missing_parts(text) == [] and missing_parts(_ad(ENGLISH)) == []


def test_task322_the_career_site_search_page_lacks_every_part():
    assert missing_parts(NVIDIA_SEARCH_PAGE) == ['tasks', 'requirements', 'salary', 'company']


@pytest.mark.parametrize('sections', [GERMAN, ENGLISH], ids=['de', 'en'])
@pytest.mark.parametrize('part', ['tasks', 'requirements', 'salary', 'company'])
def test_task322_each_missing_part_is_reported_alone(sections, part):
    assert missing_parts(_ad(sections, without=[part])) == [part]


# --- AC2: the headless re-read -------------------------------------------------------------------

def test_task322_an_incomplete_page_is_rendered_and_the_more_complete_text_kept(net, monkeypatch):
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, _html(_ad(GERMAN, without=['salary'])))
    calls = _fake_playwright(monkeypatch, html=_html(_ad(GERMAN)))
    result = posting_fetch.fetch_posting_text(JOB_URL)
    assert calls.goto == [JOB_URL] and result['ok'] and missing_parts(result['text']) == [] and 'Kollektivvertrag' in result['text']


@pytest.mark.parametrize('rendered', [_ad(GERMAN, without=['salary']) + '\nCookie settings', NVIDIA_SEARCH_PAGE], ids=['tie', 'search-page'])
def test_task322_a_render_no_more_complete_keeps_the_plain_text(net, monkeypatch, rendered):
    plain = _ad(GERMAN, without=['salary'])
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, _html(plain))
    calls = _fake_playwright(monkeypatch, html=_html(rendered))
    result = posting_fetch.fetch_posting_text(JOB_URL)
    assert calls.goto == [JOB_URL] and result['text'] == posting_fetch.extract_text(_html(plain))


def test_task322_a_complete_page_or_a_failed_fetch_is_never_rendered(net, monkeypatch):
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, _html(_ad(GERMAN)))
    calls = _fake_playwright(monkeypatch, html=_html(NVIDIA_SEARCH_PAGE))
    assert posting_fetch.fetch_posting_text(JOB_URL)['ok']
    net.fail(JOB_URL, HTTPError(JOB_URL, 403, 'Forbidden', {}, None))
    assert posting_fetch.fetch_posting_text(JOB_URL)['error'] == 'The site answered 403 Forbidden.'
    assert calls.launches == []


# --- AC3: the evaluation reports missing parts and overrides the keyword rule --------------------

def test_task322_schema_and_prompts_ask_for_missing_parts_and_the_importer_does_not_require_it(owner):
    item = job_evaluator.EVALUATION_SCHEMA['properties']['evaluations']['items']
    assert item['properties']['missing_parts']['items']['enum'] == ['tasks', 'requirements', 'salary', 'company']
    assert 'missing_parts' in item['required']  # strict structured output needs every property listed
    job = _job(owner, text=_ad(GERMAN))
    for template in (None, 'My own instructions.\n{schema}\n{jobs}'):  # the default and a saved custom template
        prompt = prompt_builder.build_prompt([job], '', 'profile', template)
        assert '"missing_parts":["list which of tasks|requirements|salary|company (company description) the posting text lacks' in prompt
    assert json_importer.validate_eval(evaluation_for(job), 0) == []
    assert json_importer.validate_eval(evaluation_for(job, missing_parts=['salary']), 0) == []


def test_task322_the_model_path_stores_missing_parts_and_it_wins_over_the_keywords(owner, client):
    UserProfile.objects.filter(user=owner).update(candidate_profile='EVAL_FIXTURE_PROFILE backend engineer')
    job = _job(owner, text=_ad(GERMAN))
    with patch('jobradar.services.job_evaluator.validate_model_capability', return_value=OLLAMA_OPTION), \
         patch('jobradar.services.job_evaluator.run_structured_model', return_value={'evaluations': [evaluation_for(job, missing_parts=['salary'])]}) as runner:
        response = client.post('/api/jobs/evaluate-with-model/', {'job_ids': [job.id], 'provider': 'ollama', 'model': 'llama3', 'commit': True}, format='json')
    assert response.status_code == 200 and response.data['ok'], response.content
    assert '"missing_parts"' in runner.call_args[0][0] and runner.call_args[0][1] is job_evaluator.EVALUATION_SCHEMA
    raw = job.evaluations.first().structured_json_raw
    assert raw['missing_parts'] == ['salary'] and raw['posting_chars'] == len(job.source_text)
    assert missing_parts(job.source_text) == [] and posting_missing(job) == ['salary']


def test_task322_posting_missing_falls_back_to_the_keywords_without_a_current_verdict(owner):
    job = _job(owner, text=_ad(GERMAN, without=['salary']))
    assert posting_missing(job) == ['salary']  # not analysed
    paste = {**evaluation_for(job), 'missing_parts': []}
    assert json_importer.import_evaluations({'evaluations': [paste]})['ok']
    assert posting_missing(job) == []  # the evaluation says the posting is complete
    JobLead.objects.filter(pk=job.pk).update(original_source_text=_ad(GERMAN, without=['salary', 'tasks']))
    job.refresh_from_db()
    assert posting_missing(job) == ['tasks', 'salary']  # it judged another text
    assert json_importer.import_evaluations({'evaluations': [evaluation_for(job)]})['ok']  # an old-style paste
    assert posting_missing(job) == ['tasks', 'salary']


# --- AC4/AC5: documents are held, Continue anyway, and a pasted posting -------------------------

def test_task322_an_incomplete_posting_holds_documents_until_continue(owner, client, tasks):
    job = _job(owner, 'to_apply', requirements=_req('de'), text=_ad(GERMAN, without=['requirements', 'company']))
    held = REASON.format('requirements, company description')
    assert application_prep.prepare(job.id, owner)['reason'] == held and tasks['started'] == []
    [item] = _items(client)
    assert (item['status'], item['key'], item['error'], item['incomplete']) == ('blocked', '', held, True)
    response = client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'continue'}, format='json')
    assert response.status_code == 200 and tasks['started'] == [(job.id, 'cv-de')]
    assert [(item['key'], item['incomplete']) for item in response.json()['items']] == [('cv-de', False)]
    # Remembered for the job: preparing it from scratch again is not held a second time.
    application_prep._save(job, owner.pk, lambda prep: prep.update(variants={}, reason=''))
    state = application_prep.prepare(job.id, owner)
    assert state['reason'] == '' and [variant['key'] for variant in state['variants']] == ['cv-de']
    assert application_prep._state(job, owner)['continue_incomplete'] is True


def test_task322_continue_is_refused_for_a_job_not_held_as_incomplete(owner, client, tasks):
    job = _job(owner, 'to_apply', requirements=_req('de'), text='https://jobs.example.test/role')
    application_prep.prepare(job.id, owner)
    assert _items(client)[0]['incomplete'] is False
    assert client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'continue'}, format='json').status_code == 400
    assert tasks['started'] == []


def test_task322_pasting_the_full_posting_clears_the_hold(owner, client, tasks, django_capture_on_commit_callbacks):
    job = _job(owner, 'to_apply', requirements=_req('de'), text=_ad(GERMAN, without=['salary']))
    application_prep.prepare(job.id, owner)
    assert _items(client)[0]['error'] == REASON.format('salary')
    with django_capture_on_commit_callbacks(execute=True):
        assert client.patch(f'/api/jobs/{job.id}/source-text/', {'original_source_text': _ad(GERMAN)}, format='json').status_code == 200
    assert tasks['started'] == [(job.id, 'cv-de')]


def test_task322_job_detail_and_board_rows_expose_posting_missing(owner, client):
    held = _job(owner, text=_ad(GERMAN, without=['salary']))
    judged = _job(owner, text=_ad(GERMAN))
    applied = _job(owner, 'applied', text=_ad(GERMAN, without=['salary']))
    assert json_importer.import_evaluations({'evaluations': [evaluation_for(judged, missing_parts=['tasks'])]})['ok']
    assert client.get(f'/api/jobs/{held.id}/').json()['posting_missing'] == ['salary']
    assert client.get(f'/api/jobs/{applied.id}/').json()['posting_missing'] == ['salary']

    def board():
        return {row['id']: row['posting_missing'] for row in client.get('/api/jobs/').json()}
    assert board() == {held.id: ['salary'], judged.id: ['tasks'], applied.id: []}  # an applied job is not flagged on the board
    assert client.patch(f'/api/jobs/{held.id}/source-text/', {'original_source_text': _ad(GERMAN)}, format='json').status_code == 200
    assert board()[held.id] == []  # the cached row follows the pasted text
