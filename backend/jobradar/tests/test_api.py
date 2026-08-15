import json
import re

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.db.models import Q
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from jobradar.models import InviteCode, JobLead, JobEvaluation, ApplicationNote, FollowUp, SiteDailyUsage, SiteVisitor, UserDailyUsage, UserProfile, VisitorDailyUsage

PNG_DATA_URL='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='


def throttled_rest_framework(**rates):
    rest_framework = dict(settings.REST_FRAMEWORK)
    rest_framework['DEFAULT_THROTTLE_RATES'] = {**rest_framework.get('DEFAULT_THROTTLE_RATES', {}), **rates}
    return override_settings(REST_FRAMEWORK=rest_framework)


def assert_rate_limited(response):
    assert response.status_code == 429
    assert response.data['detail'] == 'Rate limit exceeded. Try again later.'
    assert 'available_in_seconds' in response.data


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='pw')

@pytest.fixture
def client(db, owner):
    c=APIClient(); c.force_authenticate(owner); c.user=owner; return c

def make_job(client, **kwargs):
    kwargs.setdefault('created_by', client.user)
    return JobLead.objects.create(**kwargs)

@pytest.fixture
def job(db, owner): return JobLead.objects.create(company='ACME', title='Python Engineer', raw_description='Python Django SQL', created_by=owner)


def test_health_check_is_public_and_checks_database(db):
    r = APIClient().get('/api/health/')
    assert r.status_code == 200
    assert r.data == {'status': 'ok', 'database': 'ok'}


def test_demo_scheduler_database_claim_failure_logs_warning(db, monkeypatch, caplog):
    from django.db import DatabaseError
    from jobradar.services import demo_scheduler

    class BrokenQuery:
        def get_or_create(self, **_kwargs):
            raise DatabaseError('db down')

    class BrokenRuns:
        class objects:
            @staticmethod
            def select_for_update():
                return BrokenQuery()

    monkeypatch.setattr(demo_scheduler, 'ScheduledTaskRun', BrokenRuns)
    with caplog.at_level('WARNING', logger='jobradar.services.demo_scheduler'):
        assert demo_scheduler.seed_demo_if_due(force=True) == (False, None, [])
    assert 'Could not claim demo seed task: db down' in caplog.text


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', FRONTEND_URL='https://dachapply.example.test', DEFAULT_FROM_EMAIL='DACHApply <noreply@example.test>')
def test_password_reset_email_and_confirm_flow(db):
    user = User.objects.create_user('reset@example.test', email='reset@example.test', password='old-password')
    c = APIClient()
    r = c.post('/api/auth/password-reset/', {'email': 'reset@example.test'}, format='json')
    assert r.status_code == 200
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.subject == 'DACHApply password reset request'
    assert email.alternatives
    html_body, html_mimetype = email.alternatives[0]
    assert html_mimetype == 'text/html'
    assert 'Reset password</a>' in html_body
    assert 'If the button does not work, copy and paste this link into your browser:' in html_body
    body = email.body
    assert 'We received a request to reset the password for your DACHApply account.' in body
    assert 'If the button or link does not work, copy and paste the URL into your browser.' in body
    assert 'If you did not request this change, you can safely ignore this email.' in body
    assert 'https://dachapply.example.test/reset-password/' in body
    match = re.search(r'/reset-password/([^/]+)/([^\s]+)', body)
    assert match
    uid, token = match.groups()
    r = c.post('/api/auth/password-reset/confirm/', {'uid': uid, 'token': token, 'password': 'new-password'}, format='json')
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.check_password('new-password')


def test_password_reset_email_failure_keeps_generic_response(db, monkeypatch):
    User.objects.create_user('reset-fail@example.test', email='reset-fail@example.test', password='pw')
    def fail_send_mail(*args, **kwargs):
        raise RuntimeError('SMTP unavailable')
    monkeypatch.setattr('jobradar.views.send_mail', fail_send_mail)
    r = APIClient().post('/api/auth/password-reset/', {'email': 'reset-fail@example.test'}, format='json')
    assert r.status_code == 200
    assert r.data['detail'] == 'If an account exists for this email, a reset link was sent.'


def test_create_job(client):
    r=client.post('/api/jobs/', {'company':'X','title':'Backend','url':'https://x.test'}, format='json')
    assert r.status_code==201 and r.data['company']=='X'

@pytest.mark.parametrize('title,expected', [
    ('Backend Engineer m/f/d', 'Backend Engineer'),
    ('AI Engineer (w/m/d)', 'AI Engineer'),
    ('Senior Developer - F/M/D', 'Senior Developer'),
])
def test_create_job_strips_gender_marker_from_title(client, title, expected):
    r=client.post('/api/jobs/', {'company':'X','title':title,'url':f'https://x.test/{expected.lower().replace(" ","-")}'}, format='json')
    assert r.status_code==201 and r.data['title']==expected

def test_create_url_only_job(client):
    r=client.post('/api/jobs/', {'url':'https://x.test/job'}, format='json')
    assert r.status_code==201 and r.data['company']=='Unknown company' and r.data['title']=='Untitled role'

def test_manual_duplicate_job_requires_choice(client):
    make_job(client, company='A', title='T', url='https://manual.test/job')
    r=client.post('/api/jobs/', {'company':'B','title':'T2','url':'https://manual.test/job'}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts'

def test_manual_duplicate_job_detects_trailing_slash_and_query(client):
    make_job(client, company='A', title='T', url='https://manual.test/job')
    r=client.post('/api/jobs/', {'company':'B','title':'T2','url':'https://manual.test/job/?utm=x'}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts'

def test_manual_duplicate_job_can_duplicate(client):
    make_job(client, company='A', title='T', url='https://manual.test/job')
    r=client.post('/api/jobs/', {'company':'B','title':'T','url':'https://manual.test/job','duplicate_action':'duplicate'}, format='json')
    assert r.status_code==201 and r.data['title']=='T (1)'

def test_bulk_create_multiple_links_from_notes(client):
    r=client.post('/api/jobs/bulk-create/', {'raw_description':'https://a.test/job1\nhttps://b.test/job2'}, format='json')
    assert r.status_code==201 and r.data['count']==2 and JobLead.objects.filter(url__in=['https://a.test/job1','https://b.test/job2']).count()==2

@pytest.mark.parametrize('details', [
    {'company':'No URL Co'},
    {'title':'Unpublished role'},
    {'raw_description':'Listing shared as plain text'},
])
def test_bulk_create_job_without_url(client, details):
    r=client.post('/api/jobs/bulk-create/', details, format='json')
    assert r.status_code==201 and r.data['count']==1 and r.data['created'][0]['url']==''

def test_bulk_create_rejects_empty_job(client):
    r=client.post('/api/jobs/bulk-create/', {}, format='json')
    assert r.status_code==400 and JobLead.objects.count()==0

def test_bulk_create_does_not_treat_description_emails_as_links(client):
    description='Contacts:\nredacted@example.test\nermis.chorinopoulos@gmail.com\nredacted@example.test'
    r=client.post('/api/jobs/bulk-create/', {'company':'EBCONT (BMJ)','title':'ElasticSearch Consultant','raw_description':description}, format='json')
    assert r.status_code==201 and r.data['count']==1
    assert r.data['created'][0]['company']=='EBCONT (BMJ)' and r.data['created'][0]['url']==''

def test_bulk_create_keeps_distinct_job_query_ids(client):
    links='\n'.join([
        'https://jobboerse.strabag.at/job-detail.php?ReqId=571',
        'https://jobboerse.strabag.at/job-detail.php?ReqId=495',
        'https://jobboerse.strabag.at/job-detail.php?ReqId=754',
    ])
    response=client.post('/api/jobs/bulk-create/', {'url':links}, format='json')
    assert response.status_code==201 and response.data['count']==3
    assert set(JobLead.objects.values_list('url', flat=True))==set(links.splitlines())


def test_bulk_create_duplicate_requires_choice(client):
    make_job(client, company='A', title='T', url='https://a.test/job1')
    r=client.post('/api/jobs/bulk-create/', {'url':'https://a.test/job1\nhttps://b.test/job2'}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts' and JobLead.objects.filter(url='https://b.test/job2').count()==0

def test_bulk_create_per_conflict_skip_removes_from_conflicts(client):
    make_job(client, company='A', title='T', url='https://a.test/job1')
    make_job(client, company='B', title='T', url='https://b.test/job2')
    body={'url':'https://a.test/job1\nhttps://b.test/job2\nhttps://c.test/job3','duplicate_actions':[{'index':0,'action':'skip'}]}
    r=client.post('/api/jobs/bulk-create/', body, format='json')
    assert r.status_code==400 and [c['index'] for c in r.data['conflicts']]==[1]
    assert r.data['skipped'][0]['index']==0
    assert not JobLead.objects.filter(url='https://c.test/job3').exists()

def test_bulk_create_resolved_single_conflict_also_creates_new_links(client):
    a=make_job(client, company='A', title='T', url='https://a.test/job1')
    body={'company':'New','title':'New title','url':'https://a.test/job1\nhttps://c.test/job3','duplicate_actions':[{'index':0,'action':'override'}]}
    r=client.post('/api/jobs/bulk-create/', body, format='json')
    a.refresh_from_db()
    assert r.status_code==201
    assert a.company=='New'
    assert JobLead.objects.filter(url='https://c.test/job3').exists()

def test_bulk_create_override_with_link_only_clears_old_analysis_and_details(client):
    a=make_job(client, company='OldCo', title='Old title', url='https://a.test/job1', location='Vienna', raw_description='Old description', status='applied', status_date=timezone.localdate())
    JobEvaluation.objects.create(job=a, fit_score=90, priority='high', recommendation='apply')
    ApplicationNote.objects.create(job=a, note='old note')
    FollowUp.objects.create(job=a, follow_up_date=timezone.localdate(), reason='old follow-up')
    body={'url':'https://a.test/job1','duplicate_actions':[{'index':0,'action':'override'}]}
    r=client.post('/api/jobs/bulk-create/', body, format='json')
    a.refresh_from_db()
    assert r.status_code==201
    assert a.company=='Unknown company'
    assert a.title=='Untitled role'
    assert a.location=='' and a.raw_description==''
    assert a.status=='new' and a.status_date is None
    assert not a.evaluations.exists()
    assert not a.notes.exists()
    assert not a.followups.exists()

def test_bulk_create_per_conflict_duplicate_and_override(client):
    a=make_job(client, company='A', title='T', url='https://a.test/job1')
    make_job(client, company='B', title='T', url='https://b.test/job2')
    body={'company':'New','title':'New title','url':'https://a.test/job1\nhttps://b.test/job2','duplicate_actions':[{'index':0,'action':'override'},{'index':1,'action':'duplicate'}]}
    r=client.post('/api/jobs/bulk-create/', body, format='json')
    a.refresh_from_db()
    assert r.status_code==201
    assert a.company=='New'
    assert JobLead.objects.filter(url='https://b.test/job2').count()==2


def test_bulk_create_rejects_malformed_url_only_input(client):
    r=client.post('/api/jobs/bulk-create/', {'url':'not a job link'}, format='json')
    assert r.status_code==400
    assert JobLead.objects.count()==0


def test_bulk_create_ignores_malformed_text_and_normalizes_valid_links(client):
    r=client.post('/api/jobs/bulk-create/', {'url':'ignore this\nhttps-www.karriere.at-jobs-7794074\nhttps://example.com/job/?utm=x'}, format='json')
    assert r.status_code==201 and r.data['count']==2
    assert JobLead.objects.filter(url='https://www.karriere.at/jobs/7794074', status='new').exists()
    assert JobLead.objects.filter(url='https://example.com/job', status='new').exists()

def test_normalizes_pasted_hyphen_url(client):
    r=client.post('/api/jobs/', {'url':'https-www.karriere.at-jobs-7794074'}, format='json')
    assert r.status_code==201 and r.data['url']=='https://www.karriere.at/jobs/7794074'

def test_repairs_markdown_corrupted_url(client):
    r=client.post('/api/jobs/', {'url':'https://[https://www.karriere.at/jobs/7803497','company':'epunkt','title':'Senior Software Entwickler - Python/Odoo'}, format='json')
    assert r.status_code==201 and r.data['url']=='https://www.karriere.at/jobs/7803497'

def test_moves_url_accidentally_pasted_as_company(client):
    r=client.post('/api/jobs/', {'company':'https-www.karriere.at-jobs-7794074'}, format='json')
    assert r.status_code==201 and r.data['url']=='https://www.karriere.at/jobs/7794074' and r.data['company']=='Unknown company'

def test_public_submission_valid(db):
    InviteCode.objects.create(code='OK')
    c=APIClient(); r=c.post('/api/public/submit/', {'invite_code':'OK','company':'C','title':'T','url':'https://c.test'}, format='json')
    assert r.status_code==201

def test_public_submission_invalid(db):
    r=APIClient().post('/api/public/submit/', {'invite_code':'NO','company':'C','title':'T'}, format='json')
    assert r.status_code==400

def test_listing_jobs(client, job): assert client.get('/api/jobs/').status_code==200


def test_job_added_by_email_fields(client, owner):
    submitter=User.objects.create_user('anna', email='anna@example.test', password='pw')
    job=JobLead.objects.create(company='ACME', title='Python Engineer', created_by=submitter, submitted_for=owner)
    r=client.get(f'/api/jobs/{job.id}/')
    assert r.status_code==200
    assert r.data['created_by_username']=='anna'
    assert r.data['created_by_email']=='anna@example.test'


def test_jobs_analyzed_filter_hides_jobs_without_evaluation(client):
    analyzed = make_job(client, company='Analyzed', title='Ready')
    draft = make_job(client, company='Draft', title='Needs analysis')
    JobEvaluation.objects.create(job=analyzed, fit_score=80, priority='high', recommendation='apply')

    r = client.get('/api/jobs/?status=new&analyzed=1')
    assert r.status_code == 200
    assert analyzed.id in [row['id'] for row in r.data]
    assert draft.id not in [row['id'] for row in r.data]

    r = client.get('/api/jobs/?status=new')
    assert {analyzed.id, draft.id}.issubset({row['id'] for row in r.data})


def test_jobs_board_filter_hides_untitled_links_but_keeps_named_drafts(client):
    link_only = make_job(client, company='Unknown company', title='Untitled role 1', url='https://example.test/job')
    blank_title = make_job(client, company='Unknown company', title='', url='https://example.test/other')
    named = make_job(client, company='EBCONT (BMJ)', title='ElasticSearch Consultant')

    board_ids={row['id'] for row in client.get('/api/jobs/?status=new&board=1').data}
    assert named.id in board_ids and link_only.id not in board_ids and blank_title.id not in board_ids
    assert {link_only.id, blank_title.id}.issubset({row['id'] for row in client.get('/api/jobs/?status=new').data})


def test_update_job_status(client, job):
    r=client.patch(f'/api/jobs/{job.id}/', {'status':'to_apply'}, format='json')
    assert r.status_code==200 and r.data['status']=='to_apply'

def test_applied_status_sets_status_date(client, job):
    r=client.patch(f'/api/jobs/{job.id}/', {'status':'applied'}, format='json')
    assert r.status_code==200 and r.data['status_date'] is not None and r.data['last_update_date'] is not None


def test_rejected_status_clears_last_update_date(client, job):
    job.status='interview'; job.status_date=timezone.localdate(); job.last_update_date=timezone.localdate(); job.save()
    r=client.patch(f'/api/jobs/{job.id}/', {'status':'rejected','status_date':'2026-01-02'}, format='json')
    assert r.status_code==200 and r.data['status_date']=='2026-01-02' and r.data['last_update_date'] is None


def test_can_override_status_date(client, job):
    r=client.patch(f'/api/jobs/{job.id}/', {'status':'interview','status_date':'2026-01-02'}, format='json')
    assert r.status_code==200 and r.data['status_date']=='2026-01-02'

def test_generate_prompt(client, job):
    original='Original complete source ' + 'vollständig ' * 400
    JobLead.objects.filter(pk=job.pk).update(original_source_text=original, raw_description='Edited summary')
    r=client.post('/api/prompts/generate/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'CANDIDATE PROFILE' in r.data['generated_prompt']
    assert original in r.data['generated_prompt'] and 'Edited summary' not in r.data['generated_prompt']

def test_generate_enrichment_prompt(client, job):
    r=client.post('/api/prompts/enrich/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'job_updates' in r.data['generated_prompt']

def test_generate_combined_prompt(client, job):
    r=client.post('/api/prompts/combined/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'evaluation' in r.data['generated_prompt'] and 'job_id' in r.data['generated_prompt']
    assert 'No markdown, code fences, citations' in r.data['generated_prompt'] and 'parses as JSON' in r.data['generated_prompt']

def test_generate_bulk_links_prompt(client):
    r=client.post('/api/prompts/bulk-links/', {'links':'https-www.karriere.at-jobs-7794074\nhttps://example.com/job'}, format='json')
    assert r.status_code==200 and 'EXPECTED JSON SCHEMA' in r.data['generated_prompt'] and 'evaluation' in r.data['generated_prompt']


def test_candidate_evidence_is_required_and_loaded(tmp_path, settings):
    from jobradar.services.cv_generator import load_candidate_evidence
    settings.CODEX_CV_WORKSPACE=str(tmp_path)
    settings.CODEX_CANDIDATE_EVIDENCE_PATH=str(tmp_path/'missing.md')
    with pytest.raises(RuntimeError, match='cannot be read'):
        load_candidate_evidence('profile')
    evidence=tmp_path/'evidence.md'; evidence.write_text('verified evidence', encoding='utf-8')
    settings.CODEX_CANDIDATE_EVIDENCE_PATH=str(evidence)
    settings.CODEX_APPLICATION_RULES_PATH=str(tmp_path/'missing-rules.md')
    with pytest.raises(RuntimeError, match='adaptation rules.*cannot be read'):
        load_candidate_evidence('profile notes')
    rules=tmp_path/'rules.md'; rules.write_text('maximum two pages', encoding='utf-8')
    settings.CODEX_APPLICATION_RULES_PATH=str(rules)
    context=load_candidate_evidence('profile notes', '- [CV] Keep the profile concise')
    assert 'AUTHORITATIVE CANDIDATE EVIDENCE:\nverified evidence' in context
    assert 'MANDATORY APPLICATION ADAPTATION RULES:\nmaximum two pages' in context and 'profile notes' in context
    assert 'LEARNED ACCOUNT APPLICATION PREFERENCES' in context and '- [CV] Keep the profile concise' in context


def test_correction_image_validation(monkeypatch):
    from jobradar.services import cv_generator

    content,suffix=cv_generator.decode_correction_image(PNG_DATA_URL)
    assert suffix=='.png' and content.startswith(b'\x89PNG')
    with pytest.raises(ValueError, match='data URL'):
        cv_generator.decode_correction_image('data:image/gif;base64,R0lGODlh')
    with pytest.raises(ValueError, match='malformed'):
        cv_generator.decode_correction_image('data:image/png;base64,AAAA')
    monkeypatch.setattr(cv_generator, 'MAX_CORRECTION_IMAGE_BYTES', 10)
    with pytest.raises(ValueError, match='5 MB or smaller'):
        cv_generator.decode_correction_image(PNG_DATA_URL)


def test_generated_application_names_have_no_language_suffix(job):
    from jobradar.services.cv_generator import _target_names
    expected=('Chorinopoulos-Ermis-CV-Acme-Python-Engineer.tex','Chorinopoulos-Ermis-Letter-Acme-Python-Engineer.tex')
    assert _target_names(job, 'en', 'en')==expected
    assert _target_names(job, 'de', 'de')==expected
    job.title='Machine Learning Engineer (gn*)'
    assert _target_names(job, 'de', 'de')==('Chorinopoulos-Ermis-CV-Acme-Machine-Learning-Engineer.tex','Chorinopoulos-Ermis-Letter-Acme-Machine-Learning-Engineer.tex')
    job.company='TÜV AUSTRIA'
    assert _target_names(job, 'de', 'de')[0]=='Chorinopoulos-Ermis-CV-TUV-Austria-Machine-Learning-Engineer.tex'


def test_cv_generation_requires_original_job_text(db):
    from jobradar.services.cv_generator import generate_cv_package
    user=User.objects.create_user('no-source-owner')
    job=JobLead.objects.create(company='Link only', title='Role', raw_description='https://example.test/job', created_by=user)
    with pytest.raises(RuntimeError, match='Original job text'):
        generate_cv_package(job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium')


def test_candidate_evidence_uses_saved_compact_snapshot(tmp_path,settings):
    from jobradar.services.cv_generator import load_candidate_evidence
    full='''old chat\n# Candidate Evidence\n## Professional Summary\nKeep facts.\n## Measurable Achievements\nDrop verbose claims.\n## Interview Evidence\nDrop interview notes.\n## Needs Confirmation\nKeep caveats.\n# Candidate Evidence\nduplicate facts'''
    evidence=tmp_path/'evidence.md'; evidence.write_text(full)
    rules=tmp_path/'rules.md'; rules.write_text('Keep honest.')
    settings.CODEX_CV_WORKSPACE=str(tmp_path); settings.CODEX_CANDIDATE_EVIDENCE_PATH=str(evidence); settings.CODEX_APPLICATION_RULES_PATH=str(rules)
    context=load_candidate_evidence('Profile')
    snapshot=tmp_path/'.dachapply-cache'/'candidate-evidence-compact.md'
    assert snapshot.is_file() and len(snapshot.read_text()) < len(full)
    assert 'Keep facts.' in context and 'Keep caveats.' in context and 'Drop interview notes.' not in context and 'duplicate facts' not in context


def test_latest_generated_sources_survive_task_state_loss(job, tmp_path, settings):
    from jobradar.services.cv_generator import latest_generated_sources
    settings.CODEX_CV_WORKSPACE=str(tmp_path)
    cv_dir=tmp_path/'CVs'; letter_dir=tmp_path/'output'; cv_dir.mkdir(); letter_dir.mkdir()
    old=cv_dir/'Chorinopoulos-Ermis-CV-acme-python-engineer.tex'; old.write_text('old'); __import__('os').utime(old,(1,1))
    latest=cv_dir/'Chorinopoulos-Ermis-CV-acme-python-engineer-2.tex'; latest.write_text('latest')
    letter=letter_dir/'Chorinopoulos-Ermis-Letter-acme-python-engineer.tex'; letter.write_text('letter')
    sent=cv_dir/'sent'; sent.mkdir(); legacy=sent/'Chorinopoulos-Ermis-CV-acme-python-engineer-3.tex'; legacy.write_text('legacy latest')
    future=__import__('time').time()+10; __import__('os').utime(legacy,(future,future))
    assert latest_generated_sources(job, 'de')==(str(legacy),str(letter))


@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test', CODEX_CV_WORKSPACE='C:/missing')
def test_cv_generation_preview_is_owner_only(client, owner, job):
    assert client.get(f'/api/jobs/{job.id}/cv-generation/').status_code==404
    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    JobLead.objects.filter(pk=job.pk).update(original_source_text='Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben und die Bewerbung.', raw_description='English role and requirements')
    r=client.get(f'/api/jobs/{job.id}/cv-generation/')
    assert r.status_code==200 and r.data['language']=='de'
    assert r.data['selected_cv']=='de'
    assert {cv['key'] for cv in r.data['cvs']}=={'en','de'}
    assert {letter['key'] for letter in r.data['letters']}=={'motivation_letter','motivationsschreiben','bewerbungsschreiben','anschreiben'}
    assert any(model['key']=='gpt-5.6-sol' and {'max','ultra'} <= set(model['efforts']) for model in r.data['models'])


@override_settings(CODEX_CV_ENABLED=False, CODEX_CV_OWNER_EMAIL='owner@example.test')
def test_cv_generation_can_be_disabled(client, owner, job):
    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    assert client.get(f'/api/jobs/{job.id}/cv-generation/').status_code==404


@throttled_rest_framework(cv_generation_user='100/hour')
@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test')
def test_cv_generation_starts_asynchronously(client, owner, job, monkeypatch):
    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    UserProfile.objects.create(user=owner, learned_application_preferences='- [CV] Keep the profile concise')
    other=User.objects.create_user('other-preferences')
    UserProfile.objects.create(user=other, learned_application_preferences='OTHER_ACCOUNT_PREFERENCE')
    selected={}
    def start(job_id, user_id, profile, cv, letter, create_letter, provider, model, effort, speed, create_cv=True):
        selected.update(job_id=job_id,user_id=user_id,profile=profile,cv=cv,letter=letter,create_cv=create_cv,create_letter=create_letter,provider=provider,model=model,effort=effort,speed=speed)
        return 'task123'
    monkeypatch.setattr('jobradar.views.start_cv_task', start)
    payload={'cv_template':'de','letter_template':'anschreiben','provider':'openai','model':'gpt-5.5','effort':'high','speed':'fast'}
    r=client.post(f'/api/jobs/{job.id}/cv-generation/run/', payload, format='json')
    assert r.status_code==202 and r.data['task_id']=='task123' and r.data['status']=='queued' and r.data['estimated_seconds_remaining']>0
    context=selected.pop('profile')
    assert '- [CV] Keep the profile concise' in context and 'OTHER_ACCOUNT_PREFERENCE' not in context
    assert selected=={'job_id':job.id,'user_id':owner.id,'cv':'de','letter':'anschreiben','create_cv':True,'create_letter':True,'provider':'openai','model':'gpt-5.5','effort':'high','speed':'fast'}
    assert client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'create_cv':False,'create_letter':False}, format='json').status_code==400
    monkeypatch.setattr('jobradar.views.start_cv_task', lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('cannot schedule new futures after interpreter shutdown')))
    unavailable=client.post(f'/api/jobs/{job.id}/cv-generation/run/', payload, format='json')
    assert unavailable.status_code==503 and unavailable.data=={'detail':'CV generation is restarting. Try again shortly.'}
    monkeypatch.setattr('jobradar.views.start_cv_task', start)
    cache.clear()
    assert [client.post(f'/api/jobs/{job.id}/cv-generation/run/', payload, format='json').status_code for _ in range(4)]==[202]*4


@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test')
def test_cv_task_status_and_download_are_owner_only(client, owner, job, monkeypatch):
    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    monkeypatch.setattr('jobradar.views.get_cv_task', lambda task_id,user_id: {'id':task_id,'status':'ready','progress':100,'stage':'Ready'} if user_id==owner.id else None)
    monkeypatch.setattr('jobradar.views.get_cv_task_download', lambda task_id,user_id: (b'zip','application.zip') if user_id==owner.id else None)
    monkeypatch.setattr('jobradar.views.cancel_cv_task', lambda task_id,user_id: True if user_id==owner.id else None)
    monkeypatch.setattr('jobradar.views.start_cv_revision', lambda task_id,user_id,instructions,image=None: 'revision123' if user_id==owner.id and (instructions or image) else None)
    compile_config={}
    monkeypatch.setattr('jobradar.views.start_cv_compile_task',lambda *args: compile_config.update(args=args) or 'compile123')
    recovered_config={}
    monkeypatch.setattr('jobradar.views.latest_generated_sources', lambda job,cv: ('latest-cv.tex',None))
    monkeypatch.setattr('jobradar.views.load_candidate_evidence', lambda profile, learned='': profile + learned)
    def start_recovered(*args,**kwargs): recovered_config.update(args=args,kwargs=kwargs); return 'restart123'
    monkeypatch.setattr('jobradar.views.start_cv_task', start_recovered)
    assert client.get('/api/cv-generation/tasks/task123/').data['stage']=='Ready'
    assert client.post('/api/cv-generation/tasks/task123/cancel/').status_code==202
    download=client.get('/api/cv-generation/tasks/task123/download/')
    assert download.status_code==200 and download.content==b'zip'
    compiled=client.post(f'/api/jobs/{job.id}/cv-generation/recompile-latest/',{'cv_template':'de'},format='json')
    assert compiled.status_code==202 and compiled.data['task_id']=='compile123' and compile_config['args'][3:] == ('latest-cv.tex',None)
    other=User.objects.create_user('other@example.test', email='other@example.test', password='pw')
    other_client=APIClient(); other_client.force_authenticate(other)
    revision=client.post('/api/cv-generation/tasks/task123/revise/', {'instructions':'Shorten profile'}, format='json')
    assert revision.status_code==202 and revision.data['task_id']=='revision123'
    cache.clear()
    recovered=client.post(f'/api/jobs/{job.id}/cv-generation/revise-latest/', {'instructions':'Use less text','cv_template':'de','letter_template':'anschreiben','provider':'openai','model':'gpt-5.5','effort':'medium'}, format='json')
    assert recovered.status_code==202 and recovered.data['task_id']=='restart123'
    assert recovered_config['args'][5] is False and recovered_config['kwargs']['create_cv'] is True
    image_only=client.post(f'/api/jobs/{job.id}/cv-generation/revise-latest/', {'correction_image':PNG_DATA_URL,'cv_template':'de','letter_template':'anschreiben','provider':'openai','model':'gpt-5.5','effort':'medium'}, format='json')
    assert image_only.status_code==202 and recovered_config['kwargs']['correction_image'][1]=='.png'
    assert client.post(f'/api/jobs/{job.id}/cv-generation/revise-latest/', {'correction_image':'bad'}, format='json').status_code==400
    assert other_client.get('/api/cv-generation/tasks/task123/').status_code==404
    assert other_client.post('/api/cv-generation/tasks/task123/cancel/').status_code==404
    assert other_client.post('/api/cv-generation/tasks/task123/revise/', {'instructions':'hack'}, format='json').status_code==404


def test_cv_model_discovery_includes_anthropic_and_installed_local_models(monkeypatch):
    from types import SimpleNamespace
    from jobradar.services import cv_generator

    monkeypatch.setattr(cv_generator, 'codex_model_options', lambda: [{'provider':'openai','key':'gpt','label':'GPT','efforts':['low'],'default_effort':'low','fast_tier':''}])
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda command: command if command in ('claude','ollama','lms') else None)
    def run(command, **kwargs):
        if command[0]=='ollama': return SimpleNamespace(stdout='NAME ID SIZE MODIFIED\nqwen:latest 1 1GB now\nnomic-embed-text 2 1GB now\n')
        return SimpleNamespace(stdout=json.dumps([{'modelKey':'gemma','displayName':'Gemma'}]))
    monkeypatch.setattr(cv_generator.subprocess, 'run', run)
    options=cv_generator.available_model_options()
    assert {'openai','anthropic','ollama','lmstudio'} <= {option['provider'] for option in options}
    assert any(option['provider']=='ollama' and option['key']=='qwen:latest' for option in options)
    assert not any('embed' in option['key'] for option in options if option['provider']=='ollama')


def test_cv_generation_uses_temporary_copies(db, tmp_path, monkeypatch, settings):
    import zipfile
    from io import BytesIO
    from types import SimpleNamespace
    from jobradar.services import cv_generator
    from jobradar.services.cv_generator import generate_cv_package, recompile_generated_package

    cv=tmp_path/'CVs'/'German - AI Engineer (base)_v_1.3.tex'; cv.parent.mkdir()
    letter=tmp_path/'Motivationsschreiben.tex'; picture=tmp_path/'CVs'/'Picture.jpg'
    cv.write_text('original cv'); letter.write_text('original letter'); picture.write_bytes(b'jpg')
    settings.CODEX_CV_WORKSPACE=str(tmp_path); settings.CODEX_CV_OPEN_OUTPUT_FOLDER=True; settings.CODEX_CV_CACHE=False
    opened=[]; monkeypatch.setattr(cv_generator.os, 'startfile', lambda path: opened.append(__import__('pathlib').Path(path)), raising=False)
    monkeypatch.setattr('jobradar.services.cv_generator.shutil.which', lambda command: command)
    monkeypatch.setattr('jobradar.services.cv_generator.available_model_options', lambda: [
        {'provider':'openai','key':'gpt-5.5','label':'GPT-5.5','efforts':['low','medium','high','xhigh'],'default_effort':'medium','fast_tier':'priority'},
        {'provider':'anthropic','key':'sonnet','label':'Claude Sonnet','efforts':cv_generator.CLAUDE_EFFORTS,'default_effort':'medium','fast_tier':''},
        {'provider':'ollama','key':'qwen','label':'qwen','efforts':['default'],'default_effort':'default','fast_tier':''},
    ])
    commands=[]; prompts=[]; correction_dirs=[]; page_counts={'CV':2,'Letter':1}; compile_failures=[]; invalid_outputs=[]
    correction_image=cv_generator.decode_correction_image(PNG_DATA_URL)
    generated={'cv_tex':'\\documentclass{article}\\begin{document}tailored cv\\end{document}','letter_tex':'\\documentclass{article}\\begin{document}tailored letter\\end{document}','changed_files':['cv.tex','letter.tex'],'main_changes':['Tailored content'],'unsupported_requirements_not_claimed':['Unsupported tool'],'confirmations':{'cv_max_2_pages':True,'letter_max_1_page':True,'no_orphaned_employer_headings':True,'no_text_overlap':True,'nothing_after_end_document':True,'links_work':True,'photo_loads_if_used':True,'no_invented_tools_or_overclaims':True}}

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0]=='pdfinfo':
            pages=page_counts['Letter'] if 'Letter' in str(command[-1]) else page_counts['CV']
            return SimpleNamespace(returncode=0, stdout=f'Pages: {pages}\nPage size: 612 x 792 pts', stderr='')
        if command[0]=='pdftoppm':
            __import__('pathlib').Path(str(command[-1])+'-1.png').write_bytes(b'png')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if command[0] in ('codex','claude'):
            prompts.append(kwargs['input'])
            # revision prompts drop CANDIDATE FACTS AND RULES (and the 📌 profile marker within it) to stay minimal
            assert kwargs['encoding']=='utf-8' and 'timeout' not in kwargs and ('📌' in kwargs['input']) == ('CANDIDATE FACTS AND RULES' in kwargs['input'])
        if command[0]=='codex':
            assert command[-1]=='-' and {'--ignore-user-config','--ignore-rules'} <= set(command) and 'ORIGINAL JOB TEXT (UNTRUSTED)' in kwargs['input']
            if 'USER-PROVIDED CORRECTION IMAGE' in kwargs['input']:
                output=__import__('pathlib').Path(command[command.index('--cd')+1]); correction_dirs.append(output)
                assert (output/'user-correction-reference.png').read_bytes()==correction_image[0]
                assert command[command.index('--image')+1]==str(output/'user-correction-reference.png')
            if '--oss' not in command:
                assert command[command.index('--model')+1]=='gpt-5.5'
                assert 'model_reasoning_effort="high"' in command
            result_path=__import__('pathlib').Path(command[command.index('--output-last-message')+1])
            result_path.write_text('{"cv_tex":"broken"}' if invalid_outputs and invalid_outputs.pop() else json.dumps(generated))
            return SimpleNamespace(returncode=0, stdout='ok', stderr='')
        if command[0]=='claude':
            # The chosen effort must actually reach the CLI, not merely be offered in the UI.
            assert command[command.index('--effort')+1] in cv_generator.CLAUDE_EFFORTS, command
            return SimpleNamespace(returncode=0, stdout=json.dumps({'structured_output':generated}), stderr='')
        output=__import__('pathlib').Path(kwargs['cwd'])
        assert command[0]=='pdflatex' and 'timeout' not in kwargs and kwargs['stdin'] is cv_generator.subprocess.DEVNULL
        if compile_failures and compile_failures.pop():
            (output/__import__('pathlib').Path(command[-1]).with_suffix('.log')).write_text('Undefined control sequence on line 42')
            return SimpleNamespace(returncode=1, stdout='compile failed', stderr='')
        (output/__import__('pathlib').Path(command[-1]).with_suffix('.pdf')).write_bytes(b'pdf')
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')

    monkeypatch.setattr('jobradar.services.cv_generator.subprocess.run', fake_run)
    user=User.objects.create_user('cv-owner')
    job=JobLead.objects.create(company='Firma', title='Entwickler', raw_description='Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben.', created_by=user)
    with pytest.raises(ValueError, match='matching the CV language'):
        generate_cv_package(job, 'Factual profile', 'en', 'anschreiben', True, 'openai', 'gpt-5.5', 'high', 'fast')
    with pytest.raises(ValueError, match='speed supported'):
        generate_cv_package(job, 'Factual profile', 'de', 'motivationsschreiben', True, 'openai', 'gpt-5.5', 'high', 'turbo')
    with pytest.raises(RuntimeError, match='Current target TeX files'):
        generate_cv_package(job, 'Factual profile', 'de', 'motivationsschreiben', True, 'openai', 'gpt-5.5', 'high', revision_instructions='change layout')
    # Anthropic runs through the same pipeline; fake_run asserts --effort xhigh reaches the CLI.
    generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'anthropic', 'sonnet', 'xhigh')
    assert any(command[0]=='claude' and '--effort' in command and command[command.index('--effort')+1]=='xhigh' for command in commands)
    progress=[]
    archive,_,saved=generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'openai', 'gpt-5.5', 'high', 'fast', lambda percent,stage: progress.append((percent,stage)))
    names=zipfile.ZipFile(BytesIO(archive)).namelist()
    assert len([name for name in names if name.endswith('.pdf')])==2
    assert [stage for _,stage in progress]==['Preparing templates','Generating CV and motivation letter','CV and letter generated','Compiling CV','CV compiled','Compiling motivation letter','Motivation letter compiled','Saving files']
    settings.CODEX_CV_CACHE=True
    before=sum(command[0]=='codex' for command in commands)
    cached_first=generate_cv_package(job, 'Cached profile 📌', 'de', '', False, 'openai', 'gpt-5.5', 'high')
    cached_progress=[]
    cached_second=generate_cv_package(job, 'Cached profile 📌', 'de', '', False, 'openai', 'gpt-5.5', 'high', progress=lambda percent,stage: cached_progress.append(stage))
    assert cached_second==cached_first and sum(command[0]=='codex' for command in commands)==before+1
    assert cached_progress==['Preparing templates','Using saved package']
    settings.CODEX_CV_CACHE=False
    repairs=sum('AUTOMATIC REPAIR ATTEMPT' in prompt for prompt in prompts)
    compile_failures.append(True)
    generate_cv_package(job, 'Factual profile 📌', 'de', '', False, 'openai', 'gpt-5.5', 'high')
    invalid_outputs.append(True)
    generate_cv_package(job, 'Factual profile 📌', 'de', '', False, 'openai', 'gpt-5.5', 'high')
    assert sum('AUTOMATIC REPAIR ATTEMPT' in prompt for prompt in prompts)==repairs+2
    generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'anthropic', 'sonnet', 'medium', 'normal')
    generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'ollama', 'qwen', 'default', 'normal')
    cv_only_progress=[]
    cv_only,_,cv_only_saved=generate_cv_package(job, 'Factual profile 📌', 'de', '', False, 'openai', 'gpt-5.5', 'high', 'normal', lambda percent,stage: cv_only_progress.append((percent,stage)))
    assert len([name for name in zipfile.ZipFile(BytesIO(cv_only)).namelist() if name.endswith('.pdf')])==1
    assert __import__('pathlib').Path(saved['cv_tex']).parent==tmp_path/'CVs'
    assert __import__('pathlib').Path(saved['cv_pdf']).parent==tmp_path/'CVs'
    assert __import__('pathlib').Path(saved['letter_tex']).parent==tmp_path/'output'
    assert __import__('pathlib').Path(saved['letter_pdf']).parent==tmp_path/'output'
    model_calls=sum(command[0] in ('codex','claude') for command in commands)
    recompiled,_,recompiled_saved=recompile_generated_package(job,'de',saved['cv_tex'],saved['letter_tex'])
    assert len([name for name in zipfile.ZipFile(BytesIO(recompiled)).namelist() if name.endswith('.pdf')])==2
    assert recompiled_saved['cv_tex']==saved['cv_tex'] and sum(command[0] in ('codex','claude') for command in commands)==model_calls
    _,_,revised_saved=generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'openai', 'gpt-5.5', 'high', 'normal', source_cv=saved['cv_tex'], source_letter=saved['letter_tex'], revision_instructions='Fix the page break and overlap')
    assert revised_saved==saved
    _,_,image_revised_saved=generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'openai', 'gpt-5.5', 'high', 'normal', source_cv=saved['cv_tex'], source_letter=saved['letter_tex'], correction_image=correction_image)
    assert image_revised_saved==saved and not correction_dirs[-1].exists()
    assert any('CURRENT GENERATED PDF LAYOUT CONTEXT' in prompt and 'current-CV-page-1.png' in prompt and 'SOURCE PRIORITY' in prompt for prompt in prompts)
    assert any('USER-PROVIDED CORRECTION IMAGE' in prompt and 'user-correction-reference.png' in prompt for prompt in prompts)
    assert __import__('pathlib').Path(cv_only_saved['cv_pdf']).name != __import__('pathlib').Path(saved['cv_pdf']).name
    assert opened and all(path==tmp_path/'CVs' for path in opened)
    assert not any('letter' in stage.lower() for _,stage in cv_only_progress)
    letter_only,_,letter_only_saved=generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'openai', 'gpt-5.5', 'high', 'normal', create_cv=False)
    assert len([name for name in zipfile.ZipFile(BytesIO(letter_only)).namelist() if name.endswith('.pdf')])==1
    assert set(letter_only_saved)=={'letter_tex','letter_pdf','report'} and opened[-1]==tmp_path/'output'
    assert letter_only_saved['report']['unsupported_requirements_not_claimed']==['Unsupported tool']
    with pytest.raises(ValueError, match='at least'):
        generate_cv_package(job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'high', create_cv=False)
    page_counts['CV']=3
    with pytest.raises(RuntimeError, match='CV.*2-page limit.*repair') as failure:
        generate_cv_package(job, 'Factual profile 📌', 'de', '', False, 'openai', 'gpt-5.5', 'high')
    assert failure.value.repair_attempts==2 and 'compiled to 3 pages' in failure.value.diagnostics
    page_counts['CV']=2; page_counts['Letter']=2
    with pytest.raises(RuntimeError, match='motivation letter.*1-page limit.*repair'):
        generate_cv_package(job, 'Factual profile 📌', 'de', 'motivationsschreiben', True, 'openai', 'gpt-5.5', 'high', create_cv=False)
    assert not any(command[0]=='latexmk' for command in commands)
    assert any(command[0]=='claude' and '--json-schema' in command for command in commands)
    assert any(command[0]=='codex' and '--oss' in command and command[command.index('--local-provider')+1]=='ollama' for command in commands)
    assert cv.read_text()=='original cv' and letter.read_text()=='original letter'


def test_cv_revision_uses_minimal_prompt_and_preserves_unrelated_tex(db, tmp_path, monkeypatch, settings):
    from types import SimpleNamespace
    from jobradar.services.cv_generator import generate_cv_package

    cv=tmp_path/'CVs'/'German - AI Engineer (base)_v_1.3.tex'; cv.parent.mkdir()
    picture=tmp_path/'CVs'/'Picture.jpg'
    cv.write_text('original cv'); picture.write_bytes(b'jpg')
    settings.CODEX_CV_WORKSPACE=str(tmp_path); settings.CODEX_CV_OPEN_OUTPUT_FOLDER=False; settings.CODEX_CV_CACHE=False
    monkeypatch.setattr('jobradar.services.cv_generator.shutil.which', lambda command: command)
    monkeypatch.setattr('jobradar.services.cv_generator.available_model_options', lambda: [
        {'provider':'openai','key':'gpt-5.5','label':'GPT-5.5','efforts':['low','medium','high','xhigh'],'default_effort':'medium','fast_tier':'priority'},
    ])
    user=User.objects.create_user('revision-owner')
    job=JobLead.objects.create(company='Firma', title='Entwickler', raw_description='Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben.', created_by=user)

    unrelated='\\section{Experience}\nUnrelated bullet that must survive.'
    confirmations={'cv_max_2_pages':True,'letter_max_1_page':True,'no_orphaned_employer_headings':True,'no_text_overlap':True,'nothing_after_end_document':True,'links_work':True,'photo_loads_if_used':True,'no_invented_tools_or_overclaims':True}
    initial_cv=f'\\documentclass{{article}}\\begin{{document}}Old headline. {unrelated}\\end{{document}}'
    revised_cv=f'\\documentclass{{article}}\\begin{{document}}New headline. {unrelated}\\end{{document}}'
    responses=iter([
        {'cv_tex':initial_cv,'changed_files':['cv.tex'],'main_changes':['Initial tailoring'],'unsupported_requirements_not_claimed':[],'confirmations':confirmations},
        {'cv_tex':revised_cv,'changed_files':['cv.tex'],'main_changes':['Shortened headline'],'unsupported_requirements_not_claimed':[],'confirmations':confirmations},
    ])
    prompts=[]

    def fake_run(command, **kwargs):
        if command[0]=='pdfinfo':
            return SimpleNamespace(returncode=0, stdout='Pages: 1\nPage size: 612 x 792 pts', stderr='')
        if command[0]=='codex':
            prompts.append(kwargs['input'])
            result_path=__import__('pathlib').Path(command[command.index('--output-last-message')+1])
            result_path.write_text(json.dumps(next(responses)))
            return SimpleNamespace(returncode=0, stdout='ok', stderr='')
        output=__import__('pathlib').Path(kwargs['cwd'])
        (output/__import__('pathlib').Path(command[-1]).with_suffix('.pdf')).write_bytes(b'pdf')
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')

    monkeypatch.setattr('jobradar.services.cv_generator.subprocess.run', fake_run)
    profile='CANDIDATE FACTS AND RULES marker profile'
    _,_,saved=generate_cv_package(job, profile, 'de', '', False, 'openai', 'gpt-5.5', 'medium', create_cv=True)
    initial_prompt=prompts[-1]
    assert 'CANDIDATE FACTS AND RULES' in initial_prompt

    _,_,revised=generate_cv_package(job, profile, 'de', '', False, 'openai', 'gpt-5.5', 'medium', create_cv=True, source_cv=saved['cv_tex'], revision_instructions='Shorten the headline')
    revision_prompt=prompts[-1]
    # requested text changes while unrelated TeX content survives
    saved_text=__import__('pathlib').Path(saved['cv_tex']).read_text()
    assert revised['cv_tex']==saved['cv_tex'] and saved_text==revised_cv
    assert 'New headline' in saved_text and 'Old headline' not in saved_text and unrelated in saved_text
    # revision prompt drops candidate evidence/adaptation-rules/existing-evaluation/full job text but keeps instructions, language pin, honesty+page-limit rules, and a job identity anchor
    assert 'CANDIDATE FACTS AND RULES' not in revision_prompt and 'EXISTING EVALUATION' not in revision_prompt and job.raw_description not in revision_prompt
    assert 'CURRENT USER ADJUSTMENT INSTRUCTIONS' in revision_prompt and 'Shorten the headline' in revision_prompt
    assert 'Required CV language: German' in revision_prompt
    assert 'Never invent experience' in revision_prompt and 'CV maximum: two pages' in revision_prompt
    assert 'SOURCE PRIORITY' in revision_prompt and f'Company: {job.company}' in revision_prompt and f'Title: {job.title}' in revision_prompt
    assert len(revision_prompt) < len(initial_prompt)*.5


def test_cv_task_completes_and_is_user_scoped(job, monkeypatch, tmp_path):
    import time
    from jobradar.services import cv_tasks

    cv_tasks._tasks.clear()
    monkeypatch.setattr(cv_tasks.JobLead.objects, 'get', lambda id: job)
    copied=[]; monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: copied.append(text) or True)
    learned_calls=[]
    def learn(user_id, instructions, create_cv, create_letter):
        if not instructions: return ''
        learned_calls.append((user_id,instructions,create_cv,create_letter))
        return '- [CV + letter] ' + instructions
    monkeypatch.setattr(cv_tasks, '_learn_application_preference', learn)
    calls=[]
    latest=tmp_path/'latest.tex'; latest.write_text('generated CV TeX 📌', encoding='utf-8')
    latest_letter=tmp_path/'latest-letter.tex'; latest_letter.write_text('generated letter TeX 📌', encoding='utf-8')
    clipboard='% ===== latest.tex =====\ngenerated CV TeX 📌\n\n% ===== latest-letter.tex =====\ngenerated letter TeX 📌'
    assert cv_tasks._clipboard_contents({'cv_tex':str(latest)})=='generated CV TeX 📌'
    assert cv_tasks._clipboard_contents({'letter_tex':str(latest_letter)})=='generated letter TeX 📌'
    def generate(job, profile, cv, letter, create_letter, provider, model, effort, speed, progress, source_cv=None, source_letter=None, revision_instructions='', create_cv=True, correction_image=None, cancelled=None):
        assert (provider,model,effort,speed)==('openai','gpt-5.5','medium','normal')
        calls.append((source_cv,source_letter,revision_instructions,correction_image))
        progress(10,'Generating CV and motivation letter'); progress(95,'Motivation letter compiled')
        return b'zip','application.zip',{'cv_pdf':'ready.pdf','cv_tex':str(latest),'letter_tex':str(latest_letter)}
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)
    task_id=cv_tasks.start_cv_task(job.id, job.created_by_id, 'profile', 'en', 'motivation_letter', True, 'openai', 'gpt-5.5', 'medium', 'normal')
    for _ in range(100):
        task=cv_tasks.get_cv_task(task_id, job.created_by_id)
        if task['status']=='ready': break
        time.sleep(.01)
    assert task['progress']==100 and task['stage']=='Ready'
    assert cv_tasks.get_cv_task(task_id, -1) is None
    assert cv_tasks.get_cv_task_download(task_id, job.created_by_id)==(b'zip','application.zip')
    assert task['artifacts']['cv_pdf']=='ready.pdf' and task['clipboard_tex']==clipboard
    assert task['clipboard_copied'] is True and copied==[clipboard]
    monkeypatch.setattr(cv_tasks,'recompile_generated_package',lambda job,cv,source_cv,source_letter,progress,cancelled=None:(progress(95,'Motivation letter compiled') or (b'recompiled','recompiled.zip',{'cv_tex':str(latest),'letter_tex':str(latest_letter)})))
    compile_id=cv_tasks.start_cv_compile_task(job.id,job.created_by_id,'en',str(latest),str(latest_letter))
    for _ in range(100):
        compiled=cv_tasks.get_cv_task(compile_id,job.created_by_id)
        if compiled['status']=='ready': break
        time.sleep(.01)
    assert compiled['status']=='ready' and cv_tasks.get_cv_task_download(compile_id,job.created_by_id)==(b'recompiled','recompiled.zip')
    revision_id=cv_tasks.start_cv_revision(task_id, job.created_by_id, 'Shorten the profile')
    for _ in range(100):
        revision_task=cv_tasks.get_cv_task(revision_id, job.created_by_id)
        if revision_task['status']=='ready': break
        time.sleep(.01)
    assert revision_task['status']=='ready'
    assert calls[-1][:3]==(str(latest),str(latest_letter),'Shorten the profile')
    image_revision_id=cv_tasks.start_cv_revision(revision_id, job.created_by_id, '', (b'png','.png'))
    for _ in range(100):
        image_revision=cv_tasks.get_cv_task(image_revision_id, job.created_by_id)
        if image_revision['status']=='ready': break
        time.sleep(.01)
    assert image_revision['status']=='ready' and calls[-1][2:]==('',(b'png','.png'))
    learned='- [CV + letter] Shorten the profile'
    assert revision_task['learned_preference']==learned
    assert learned_calls==[(job.created_by_id,'Shorten the profile',True,True)]
    before=list(learned_calls)
    generation_error=RuntimeError('full compiler output'); generation_error.public_message='LaTeX could not compile the CV after repair.'; generation_error.diagnostics='line 42: undefined control sequence'; generation_error.repair_attempts=2
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', lambda *args,**kwargs: (_ for _ in ()).throw(generation_error))
    failed_id=cv_tasks.start_cv_revision(revision_id, job.created_by_id, 'This must not be learned')
    for _ in range(100):
        failed=cv_tasks.get_cv_task(failed_id, job.created_by_id)
        if failed['status']=='failed': break
        time.sleep(.01)
    assert failed['status']=='failed' and failed['stage']=='Failed' and failed['error']=='LaTeX could not compile the CV after repair.'
    assert failed['repair_attempts']==2 and 'undefined control sequence' in failed['diagnostics'] and learned_calls==before
    with pytest.raises(ValueError): cv_tasks.start_cv_revision(task_id, -1, 'hack')


def test_cv_tasks_run_as_parallel_agents_with_live_eta(job, monkeypatch):
    import time
    from threading import Event, Lock
    from jobradar.services import cv_tasks

    cv_tasks._tasks.clear(); cv_tasks._stage_history.clear()
    monkeypatch.setattr(cv_tasks.JobLead.objects, 'get', lambda id: job)
    both_entered=Event(); release=Event(); entered=[]; entered_lock=Lock()
    def generate(job, profile, cv, letter, create_letter, provider, model, effort, speed, progress, *args, **kwargs):
        progress(5,'Preparing templates'); progress(10,'Generating CV')
        with entered_lock:
            entered.append(job.id)
            if len(entered)==2: both_entered.set()
        release.wait(2)
        progress(65,'CV generated'); progress(70,'Compiling CV'); progress(82,'CV compiled'); progress(97,'Saving files')
        return b'zip','application.zip',{}
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)
    first_id=cv_tasks.start_cv_task(job.id, job.created_by_id, 'profile', 'en', '', False, 'openai', 'gpt-5.5', 'medium', 'normal')
    second_id=cv_tasks.start_cv_task(job.id, job.created_by_id, 'profile', 'en', '', False, 'openai', 'gpt-5.5', 'medium', 'normal')
    try:
        assert both_entered.wait(1)
        with cv_tasks._lock:
            cv_tasks._tasks[first_id]['_stage_started_at']-=45
            cv_tasks._tasks[first_id]['_created_at']-=50
        first=cv_tasks.get_cv_task(first_id,job.created_by_id); second=cv_tasks.get_cv_task(second_id,job.created_by_id)
        assert 10 < first['progress'] < 65 and first['estimated_seconds_remaining'] > 0 and first['elapsed_seconds'] >= 50
        assert second['status']=='running' and second['estimated_seconds_remaining'] > 0
    finally:
        release.set()
    for _ in range(100):
        first=cv_tasks.get_cv_task(first_id,job.created_by_id); second=cv_tasks.get_cv_task(second_id,job.created_by_id)
        if first['status']=='ready' and second['status']=='ready': break
        time.sleep(.01)
    assert first['progress']==second['progress']==100
    assert first['estimated_seconds_remaining']==second['estimated_seconds_remaining']==0


@throttled_rest_framework(cv_generation_user='100/hour')
@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test')
def test_cv_generation_rejects_unsupported_capability_combinations(client, owner, job, monkeypatch):
    from jobradar.services import cv_generator
    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    monkeypatch.setattr(cv_generator, 'available_model_options', lambda: [
        {'provider':'openai','key':'gpt-5.4-mini','label':'GPT-5.4-Mini','efforts':['low','medium','high','xhigh'],'default_effort':'medium','fast_tier':''},
        {'provider':'openai','key':'gpt-5.5','label':'GPT-5.5','efforts':['low','medium','high','xhigh'],'default_effort':'medium','fast_tier':'priority'},
        {'provider':'anthropic','key':'sonnet','label':'Claude Sonnet','efforts':['default'],'default_effort':'default','fast_tier':''},
    ])
    started=[]
    monkeypatch.setattr('jobradar.views.start_cv_task', lambda *args,**kwargs: started.append((args,kwargs)) or 'task123')

    unsupported_effort=client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'provider':'openai','model':'gpt-5.5','effort':'ultra','speed':'normal'}, format='json')
    assert unsupported_effort.status_code==400 and 'ultra' in unsupported_effort.data['detail'] and 'GPT-5.5' in unsupported_effort.data['detail']

    unsupported_fast=client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'provider':'openai','model':'gpt-5.4-mini','effort':'medium','speed':'fast'}, format='json')
    assert unsupported_fast.status_code==400 and 'fast' in unsupported_fast.data['detail'].lower()

    unknown_model=client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'provider':'openai','model':'not-a-model','effort':'medium'}, format='json')
    assert unknown_model.status_code==400

    fast_ok=client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'provider':'openai','model':'gpt-5.5','effort':'medium','speed':'fast'}, format='json')
    assert fast_ok.status_code==202

    anthropic_ok=client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'provider':'anthropic','model':'sonnet','effort':'default','speed':'normal'}, format='json')
    assert anthropic_ok.status_code==202

    assert len(started)==2  # only the two accepted combinations reached start_cv_task


def test_cv_task_step_progress_reflects_route_completion_and_cache_reduction():
    from jobradar.services import cv_tasks

    plan,defaults,estimate_key=cv_tasks._task_timing('openai','gpt-5.5','medium','normal',True,True,False)
    assert plan==['preparing','generating','generated','compiling_cv','cv_compiled','compiling_letter','letter_compiled','saving']
    task={'status':'running','stage':'Preparing templates','_stage_key':'preparing','_stage_plan':plan}
    assert cv_tasks._step_progress(task)==(0,5,'Preparing templates')
    task['_stage_key']='generating'
    assert cv_tasks._step_progress(task)==(1,5,'Generating documents')
    task['_stage_key']='generated'
    assert cv_tasks._step_progress(task)==(2,5,'Documents generated')
    task['_stage_key']='compiling_cv'
    assert cv_tasks._step_progress(task)==(2,5,'Compiling CV')
    # Each finished PDF is reported explicitly, not merely implied by the step counter advancing.
    task['_stage_key']='cv_compiled'
    assert cv_tasks._step_progress(task)==(3,5,'CV compiled')
    task['_stage_key']='compiling_letter'
    assert cv_tasks._step_progress(task)==(3,5,'Compiling motivation letter')
    task['_stage_key']='letter_compiled'
    assert cv_tasks._step_progress(task)==(4,5,'Motivation letter compiled')
    task['_stage_key']='saving'
    assert cv_tasks._step_progress(task)==(4,5,'Saving files')
    task['status']='ready'
    assert cv_tasks._step_progress(task)==(5,5,'Ready')

    # CV-only skips the letter step entirely -- no phantom step in the total.
    cv_only_plan,_,_=cv_tasks._task_timing('openai','gpt-5.5','medium','normal',True,False,False)
    assert cv_tasks._plan_steps(cv_only_plan)==['preparing','generating','compiling_cv','saving']

    # PDF-only recompile of both artifacts: 2 steps, no preparing/generating/saving phantom steps.
    recompile_plan=['compiling_cv','cv_compiled','compiling_letter','letter_compiled']
    assert cv_tasks._plan_steps(recompile_plan)==['compiling_cv','compiling_letter']

    # An exact cache hit is only known at runtime -- _update() collapses the plan once it fires,
    # so the total shrinks from the full generate/compile/save route down to 2 steps.
    now=__import__('time').monotonic()
    cv_tasks._tasks.clear(); cv_tasks._stage_history.clear()
    cv_tasks._tasks['cache-task']={'id':'cache-task','user_id':1,'status':'running','progress':5,'stage':'Preparing templates','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_copied':False,'learned_preference':'','diagnostics':'','repair_attempts':0,'_created_at':now,'_started_at':now,'_finished_at':None,'_stage_key':'preparing','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':defaults,'_estimate_key':estimate_key,'updated_at':__import__('time').time()}
    cv_tasks._update('cache-task', status='running', progress=97, stage='Using saved package')
    cached=cv_tasks.get_cv_task('cache-task', 1)
    assert cached['step_total']==2 and cached['step_completed']==1 and cached['step_label']=='Using saved package'
    cv_tasks._tasks.clear()


def test_long_generation_recycles_the_db_connection_before_learning_a_preference(db, job, owner, monkeypatch):
    from threading import Event
    from jobradar.services import cv_tasks

    # Regression: a revision that ran ~280s failed at the very end with "server closed the
    # connection unexpectedly" -- the pooled connection had gone stale during the model call, and
    # _learn_application_preference was the first query after it. Generation never hit this because
    # it passes empty instructions and returns before touching the database.
    order=[]
    monkeypatch.setattr(cv_tasks,'close_old_connections',lambda:order.append('recycle'))
    monkeypatch.setattr(cv_tasks,'generate_cv_package',lambda *a,**k:(order.append('generate'),(b'zip','a.zip',{}))[1])
    monkeypatch.setattr(cv_tasks,'_learn_application_preference',lambda *a,**k:(order.append('db-write'),'')[1])
    monkeypatch.setattr(cv_tasks,'_clipboard_contents',lambda artifacts:'')
    monkeypatch.setattr(cv_tasks,'_copy_to_clipboard',lambda text:False)

    # Called directly rather than via start_cv_task: the worker thread would use its own connection
    # and could not see this test's uncommitted transaction.
    cv_tasks._run('t1', job.id, owner.id, 'ctx', 'en', 'motivation_letter', True,
                  'openai','gpt-5.5','medium','normal',
                  revision_instructions='tweak the summary', cancel_event=Event())

    assert 'db-write' in order, order
    assert order.index('recycle', order.index('generate')) < order.index('db-write'), order


def test_latest_cv_template_picks_the_newest_version_on_disk(tmp_path, settings):
    from jobradar.services import cv_generator

    settings.CODEX_CV_WORKSPACE=str(tmp_path)
    cvs=tmp_path/'CVs'; cvs.mkdir(parents=True)
    for name in ('English - AI Engineer (base)_v_1.2.tex','English - AI Engineer (base)_v_1.3.tex','English - AI Engineer (base)_v_1.4.tex'):
        (cvs/name).write_text('cv', encoding='utf-8')
    assert cv_generator.latest_cv_template('en')=='CVs/English - AI Engineer (base)_v_1.4.tex'

    # Numeric compare, not lexical: _v_1.10 must beat _v_1.9.
    (cvs/'English - AI Engineer (base)_v_1.9.tex').write_text('cv', encoding='utf-8')
    (cvs/'English - AI Engineer (base)_v_1.10.tex').write_text('cv', encoding='utf-8')
    assert cv_generator.latest_cv_template('en')=='CVs/English - AI Engineer (base)_v_1.10.tex'

    # A different role's template must not be mistaken for a newer base CV.
    (cvs/'English - Backend Engineer_v_9.9.tex').write_text('cv', encoding='utf-8')
    assert cv_generator.latest_cv_template('en')=='CVs/English - AI Engineer (base)_v_1.10.tex'

    # Nothing on disk: fall back to the declared template rather than crashing.
    settings.CODEX_CV_WORKSPACE=str(tmp_path/'empty')
    assert cv_generator.latest_cv_template('en')==cv_generator.TEMPLATES['en']['cv'][0]
    assert cv_generator.latest_cv_template('de')==cv_generator.TEMPLATES['de']['cv'][0]


def test_available_model_options_are_cached_between_calls(monkeypatch):
    from jobradar.services import cv_generator

    calls=[]
    monkeypatch.setattr(cv_generator,'_discover_model_options',lambda:(calls.append(1) or [{'provider':'openai','key':'gpt-5.5','efforts':['medium'],'default_effort':'medium','fast_tier':''}]))
    first=cv_generator.available_model_options()
    second=cv_generator.available_model_options()
    # The popup hits this on every open; shelling out to ollama/lms each time is the cost being avoided.
    assert first==second and len(calls)==1


def _reveal_task(owner, artifacts):
    from jobradar.services import cv_tasks
    owner.email='owner@example.test'; owner.save()
    now=__import__('time').monotonic()
    cv_tasks._tasks.clear()
    cv_tasks._tasks['reveal-task']={'id':'reveal-task','user_id':owner.id,'status':'ready','progress':100,'stage':'Ready','error':'','archive':None,'filename':'','artifacts':artifacts,'report':None,'clipboard_tex':'','clipboard_copied':False,'learned_preference':'','diagnostics':'','repair_attempts':0,'_created_at':now,'_started_at':now,'_finished_at':now,'_stage_key':'ready','_stage_started_at':now,'_stage_plan':['preparing','saving'],'_stage_defaults':{'preparing':1,'saving':1},'_estimate_key':(),'_stage_times':{},'_initial_eta':2,'updated_at':__import__('time').time()}
    return 'reveal-task'


@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test', CODEX_CV_OPEN_OUTPUT_FOLDER=True)
def test_reveal_artifact_opens_only_a_whitelisted_key_from_the_task_payload(client, owner, tmp_path, monkeypatch):
    from jobradar.services import cv_generator, cv_tasks

    pdf=tmp_path/'Chorinopoulos-Ermis-CV-Acme.pdf'; pdf.write_bytes(b'%PDF')
    opened=[]
    monkeypatch.setattr(cv_generator.os,'startfile',lambda folder:opened.append(str(folder)),raising=False)
    task_id=_reveal_task(owner, {'cv_pdf':str(pdf)})

    ok=client.post(f'/api/cv-generation/tasks/{task_id}/reveal/', {'key':'cv_pdf'}, format='json')
    assert ok.status_code==200 and opened==[str(tmp_path)]

    # A path in the body is not a key: it must be rejected outright, never opened.
    opened.clear()
    injected=client.post(f'/api/cv-generation/tasks/{task_id}/reveal/', {'key':str(tmp_path/'evil.pdf')}, format='json')
    assert injected.status_code==400 and opened==[]
    assert 'cv_tex' in injected.json()['detail']

    # A whitelisted key this task never produced resolves to nothing.
    assert client.post(f'/api/cv-generation/tasks/{task_id}/reveal/', {'key':'letter_pdf'}, format='json').status_code==404
    assert opened==[]

    # An unknown task id cannot be probed.
    assert client.post('/api/cv-generation/tasks/does-not-exist/reveal/', {'key':'cv_pdf'}, format='json').status_code==404
    cv_tasks._tasks.clear()


@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test', CODEX_CV_OPEN_OUTPUT_FOLDER=True)
def test_reveal_artifact_is_not_reachable_by_a_non_owner(db, owner, tmp_path, monkeypatch):
    from jobradar.services import cv_generator, cv_tasks

    pdf=tmp_path/'cv.pdf'; pdf.write_bytes(b'%PDF')
    opened=[]
    monkeypatch.setattr(cv_generator.os,'startfile',lambda folder:opened.append(str(folder)),raising=False)
    task_id=_reveal_task(owner, {'cv_pdf':str(pdf)})
    intruder=User.objects.create_user('intruder', email='intruder@example.test', password='pw')
    stranger=APIClient(); stranger.force_authenticate(intruder)
    assert stranger.post(f'/api/cv-generation/tasks/{task_id}/reveal/', {'key':'cv_pdf'}, format='json').status_code==404
    assert opened==[]
    cv_tasks._tasks.clear()


@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test', CODEX_CV_OPEN_OUTPUT_FOLDER=False)
def test_reveal_artifact_respects_the_open_output_folder_kill_switch(client, owner, tmp_path, monkeypatch):
    from jobradar.services import cv_generator, cv_tasks

    pdf=tmp_path/'cv.pdf'; pdf.write_bytes(b'%PDF')
    opened=[]
    monkeypatch.setattr(cv_generator.os,'startfile',lambda folder:opened.append(str(folder)),raising=False)
    task_id=_reveal_task(owner, {'cv_pdf':str(pdf)})
    response=client.post(f'/api/cv-generation/tasks/{task_id}/reveal/', {'key':'cv_pdf'}, format='json')
    assert response.status_code==409 and opened==[]  # disabled server-side, not merely hidden in the UI
    cv_tasks._tasks.clear()


def test_stage_key_maps_every_reported_event_string_to_a_progress_stage():
    from jobradar.services import cv_tasks

    # The raw strings are whatever cv_generator's progress callback reports; drift here silently
    # breaks the step counter and the ETA, so pin the mapping directly.
    assert cv_tasks._stage_key('Preparing templates')=='preparing'
    assert cv_tasks._stage_key('Generating CV and motivation letter')=='generating'
    assert cv_tasks._stage_key('Repairing generated documents (1/2)')=='generating'
    assert cv_tasks._stage_key('CV and letter generated')=='generated'
    assert cv_tasks._stage_key('Compiling CV')=='compiling_cv'
    assert cv_tasks._stage_key('CV compiled')=='cv_compiled'
    assert cv_tasks._stage_key('Compiling motivation letter')=='compiling_letter'
    assert cv_tasks._stage_key('Motivation letter compiled')=='letter_compiled'
    assert cv_tasks._stage_key('Using saved package')=='cached'
    assert cv_tasks._stage_key('Saving files')=='saving'
    assert cv_tasks._stage_key('Ready')=='ready'
    assert cv_tasks._stage_key('Cancelling')=='cancelling'
    assert cv_tasks._stage_key('something new')=='working'  # unknown strings must not crash
    assert cv_tasks._stage_key(None)=='working'
    # every mapped stage that belongs to a step must be reachable from a real event string
    assert set(cv_tasks._STAGE_STEP) <= {cv_tasks._stage_key(text) for text in
        ['Preparing templates','Generating CV','CV generated','Compiling CV','CV compiled',
         'Compiling motivation letter','Motivation letter compiled','Using saved package','Saving files']}


def test_finished_task_records_estimated_versus_actual_duration_and_phase_timings(tmp_path, settings):
    import json
    import time
    from jobradar.services import cv_tasks

    settings.CODEX_CV_WORKSPACE=str(tmp_path)
    now=time.monotonic()
    plan,defaults,estimate_key=cv_tasks._task_timing('openai','gpt-5.5','medium','normal',True,True,False)
    cv_tasks._tasks.clear(); cv_tasks._stage_history.clear()
    cv_tasks._tasks['bench']={'id':'bench','user_id':1,'status':'running','progress':5,'stage':'Preparing templates','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_copied':False,'learned_preference':'','diagnostics':'','repair_attempts':0,'_created_at':now-42,'_started_at':now-42,'_finished_at':None,'_stage_key':'compiling_cv','_stage_started_at':now-3,'_stage_plan':plan,'_stage_defaults':defaults,'_estimate_key':estimate_key,'_stage_times':{'preparing':2.5},'_initial_eta':61.0,'updated_at':time.time()}
    cv_tasks._update('bench', status='ready', progress=100, stage='Ready')

    rows=[json.loads(line) for line in (tmp_path/'.dachapply-cache'/'cv-benchmarks.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==1
    row=rows[0]
    assert row['route']=='generation' and row['provider']=='openai' and row['model']=='gpt-5.5'
    assert row['status']=='ready' and row['estimated_seconds']==61.0
    assert 40 <= row['actual_seconds'] <= 45  # measured against _created_at, not guessed
    # phase timings survive for the revision/ETA benchmarks, including the stage active at finish
    assert row['stage_seconds']['preparing']==2.5 and row['stage_seconds']['compiling_cv'] >= 2.5
    cv_tasks._tasks.clear()


def test_benchmark_is_not_written_when_the_workspace_does_not_exist(tmp_path, settings):
    import time
    from jobradar.services import cv_tasks

    missing=tmp_path/'not-a-workspace'
    settings.CODEX_CV_WORKSPACE=str(missing)
    cv_tasks._record_benchmark({'id':'x','status':'ready','_created_at':time.monotonic(),'_estimate_key':()}, time.monotonic())
    assert not missing.exists()  # never create the workspace as a side effect of benchmarking


def test_latest_generated_artifacts_survive_a_restart_by_reading_the_workspace(tmp_path, settings):
    from types import SimpleNamespace
    from jobradar.services import cv_generator

    settings.CODEX_CV_WORKSPACE=str(tmp_path)
    job=SimpleNamespace(id=1, company='ACME', title='AI Engineer', raw_description='', language_requirements='', source_text='')
    cv_name,letter_name=cv_generator._target_names(job,'english','english')
    (tmp_path/'CVs').mkdir(parents=True)
    (tmp_path/'output').mkdir(parents=True)
    cv_tex=tmp_path/'CVs'/cv_name; cv_tex.write_text('cv', encoding='utf-8')
    cv_pdf=cv_tex.with_suffix('.pdf'); cv_pdf.write_bytes(b'%PDF')
    letter_tex=tmp_path/'output'/letter_name; letter_tex.write_text('letter', encoding='utf-8')

    # No task record exists here at all -- this is what a page load after a Django restart sees.
    artifacts=cv_generator.latest_generated_artifacts(job,'english')
    assert artifacts['cv_tex']==str(cv_tex) and artifacts['cv_pdf']==str(cv_pdf)
    # The letter PDF was never compiled: report the TeX, never invent a path to a missing file.
    assert artifacts['letter_tex']==str(letter_tex) and 'letter_pdf' not in artifacts
    # The preview is the route that carries them to the client once polling is over.
    assert cv_generator.generation_preview(job)['artifacts']==artifacts


def test_latest_generated_artifacts_is_empty_when_nothing_was_generated(tmp_path, settings):
    from types import SimpleNamespace
    from jobradar.services import cv_generator

    settings.CODEX_CV_WORKSPACE=str(tmp_path)
    (tmp_path/'CVs').mkdir(parents=True)
    (tmp_path/'output').mkdir(parents=True)
    job=SimpleNamespace(id=2, company='Nothing', title='Generated Yet', raw_description='', language_requirements='', source_text='')
    assert cv_generator.latest_generated_artifacts(job,'english')=={}


def test_task_timing_estimate_varies_with_provider_and_model():
    from jobradar.services import cv_tasks

    def generation(provider, model):
        return cv_tasks._task_timing(provider, model, 'medium', 'normal', True, True, False)[1]['generating']

    cloud=generation('openai','gpt-5.5')
    assert generation('ollama','llama3.1:8b') > cloud
    assert generation('lmstudio','qwen2.5-coder') > cloud
    assert generation('anthropic','opus') > generation('anthropic','haiku')
    assert generation('openai','gpt-5.4-mini') < cloud
    # provider and model must reach the estimate itself, not only the empirical-history cache key
    assert generation('ollama','llama3.1:8b') != generation('openai','llama3.1:8b')
    # LaTeX compile is local work -- it must not scale with the model provider
    assert cv_tasks._task_timing('ollama','llama3.1:8b','medium','normal',True,True,False)[1]['compiling_cv'] \
        == cv_tasks._task_timing('openai','gpt-5.5','medium','normal',True,True,False)[1]['compiling_cv']


def test_anthropic_models_expose_real_effort_levels_and_pass_them_to_the_cli(monkeypatch, tmp_path, settings):
    from jobradar.services import cv_generator

    # `claude --help`: "--effort <level>  Effort level for the current session (low, medium, high,
    # xhigh, max)". These were previously hardcoded to ['default'] and never passed to the CLI, so
    # the UI showed a disabled control and every Claude run silently used the default effort.
    monkeypatch.setattr(cv_generator.shutil,'which',lambda command: command if command in ('claude','ollama','lms') else None)
    monkeypatch.setattr(cv_generator,'codex_model_options',lambda:[])
    monkeypatch.setattr(cv_generator.subprocess,'run',lambda *a,**k:(_ for _ in ()).throw(OSError))
    claude_models=[o for o in cv_generator._discover_model_options() if o['provider']=='anthropic']
    assert claude_models, 'claude is on PATH so Anthropic models must be offered'
    for option in claude_models:
        assert option['efforts']==['low','medium','high','xhigh','max']
        assert option['default_effort']=='medium'
        # The CLI exposes no speed/tier flag, so offering "fast" here would be a lie.
        assert option['fast_tier']==''

    # Every level the model advertises must be accepted by the server-side guard.
    for level in cv_generator.CLAUDE_EFFORTS:
        assert cv_generator.validate_model_capability('anthropic','opus',level,'normal')
    with pytest.raises(ValueError):
        cv_generator.validate_model_capability('anthropic','opus','default','normal')


def test_validate_model_capability_accepts_anthropic_normal_speed_and_rejects_its_fast_speed(monkeypatch):
    from jobradar.services import cv_generator

    monkeypatch.setattr(cv_generator, 'available_model_options', lambda: [
        {'provider':'anthropic','key':'sonnet','label':'Claude Sonnet','efforts':['default'],'default_effort':'default','fast_tier':''},
    ])
    accepted=cv_generator.validate_model_capability('anthropic','sonnet','default','normal')
    assert accepted=={'provider':'anthropic','key':'sonnet','label':'Claude Sonnet','efforts':['default'],'default_effort':'default','fast_tier':''}
    with pytest.raises(ValueError, match='Claude Sonnet does not support fast speed'):
        cv_generator.validate_model_capability('anthropic','sonnet','default','fast')


@throttled_rest_framework(cv_generation_user='100/hour')
@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test')
def test_cv_generation_starts_task_for_anthropic_model_but_rejects_its_fast_speed(client, owner, job, monkeypatch):
    from jobradar.services import cv_generator
    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    monkeypatch.setattr(cv_generator, 'available_model_options', lambda: [
        {'provider':'anthropic','key':'sonnet','label':'Claude Sonnet','efforts':['default'],'default_effort':'default','fast_tier':''},
    ])
    started=[]
    monkeypatch.setattr('jobradar.views.start_cv_task', lambda *args,**kwargs: started.append((args,kwargs)) or 'anthropic-task')

    fast=client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'provider':'anthropic','model':'sonnet','effort':'default','speed':'fast'}, format='json')
    assert fast.status_code==400 and 'fast speed' in fast.data['detail']
    assert started==[]  # rejected combos never reach start_cv_task

    normal=client.post(f'/api/jobs/{job.id}/cv-generation/run/', {'provider':'anthropic','model':'sonnet','effort':'default','speed':'normal'}, format='json')
    assert normal.status_code==202 and normal.data['task_id']=='anthropic-task'
    assert len(started)==1
    args,kwargs=started[0]
    assert args[6:10]==('anthropic','sonnet','default','normal') and kwargs=={'create_cv':True}


@pytest.mark.parametrize('stage', ['generating','compiling_cv','compiling_letter'])
def test_remaining_runtime_never_collapses_near_zero_for_active_stages(stage):
    import time
    from jobradar.services import cv_tasks

    cv_tasks._stage_history.clear()
    plan,defaults,estimate_key=cv_tasks._task_timing('openai','gpt-5.5','medium','normal',True,True,False)
    now=time.monotonic()
    expected=defaults[stage]
    # The stage's own budget has just run out (elapsed == expected) but the model call / compile
    # is still the live stage -- the ETA must not be allowed to read ~0 here.
    task={'_stage_plan':[stage],'_stage_key':stage,'_stage_started_at':now-expected,'_estimate_key':estimate_key,'_stage_defaults':defaults}
    assert cv_tasks._remaining_runtime(task, now) >= 2


def test_remaining_runtime_has_a_lower_floor_for_non_active_stages():
    import time
    from jobradar.services import cv_tasks

    cv_tasks._stage_history.clear()
    plan,defaults,estimate_key=cv_tasks._task_timing('openai','gpt-5.5','medium','normal',True,True,False)
    now=time.monotonic()
    expected=defaults['saving']
    task={'_stage_plan':['saving'],'_stage_key':'saving','_stage_started_at':now-expected,'_estimate_key':estimate_key,'_stage_defaults':defaults}
    # 'saving' is not an active (model/compile) stage, so it is allowed to read a smaller floor --
    # this proves the >=2 floor above is specific to active stages, not a blanket minimum.
    assert cv_tasks._remaining_runtime(task, now) < 2


def test_cv_task_step_completed_never_exceeds_step_total_across_cache_collapse(job, monkeypatch):
    import time
    from threading import Event
    from jobradar.services import cv_tasks

    cv_tasks._tasks.clear(); cv_tasks._stage_history.clear()
    monkeypatch.setattr(cv_tasks.JobLead.objects, 'get', lambda id: job)
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: True)
    paused=Event(); resume=Event()

    def generate(job, profile, cv, letter, create_letter, provider, model, effort, speed, progress, *args, **kwargs):
        progress(5,'Preparing templates'); progress(10,'Generating CV')
        paused.set()
        resume.wait(2)
        progress(97,'Using saved package')
        return b'zip','application.zip',{}
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)

    task_id=cv_tasks.start_cv_task(job.id, job.created_by_id, 'profile', 'en', '', False, 'openai', 'gpt-5.5', 'medium', 'normal')
    assert paused.wait(2)
    observed=[]
    for _ in range(5):
        task=cv_tasks.get_cv_task(task_id, job.created_by_id)
        observed.append((task['step_completed'], task['step_total']))
        time.sleep(.01)
    pre_cache_totals={total for _,total in observed}
    resume.set()
    for _ in range(200):
        task=cv_tasks.get_cv_task(task_id, job.created_by_id)
        observed.append((task['step_completed'], task['step_total']))
        if task['status']=='ready': break
        time.sleep(.01)
    assert task['status']=='ready'
    # single-CV, no-letter route: 4 steps until the exact-cache hit collapses the plan to 2.
    assert pre_cache_totals=={4}
    assert observed[-1]==(2,2)
    assert all(completed <= total for completed, total in observed)
    cv_tasks._tasks.clear()


@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test', CODEX_CV_WORKSPACE='C:/missing')
def test_cv_generation_preview_exposes_absolute_template_paths(client, owner, job):
    # The template path sits next to the generated-artifact paths in the UI and is meant to be
    # copied into an editor or file manager, so it is absolute for the same reason they are.
    from pathlib import Path

    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    JobLead.objects.filter(pk=job.pk).update(original_source_text='Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben und die Bewerbung.', raw_description='English role and requirements')
    r=client.get(f'/api/jobs/{job.id}/cv-generation/')
    assert r.status_code==200
    paths={cv['key']:cv['path'] for cv in r.data['cvs']}
    names={cv['key']:cv['filename'] for cv in r.data['cvs']}
    for key, expected in (('en','English - AI Engineer (base)'), ('de','German - AI Engineer (base)')):
        assert Path(paths[key]).is_absolute(), paths[key]
        assert paths[key].startswith(str(Path('C:/missing')))  # the workspace this test overrides to
        assert expected in paths[key] and paths[key].endswith('.tex')
        assert names[key]==Path(paths[key]).name  # filename stays the basename, not the full path


def test_start_cv_revision_inherits_parent_config_without_reverifying_capability(job, monkeypatch):
    from jobradar.services import cv_generator, cv_tasks

    # The parent's stored provider/model/effort/speed combo is genuinely invalid under
    # validate_model_capability (Claude Opus reports fast_tier=''), so if the revision path
    # re-ran that check it would reject this combo outright.
    monkeypatch.setattr(cv_generator, 'available_model_options', lambda: [
        {'provider':'anthropic','key':'opus','label':'Claude Opus','efforts':['default'],'default_effort':'default','fast_tier':''},
    ])
    with pytest.raises(ValueError, match='fast speed'):
        cv_generator.validate_model_capability('anthropic','opus','default','fast')

    cv_tasks._tasks.clear()
    captured=[]
    monkeypatch.setattr(cv_tasks, 'start_cv_task', lambda *args,**kwargs: captured.append((args,kwargs)) or 'child-task-id')
    cv_tasks._tasks['parent-task']={'id':'parent-task','user_id':7,'job_id':job.id,'status':'ready','artifacts':{'cv_tex':'saved-cv.tex','letter_tex':'saved-letter.tex'},'_config':{'profile':'profile text','cv_key':'de','letter_key':'anschreiben','create_letter':True,'create_cv':True,'provider':'anthropic','model':'opus','effort':'default','speed':'fast'}}

    child_id=cv_tasks.start_cv_revision('parent-task', 7, 'Shorten the intro')

    assert child_id=='child-task-id' and len(captured)==1
    args,kwargs=captured[0]
    assert args==(job.id, 7)
    assert kwargs=={'profile':'profile text','cv_key':'de','letter_key':'anschreiben','create_letter':True,'create_cv':True,'provider':'anthropic','model':'opus','effort':'default','speed':'fast','source_cv':'saved-cv.tex','source_letter':'saved-letter.tex','revision_instructions':'Shorten the intro','correction_image':None}
    cv_tasks._tasks.clear()


def test_cv_generation_command_can_be_cancelled(monkeypatch):
    import subprocess
    from jobradar.services import cv_generator

    class Process:
        returncode=None
        killed=False
        def communicate(self, input=None, timeout=None):
            if self.killed:
                return '',''
            raise subprocess.TimeoutExpired(['codex'], timeout)
        def kill(self):
            self.killed=True; self.returncode=-9
    process=Process(); checks=iter([False,False,True])
    monkeypatch.setattr(cv_generator.subprocess, 'Popen', lambda *args,**kwargs: process)
    monkeypatch.setattr(cv_generator, '_stop_process', lambda process: process.kill())
    with pytest.raises(cv_generator.GenerationCancelled):
        cv_generator._run_command(['codex'], lambda: next(checks,True), input='prompt', capture_output=True, text=True, timeout=10)
    assert process.killed


def test_cv_task_can_be_cancelled_without_saving_or_learning(job, monkeypatch):
    import time
    from threading import Event
    from jobradar.services import cv_tasks

    cv_tasks._tasks.clear(); entered=Event(); learned=[]
    monkeypatch.setattr(cv_tasks.JobLead.objects, 'get', lambda id: job)
    monkeypatch.setattr(cv_tasks, '_learn_application_preference', lambda *args: learned.append(args))
    def generate(job, profile, cv, letter, create_letter, provider, model, effort, speed, progress, *args, cancelled=None, **kwargs):
        progress(10,'Generating CV'); entered.set()
        while not cancelled(): time.sleep(.005)
        raise cv_tasks.GenerationCancelled
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)
    task_id=cv_tasks.start_cv_task(job.id, job.created_by_id, 'profile', 'en', '', False, 'openai', 'gpt-5.5', 'medium', 'normal')
    assert entered.wait(1)
    assert cv_tasks.cancel_cv_task(task_id,-1) is None
    assert cv_tasks.cancel_cv_task(task_id,job.created_by_id) is True
    for _ in range(100):
        task=cv_tasks.get_cv_task(task_id,job.created_by_id)
        if task['status']=='cancelled': break
        time.sleep(.01)
    assert task['status']=='cancelled' and task['stage']=='Cancelled' and task['estimated_seconds_remaining']==0
    assert not task['artifacts'] and not learned and cv_tasks.get_cv_task_download(task_id,job.created_by_id) is None
    assert cv_tasks.cancel_cv_task(task_id,job.created_by_id) is False


def test_learned_application_preferences_are_scoped_and_deduplicated(db):
    from jobradar.services.cv_tasks import _learn_application_preference

    user=User.objects.create_user('learning-owner')
    other=User.objects.create_user('learning-other')
    combined=_learn_application_preference(user.id, 'Shorten the profile', True, True)
    _learn_application_preference(user.id, '  Shorten   the profile ', True, True)
    cv=_learn_application_preference(user.id, 'Prefer short bullets', True, False)
    letter=_learn_application_preference(user.id, 'Use a direct opening', False, True)
    assert UserProfile.objects.get(user=user).learned_application_preferences.splitlines()==[combined,cv,letter]
    assert not UserProfile.objects.filter(user=other).exists()


def valid_payload(job):
    return {'evaluations':[{'job_id':job.id,'company':job.company,'title':job.title,'fit_score':90,'priority':'high','recommendation':'apply','summary':'Good','main_match_reasons':['Python'],'main_gaps':['None'],'required_skills':['Python'],'nice_to_have_skills':['Django'],'matched_skills':['Python'],'missing_skills':[],'cv_adjustment_notes':'Tune CV','interview_prep_notes':'Prep','risk_notes':'Low','next_action':'Apply'}]}

def test_import_valid_evaluation(client, job):
    r=client.post('/api/evaluations/import/', {'json':json.dumps(valid_payload(job))}, format='json')
    assert r.status_code==201 and JobEvaluation.objects.count()==1


def test_import_extracts_json_before_chatgpt_citations(client, job):
    payload=valid_payload(job); payload['evaluations'][0]['summary']='Excerpt: "Application Manager Wertpapier".'
    broken=json.dumps(payload).replace('\\"Application Manager Wertpapier\\"','"Application Manager Wertpapier"')
    pasted=f'```json\n{broken}\n```\n\n[1]: https://jobs.example/5768 "Job source"'
    assert client.post('/api/evaluations/import/', {'json':pasted}, format='json').status_code==201
    assert JobEvaluation.objects.get().summary=='Excerpt: "Application Manager Wertpapier".'
    assert client.post('/api/evaluations/import/', {'json':'No JSON here. [1]: https://example.test'}, format='json').status_code==400


def test_smart_skill_statuses_include_profile_aliases(client, job):
    payload=valid_payload(job); payload['evaluations'][0]['required_skills']=['Python 3','SQL','React']; payload['evaluations'][0]['matched_skills']=[]; payload['evaluations'][0]['missing_skills']=['Python 3','SQL','React']
    client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    r=client.get(f'/api/jobs/{job.id}/')
    statuses=r.data['latest_evaluation']['skill_statuses']
    assert statuses['Python 3']['status']=='match' and statuses['Python 3']['display']=='Python'
    assert statuses['SQL']['status']=='match' and statuses['React']['status']=='weak'

def test_reject_invalid_evaluation(client, job):
    r=client.post('/api/evaluations/import/', {'json':'{"evaluations":[{}]}'}, format='json')
    assert r.status_code==400 and JobEvaluation.objects.count()==0

def test_import_job_updates(client, job):
    payload={'job_updates':[{'job_id':job.id,'company':'NewCo','title':'Senior Backend Engineer','location':'Vienna','work_mode':'hybrid','notes':'Extracted manually via ChatGPT'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    job.refresh_from_db()
    assert r.status_code==201 and job.company=='NewCo' and job.title=='Senior Backend Engineer'

def test_import_job_updates_strips_gender_marker_from_title(client, job):
    payload={'job_updates':[{'job_id':job.id,'title':'Senior Backend Engineer (m/f/d)'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    job.refresh_from_db()
    assert r.status_code==201 and job.title=='Senior Backend Engineer'


@override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test', CODEX_CV_WORKSPACE='C:/missing')
def test_chatgpt_import_replaces_link_placeholder_and_detects_language(client, owner):
    owner.email='owner@example.test'; owner.save(update_fields=['email'])
    job=JobLead.objects.create(company='Firma', title='Engineer', raw_description='https://example.test/job', created_by=owner)
    assert job.original_source_text==''
    german='Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben und Anforderungen.'
    payload={'job_updates':[{'job_id':job.id,'raw_description':'Clean summary','original_source_text':german}]}
    assert client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json').status_code==201
    job.refresh_from_db(); assert job.original_source_text==german
    assert client.get(f'/api/jobs/{job.id}/cv-generation/').data['language']=='de'
    replacement={'job_updates':[{'job_id':job.id,'original_source_text':'The full English replacement text and requirements.'}]}
    client.post('/api/evaluations/import/', {'json':json.dumps(replacement)}, format='json')
    job.refresh_from_db(); assert job.original_source_text==german

def test_import_bulk_jobs_with_evaluations(client):
    payload={'jobs':[{'url':'https-www.karriere.at-jobs-7794074','company':'Karriere Co','title':'Python Engineer','location':'Vienna','work_mode':'hybrid','raw_description':'Python Django','evaluation':{'fit_score':82,'priority':'high','recommendation':'apply','summary':'Good fit','main_match_reasons':['Python'],'main_gaps':['Unknown cloud depth'],'required_skills':['Python'],'nice_to_have_skills':['Django'],'matched_skills':['Python'],'missing_skills':[],'cv_adjustment_notes':'Emphasize backend','interview_prep_notes':'APIs','risk_notes':'Low','next_action':'Apply'}}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==201 and JobLead.objects.filter(company='Karriere Co').exists() and JobEvaluation.objects.count()==1
    assert r.data['jobs_found']==1
    assert r.data['imported_jobs'][0]['company']=='Karriere Co'
    assert r.data['imported_jobs'][0]['title']=='Python Engineer'


def test_import_keeps_distinct_job_query_ids(client):
    jobs=[{'url':f'https://jobboerse.strabag.at/job-detail.php?ReqId={job_id}','company':'STRABAG','title':f'Role {job_id}'} for job_id in (571,495,754)]
    response=client.post('/api/evaluations/import/', {'json':json.dumps({'jobs':jobs})}, format='json')
    assert response.status_code==201
    assert JobLead.objects.filter(url__contains='ReqId=').count()==3


def test_original_job_text_is_full_immutable_and_portable(client):
    from jobradar.services.user_data_portability import build_user_export, import_user_export
    original='Full source text. ' * 1000
    UserProfile.objects.create(user=client.user, learned_application_preferences='- [Letter] Use a direct opening')
    payload={'jobs':[{'company':'Snapshot Co','title':'Role','raw_description':'Clean description','original_source_text':original}]}
    assert client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json').status_code==201
    saved=JobLead.objects.get(company='Snapshot Co')
    assert saved.original_source_text==original and len(saved.original_source_text)>12000
    update={'job_updates':[{'job_id':saved.id,'raw_description':'Edited description','original_source_text':'replacement'}]}
    assert client.post('/api/evaluations/import/', {'json':json.dumps(update)}, format='json').status_code==201
    saved.refresh_from_db(); assert saved.raw_description=='Edited description' and saved.original_source_text==original
    exported=build_user_export(client.user)
    assert next(row for row in exported['data']['jobs'] if row['id']==saved.id)['original_source_text']==original
    assert exported['data']['profile'][0]['learned_application_preferences']=='- [Letter] Use a direct opening'
    other=User.objects.create_user('snapshot-importer')
    assert not import_user_export(other, exported)['errors']
    assert JobLead.objects.get(created_by=other).original_source_text==original
    assert UserProfile.objects.get(user=other).learned_application_preferences=='- [Letter] Use a direct opening'

def test_combined_import_existing_evaluation_requires_choice(client, job):
    JobEvaluation.objects.create(job=job, fit_score=70, priority='medium', recommendation='maybe', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    payload={'jobs':[{'job_id':job.id,'company':job.company,'title':job.title,'evaluation':{'fit_score':82,'priority':'high','recommendation':'apply','summary':'Good fit','main_match_reasons':['Python'],'main_gaps':[],'required_skills':['Python'],'nice_to_have_skills':[],'matched_skills':['Python'],'missing_skills':[],'cv_adjustment_notes':'','interview_prep_notes':'','risk_notes':'','next_action':'Apply'}}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==400 and r.data['type']=='evaluation_conflicts'

def test_import_bulk_job_moves_company_url_to_url(client):
    payload={'jobs':[{'company':'https-www.karriere.at-jobs-7794074','title':'Unknown'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    job=JobLead.objects.get(title='Unknown')
    assert r.status_code==201 and job.url=='https://www.karriere.at/jobs/7794074' and job.company=='Unknown company'

def test_bulk_import_duplicate_requires_choice(client):
    make_job(client, company='A', title='T', url='https://dup.test/job')
    payload={'jobs':[{'company':'B','title':'T2','url':'https://dup.test/job'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts'

def test_bulk_import_repeated_position_in_same_payload_is_skipped(client):
    payload={'jobs':[{'company':'A','title':'T'},{'company':'A','title':'T'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==201
    assert JobLead.objects.filter(company='A', title='T').count()==1
    assert r.data['jobs_found']==1
    assert r.data['jobs'][1]['action']=='skipped_duplicate'

def test_bulk_import_existing_position_without_url_requires_choice(client):
    make_job(client, company='A', title='T')
    payload={'jobs':[{'company':'A','title':'T'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts'

def test_bulk_import_duplicate_can_duplicate(client):
    make_job(client, company='A', title='T', url='https://dup.test/job')
    payload={'duplicate_strategy':'duplicate','jobs':[{'company':'B','title':'T','url':'https://dup.test/job'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==201 and JobLead.objects.filter(url='https://dup.test/job').count()==2 and JobLead.objects.filter(title='T (1)').exists()

def test_bulk_import_duplicate_can_override(client):
    existing=make_job(client, company='A', title='T', url='https://dup.test/job')
    payload={'duplicate_strategy':'override','jobs':[{'company':'B','title':'T2','url':'https://dup.test/job'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    existing.refresh_from_db()
    assert r.status_code==201 and existing.company=='B' and existing.title=='T2'

def test_import_bulk_job_cleans_markdown_corrupted_company(client):
    bad='Enlivion](https://www.karriere.at/jobs/10019854%22,%22company%22:%22Enlivion) GmbH'
    payload={'jobs':[{'company':bad,'title':'Software Engineer AI Agent Design & KNX-Integration'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    job=JobLead.objects.get(title='Software Engineer AI Agent Design & KNX-Integration')
    assert r.status_code==201
    assert job.company=='Enlivion GmbH'
    assert job.url=='https://www.karriere.at/jobs/10019854'

def test_export_jobs(client, job): assert client.get('/api/export/jobs.json').status_code==200


def test_application_outcomes_are_ai_exportable(client, job):
    job.status='interview'; job.status_date=timezone.localdate(); job.interview_stage=2; job.interview_total=3; job.save()
    rejected=JobLead.objects.create(company='NoCo', title='Rejected role', status='rejected', status_date=timezone.localdate(), created_by=job.created_by)

    payload=json.loads(client.get('/api/export/jobs.json').content)
    exported={row['id']:row for row in payload}
    assert exported[job.id]['status']=='interview' and exported[job.id]['interview_stage']==2
    assert exported[rejected.id]['status']=='rejected' and exported[rejected.id]['status_date']==str(timezone.localdate())

    csv_export=client.get('/api/export/jobs.csv').content.decode()
    assert 'status_date,interview_stage,interview_total,last_update_date,feedback_due_date' in csv_export
    brief=client.get('/api/export/chatgpt-brief.md').content.decode()
    assert 'status: interview' in brief and 'interview stage: 2/3' in brief and 'status: rejected' in brief


def test_authenticated_user_data_export(client):
    user = User.objects.get(username='owner')
    job = JobLead.objects.create(company='Mine', title='Backend', url='https://mine.test/job', created_by=user)
    JobEvaluation.objects.create(job=job, fit_score=88, priority='high', recommendation='apply', summary='Good', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    ApplicationNote.objects.create(job=job, note='Private note', created_by=user)
    r = client.get('/api/export/')
    assert r.status_code == 200
    assert r.data['schema_version'] == 1
    assert r.data['app'] == 'dachapply'
    assert len(r.data['data']['jobs']) == 1
    assert r.data['data']['jobs'][0]['company'] == 'Mine'
    assert 'password' not in json.dumps(r.data).lower()

def test_staff_export_includes_legacy_unowned_jobs(db):
    staff = User.objects.create_user('staff', password='pw', is_staff=True)
    JobLead.objects.create(company='Legacy', title='Unowned')
    c = APIClient(); c.force_authenticate(staff)
    r = c.get('/api/export/')
    assert r.status_code == 200
    assert 'Legacy' in [j['company'] for j in r.data['data']['jobs']]

def test_regular_export_excludes_legacy_unowned_jobs(db):
    user = User.objects.create_user('regular', password='pw')
    JobLead.objects.create(company='Legacy', title='Unowned')
    c = APIClient(); c.force_authenticate(user)
    r = c.get('/api/export/')
    assert r.status_code == 200
    assert 'Legacy' not in [j['company'] for j in r.data['data']['jobs']]

def test_unauthenticated_user_data_export_blocked(db):
    r = APIClient().get('/api/export/')
    assert r.status_code in (401, 403)

def test_user_data_export_csv_and_xlsx(client):
    user = User.objects.get(username='owner')
    JobLead.objects.create(company='CSV Co', title='Role', created_by=user)
    assert client.get('/api/export/?type=csv').status_code == 200
    r = client.get('/api/export/?type=xlsx')
    assert r.status_code == 200
    assert r['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

def test_import_valid_user_data_file(client):
    payload = {'schema_version': 1, 'app': 'dachapply', 'exported_at': '2026-05-22T00:00:00Z', 'user': {'email': 'old@example.test'}, 'data': {'jobs': [{'id': 500, 'company': 'Imported Co', 'title': 'Imported Role', 'url': 'https://import.test/job', 'work_mode': 'remote', 'status': 'new'}], 'evaluations': [{'id': 600, 'job': 500, 'fit_score': 91, 'priority': 'high', 'recommendation': 'apply', 'summary': 'Strong', 'main_match_reasons': ['Python'], 'main_gaps': [], 'required_skills': ['Python'], 'nice_to_have_skills': [], 'matched_skills': ['Python'], 'missing_skills': []}], 'notes': [{'id': 700, 'job': 500, 'note': 'Remember follow up', 'note_type': 'general'}], 'followups': []}}
    r = client.post('/api/import/', {'json': json.dumps(payload)}, format='json')
    assert r.status_code == 200
    user = User.objects.get(username='owner')
    job = JobLead.objects.get(url='https://import.test/job')
    assert job.created_by == user and job.submitted_for is None
    assert JobEvaluation.objects.filter(job=job, fit_score=91).exists()
    assert ApplicationNote.objects.filter(job=job, created_by=user).exists()
    assert r.data['created']['jobs'] == 1

def test_import_invalid_json(client):
    r = client.post('/api/import/', data='not-json', content_type='application/json')
    assert r.status_code == 400
    assert r.data['errors']

def test_import_returns_preferences_from_full_payload(client):
    payload = {'schema_version': 1, 'app': 'dachapply', 'frontend_preferences': {'work_mode_tones': {'remote': 'green'}}, 'data': {'jobs': [{'id': 910, 'company': 'Pref Co', 'title': 'Role'}], 'evaluations': [], 'notes': [], 'followups': []}}
    r = client.post('/api/import/', {'json': json.dumps(payload)}, format='json')
    assert r.status_code == 200
    assert r.data['frontend_preferences']['work_mode_tones']['remote'] == 'green'
    assert JobLead.objects.filter(company='Pref Co').exists()

def test_import_csv_file(client):
    csv_data = b'id,company,title,url,status\n900,CSV Imported,CSV Role,https://csv.test/job,new\n'
    upload = SimpleUploadedFile('dachapply.csv', csv_data, content_type='text/csv')
    r = client.post('/api/import/', {'file': upload}, format='multipart')
    assert r.status_code == 200
    assert JobLead.objects.filter(company='CSV Imported', created_by__username='owner').exists()

def test_import_conflict_list_for_existing_url(client):
    user = User.objects.get(username='owner')
    JobLead.objects.create(company='Existing', title='Role', url='https://conflict.test/job', created_by=user)
    payload = {'schema_version': 1, 'app': 'dachapply', 'data': {'jobs': [{'id': 901, 'company': 'Incoming', 'title': 'Role', 'url': 'https://conflict.test/job'}], 'evaluations': [], 'notes': [], 'followups': []}}
    r = client.post('/api/import/', {'json': json.dumps(payload)}, format='json')
    assert r.status_code == 400
    assert r.data['type'] == 'import_conflicts'
    assert r.data['conflicts'][0]['kind'] == 'duplicate_url'
    r = client.post('/api/import/', {'json': json.dumps({**payload, 'duplicate_strategy': 'skip'})}, format='json')
    assert r.status_code == 200
    assert r.data['skipped']['jobs'] == 1

def test_import_does_not_overwrite_another_users_data(client, db):
    other = User.objects.create_user('other', password='pw')
    other_job = JobLead.objects.create(id=1234, company='Other Co', title='Secret', url='https://other.test/job', created_by=other)
    payload = {'schema_version': 1, 'app': 'dachapply', 'exported_at': '2026-05-22T00:00:00Z', 'user': {}, 'data': {'jobs': [{'id': other_job.id, 'company': 'Hacked', 'title': 'Changed', 'url': 'https://new.test/job', 'created_by_username': 'other'}], 'evaluations': [], 'notes': [], 'followups': []}}
    r = client.post('/api/import/', {'json': json.dumps(payload)}, format='json')
    assert r.status_code == 200
    other_job.refresh_from_db()
    assert other_job.company == 'Other Co'
    assert JobLead.objects.get(company='Hacked').submitted_by == 'other'
    assert JobLead.objects.filter(company='Hacked', created_by__username='owner').exists()
    exported = client.get('/api/export/').data
    assert 'Other Co' not in json.dumps(exported)

def test_owner_can_explicitly_replace_original_job_text(client, job):
    other=User.objects.create_user('source-other', password='pw')
    other_client=APIClient(); other_client.force_authenticate(other)
    url=f'/api/jobs/{job.id}/source-text/'
    assert other_client.patch(url, {'original_source_text':'Other user text'}, format='json').status_code==404
    assert client.patch(url, {'original_source_text':'https://example.test/job'}, format='json').status_code==400
    text='Manually corrected vollständige deutsche Stellenbeschreibung mit Aufgaben und Anforderungen.'
    assert client.patch(url, {'original_source_text':text}, format='json').status_code==200
    job.refresh_from_db(); assert job.original_source_text==text
    job.raw_description='Later summary'; job.save(); job.refresh_from_db()
    assert job.original_source_text==text


def test_owner_can_edit_job_and_evaluation_text(client, job):
    evaluation=JobEvaluation.objects.create(job=job, fit_score=70, priority='medium', recommendation='maybe', summary='Old', main_match_reasons=['Python'], main_gaps=['Cloud'])
    other=User.objects.create_user('detail-other', password='pw')
    other_client=APIClient(); other_client.force_authenticate(other)
    assert other_client.patch(f'/api/jobs/{job.id}/', {'company':'Changed'}, format='json').status_code==404
    assert other_client.patch(f'/api/evaluations/{evaluation.id}/', {'summary':'Changed'}, format='json').status_code==404
    assert client.patch(f'/api/jobs/{job.id}/', {'company':'New Co', 'location':'Berlin'}, format='json').status_code==200
    response=client.patch(f'/api/evaluations/{evaluation.id}/', {'summary':'Updated summary', 'main_gaps':['Kubernetes','AWS']}, format='json')
    assert response.status_code==200
    job.refresh_from_db(); evaluation.refresh_from_db()
    assert (job.company,job.location)==('New Co','Berlin')
    assert evaluation.summary=='Updated summary' and evaluation.main_gaps==['Kubernetes','AWS']


def test_filtering_jobs(client, job):
    make_job(client, company='Other', title='Java')
    r=client.get('/api/jobs/?search=ACME')
    assert len(r.data)==1

def test_jobs_default_excludes_archived_and_status_filter_allows_multiple(client):
    make_job(client, company='Archived', title='Old', status='archived')
    make_job(client, company='Applied', title='Sent', status='applied')
    make_job(client, company='Interview', title='Call', status='interview')
    r=client.get('/api/jobs/')
    assert 'Archived' not in [x['company'] for x in r.data]
    r=client.get('/api/jobs/?status=applied,interview')
    assert {x['status'] for x in r.data} == {'applied','interview'}
    r=client.get('/api/jobs/?status=archived')
    assert [x['company'] for x in r.data] == ['Archived']

def test_owner_can_restore_archived_job(client):
    archived=make_job(client, company='Archived', title='Restore me', status='archived')
    other=User.objects.create_user('archive-other', password='pw')
    other_client=APIClient(); other_client.force_authenticate(other)
    assert other_client.patch(f'/api/jobs/{archived.id}/', {'status':'new'}, format='json').status_code==404
    r=client.patch(f'/api/jobs/{archived.id}/', {'status':'new'}, format='json')
    archived.refresh_from_db()
    assert r.status_code==200 and archived.status=='new'


def test_delete_archived_job_without_status_filter(client):
    archived=make_job(client, company='Archived', title='Delete me', status='archived')
    active=make_job(client, company='Active', title='Keep me', status='new')
    r=client.delete(f'/api/jobs/{archived.id}/')
    assert r.status_code == 204
    assert not JobLead.objects.filter(id=archived.id).exists()
    r=client.delete(f'/api/jobs/{active.id}/')
    assert r.status_code == 400
    assert JobLead.objects.filter(id=active.id).exists()

def test_jobs_priority_and_recommendation_filters_allow_multiple(client):
    high=make_job(client, company='High', title='A')
    low=make_job(client, company='Low', title='B')
    skip=make_job(client, company='Skip', title='C')
    JobEvaluation.objects.create(job=high, fit_score=90, priority='high', recommendation='apply', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    JobEvaluation.objects.create(job=low, fit_score=50, priority='low', recommendation='maybe', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    JobEvaluation.objects.create(job=skip, fit_score=20, priority='medium', recommendation='skip', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    r=client.get('/api/jobs/?priority=high,low')
    assert {x['company'] for x in r.data} == {'High','Low'}
    r=client.get('/api/jobs/?recommendation=apply,maybe')
    assert {x['company'] for x in r.data} == {'High','Low'}

def test_stats_include_application_pace(client):
    today = timezone.localdate()
    week_start = today - timezone.timedelta(days=today.weekday())
    last_week = week_start - timezone.timedelta(days=1)
    make_job(client, company='Applied', title='This week', status='applied', status_date=today)
    make_job(client, company='Interview', title='Also counts', status='interview', status_date=week_start)
    make_job(client, company='Old', title='Last week', status='applied', status_date=last_week)
    make_job(client, company='Rejected', title='No longer active', status='rejected', status_date=today)
    new_high = make_job(client, company='New high', title='Priority', status='new')
    applied_high = make_job(client, company='Applied high', title='Priority', status='applied')
    for job in [new_high, applied_high]:
        JobEvaluation.objects.create(job=job, fit_score=90, priority='high', recommendation='apply', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    r = client.get('/api/stats/')
    assert r.status_code == 200
    assert r.data['high_priority_jobs'] == 1
    assert r.data['applications_this_week'] == 3
    assert r.data['applications_per_workday'] >= 0
    assert len(r.data['workday_applications']) >= 20
    assert len(r.data['month_week_applications']) >= 4
    assert r.data['month_week_applications'][0]['range'].startswith('1-')
    assert len(r.data['weekly_applications']) == 4
    assert r.data['weekly_applications'][-1]['count'] == 3

def test_default_sort_new_first_then_priority_and_fit(client):
    old=make_job(client, company='Old', title='Applied', status='applied')
    low=make_job(client, company='Low', title='New low', status='new')
    high=make_job(client, company='High', title='New high', status='new')
    JobEvaluation.objects.create(job=old, fit_score=99, priority='high', recommendation='apply', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    JobEvaluation.objects.create(job=low, fit_score=20, priority='low', recommendation='skip', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    JobEvaluation.objects.create(job=high, fit_score=90, priority='high', recommendation='apply', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    r=client.get('/api/jobs/')
    ids=[x['id'] for x in r.data]
    assert ids.index(high.id) < ids.index(low.id) < ids.index(old.id)


def test_user_a_cannot_list_retrieve_update_or_delete_user_b_job(db):
    user_a = User.objects.create_user('a', password='pw')
    user_b = User.objects.create_user('b', password='pw')
    b_job = JobLead.objects.create(company='SecretCo', title='Secret Role', status='archived', created_by=user_b)
    c = APIClient(); c.force_authenticate(user_a)

    r = c.get('/api/jobs/')
    assert b_job.id not in [row['id'] for row in r.data]
    assert c.get(f'/api/jobs/{b_job.id}/').status_code == 404
    assert c.patch(f'/api/jobs/{b_job.id}/', {'company': 'Hacked'}, format='json').status_code == 404
    assert c.delete(f'/api/jobs/{b_job.id}/').status_code == 404
    b_job.refresh_from_db()
    assert b_job.company == 'SecretCo'


def test_user_a_cannot_access_or_mutate_user_b_related_records(db):
    user_a = User.objects.create_user('a', password='pw')
    user_b = User.objects.create_user('b', password='pw')
    b_job = JobLead.objects.create(company='SecretCo', title='Secret Role', created_by=user_b)
    ev = JobEvaluation.objects.create(job=b_job, fit_score=88, priority='high', recommendation='apply', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    note = ApplicationNote.objects.create(job=b_job, note='private', created_by=user_b)
    followup = FollowUp.objects.create(job=b_job, follow_up_date=timezone.localdate(), reason='private')
    c = APIClient(); c.force_authenticate(user_a)

    assert ev.id not in [row['id'] for row in c.get('/api/evaluations/').data]
    assert c.get(f'/api/evaluations/{ev.id}/').status_code == 404
    assert c.delete(f'/api/notes/{note.id}/').status_code == 404
    assert c.patch(f'/api/followups/{followup.id}/', {'completed': True}, format='json').status_code == 404
    followup.refresh_from_db()
    assert followup.completed is False


def test_user_a_exports_do_not_include_user_b_jobs(db):
    user_a = User.objects.create_user('a', password='pw')
    user_b = User.objects.create_user('b', password='pw')
    mine = JobLead.objects.create(company='MineCo', title='Mine', created_by=user_a)
    JobLead.objects.create(company='SecretCo', title='Secret Role', created_by=user_b)
    c = APIClient(); c.force_authenticate(user_a)

    payload = c.get('/api/export/').data
    assert [j['id'] for j in payload['data']['jobs']] == [mine.id]
    assert 'SecretCo' not in json.dumps(payload)
    legacy_json = c.get('/api/export/jobs.json').content.decode()
    assert 'MineCo' in legacy_json and 'SecretCo' not in legacy_json
    legacy_csv = c.get('/api/export/jobs.csv').content.decode()
    assert 'MineCo' in legacy_csv and 'SecretCo' not in legacy_csv
    brief = c.get('/api/export/chatgpt-brief.md').content.decode()
    assert 'MineCo' in brief and 'SecretCo' not in brief


def test_user_a_cannot_prompt_generate_user_b_job(db):
    user_a = User.objects.create_user('a', password='pw')
    user_b = User.objects.create_user('b', password='pw')
    b_job = JobLead.objects.create(company='SecretCo', title='Secret Role', raw_description='secret', created_by=user_b)
    c = APIClient(); c.force_authenticate(user_a)

    assert c.post('/api/prompts/generate/', {'job_ids': [b_job.id]}, format='json').status_code == 400
    assert c.post('/api/prompts/combined/', {'job_ids': [b_job.id]}, format='json').status_code == 400
    assert c.post('/api/prompts/enrich/', {'job_ids': [b_job.id]}, format='json').status_code == 400


def test_user_a_cannot_import_eval_or_update_for_user_b_job(db):
    user_a = User.objects.create_user('a', password='pw')
    user_b = User.objects.create_user('b', password='pw')
    b_job = JobLead.objects.create(company='SecretCo', title='Secret Role', created_by=user_b)
    c = APIClient(); c.force_authenticate(user_a)

    r = c.post('/api/evaluations/import/', {'json': json.dumps(valid_payload(b_job))}, format='json')
    assert r.status_code == 400
    assert JobEvaluation.objects.count() == 0

    payload = {'job_updates': [{'job_id': b_job.id, 'company': 'Hacked', 'title': 'Changed'}]}
    r = c.post('/api/evaluations/import/', {'json': json.dumps(payload)}, format='json')
    assert r.status_code == 400
    b_job.refresh_from_db()
    assert b_job.company == 'SecretCo'


def test_user_a_user_data_import_does_not_overwrite_user_b_job(db):
    user_a = User.objects.create_user('a', password='pw')
    user_b = User.objects.create_user('b', password='pw')
    b_job = JobLead.objects.create(company='SecretCo', title='Secret Role', url='https://secret.test/job', created_by=user_b)
    c = APIClient(); c.force_authenticate(user_a)
    payload = {'schema_version': 1, 'app': 'dachapply', 'data': {'jobs': [{'id': b_job.id, 'company': 'Incoming', 'title': 'Mine now', 'url': 'https://mine-new.test/job'}], 'evaluations': [], 'notes': [], 'followups': []}}

    r = c.post('/api/import/', {'json': json.dumps(payload)}, format='json')
    assert r.status_code == 200
    b_job.refresh_from_db()
    assert b_job.company == 'SecretCo'
    assert JobLead.objects.filter(company='Incoming', created_by=user_a).exists()


def test_approved_friend_submitter_flow_remains_accessible_to_owner_and_submitter(db):
    owner = User.objects.create_user('owner2', password='pw')
    friend = User.objects.create_user('friend', password='pw')
    stranger = User.objects.create_user('stranger', password='pw')
    UserProfile.objects.create(user=friend, submit_for=owner)
    friend_client = APIClient(); friend_client.force_authenticate(friend)

    r = friend_client.post('/api/public/submit/', {'company': 'FriendCo', 'title': 'Referral', 'url': 'https://friend.test/job'}, format='json')
    assert r.status_code == 201
    job = JobLead.objects.get(url='https://friend.test/job')
    assert job.created_by == friend and job.submitted_for == owner and job.source == 'friend'

    owner_client = APIClient(); owner_client.force_authenticate(owner)
    assert job.id in [row['id'] for row in owner_client.get('/api/jobs/').data]
    assert job.id in [row['id'] for row in friend_client.get('/api/jobs/').data]
    stranger_client = APIClient(); stranger_client.force_authenticate(stranger)
    assert job.id not in [row['id'] for row in stranger_client.get('/api/jobs/').data]


def test_user_a_cannot_create_or_update_job_into_user_b_dashboard(db):
    user_a = User.objects.create_user('a', password='pw')
    user_b = User.objects.create_user('b', password='pw')
    c = APIClient(); c.force_authenticate(user_a)

    r = c.post('/api/jobs/', {'company': 'Injected', 'title': 'Role', 'submitted_for': user_b.id}, format='json')
    assert r.status_code == 201
    job = JobLead.objects.get(id=r.data['id'])
    assert job.created_by == user_a and job.submitted_for is None

    r = c.patch(f'/api/jobs/{job.id}/', {'submitted_for': user_b.id}, format='json')
    assert r.status_code == 200
    job.refresh_from_db()
    assert job.submitted_for is None

    b_client = APIClient(); b_client.force_authenticate(user_b)
    assert job.id not in [row['id'] for row in b_client.get('/api/jobs/').data]


def test_candidate_profile_settings_can_be_saved_and_loaded(client):
    payload = {
        'candidate_profile': 'Senior data engineer in Berlin with Go and Rust.',
        'target_roles': 'Data Engineer\nBackend Engineer',
        'preferred_locations': 'Berlin, remote Germany',
        'salary_expectations': '90k EUR+',
        'language_levels': 'English C2, German B1',
        'preferred_stack': 'Go, Rust, Kafka, Postgres',
        'red_flags': 'No unpaid overtime',
        'selling_points': 'Distributed systems and mentoring',
        'learned_application_preferences': '- [CV] Keep the profile concise',
    }
    r = client.patch('/api/profile/', payload, format='json')
    assert r.status_code == 200
    assert r.data['preferred_stack'] == 'Go, Rust, Kafka, Postgres'

    r = client.get('/api/profile/')
    assert r.status_code == 200
    for key, value in payload.items():
        assert r.data[key] == value


def test_prompt_generation_uses_current_users_candidate_profile(db):
    user_a = User.objects.create_user('profile-a', password='pw')
    user_b = User.objects.create_user('profile-b', password='pw')
    job_a = JobLead.objects.create(company='A Co', title='Data Engineer', raw_description='Kafka pipelines', created_by=user_a)
    job_b = JobLead.objects.create(company='B Co', title='Frontend Engineer', raw_description='React UI', created_by=user_b)
    UserProfile.objects.create(user=user_a, candidate_profile='A_PROFILE_UNIQUE Kafka Go Berlin', preferred_stack='Go Kafka')
    UserProfile.objects.create(user=user_b, candidate_profile='B_PROFILE_UNIQUE React Lisbon', preferred_stack='React TypeScript')

    c = APIClient(); c.force_authenticate(user_a)
    r = c.post('/api/prompts/generate/', {'job_ids': [job_a.id]}, format='json')
    assert r.status_code == 200
    assert 'A_PROFILE_UNIQUE Kafka Go Berlin' in r.data['generated_prompt']
    assert 'Go Kafka' in r.data['generated_prompt']
    assert 'B_PROFILE_UNIQUE' not in r.data['generated_prompt']
    assert 'React TypeScript' not in r.data['generated_prompt']
    assert f'Job ID: {job_b.id}' not in r.data['generated_prompt']


def test_bulk_links_prompt_uses_current_users_candidate_profile(db):
    user = User.objects.create_user('profile-links', password='pw')
    UserProfile.objects.create(user=user, candidate_profile='LINKS_PROFILE_UNIQUE AI search', target_roles='AI Search Engineer')
    c = APIClient(); c.force_authenticate(user)

    r = c.post('/api/prompts/bulk-links/', {'links': 'https://example.test/job'}, format='json')
    assert r.status_code == 200
    assert 'LINKS_PROFILE_UNIQUE AI search' in r.data['generated_prompt']
    assert 'AI Search Engineer' in r.data['generated_prompt']


def test_prompt_template_from_profile_page_is_used(client, job):
    template = 'CUSTOM COMBINED TEMPLATE\nPROFILE={candidate_profile}\nSCHEMA={schema}\nJOBS={jobs}'
    r = client.patch('/api/profile/', {'candidate_profile': 'PROFILE_FROM_SETTINGS', 'combined_prompt_template': template}, format='json')
    assert r.status_code == 200
    assert r.data['combined_prompt_template'] == template

    r = client.post('/api/prompts/combined/', {'job_ids': [job.id]}, format='json')
    assert r.status_code == 200
    prompt = r.data['generated_prompt']
    assert prompt.startswith('CUSTOM COMBINED TEMPLATE')
    assert 'PROFILE=Candidate profile:\nPROFILE_FROM_SETTINGS' in prompt
    assert f'Job ID: {job.id}' in prompt
    assert '"jobs"' in prompt


def test_demo_login_creates_rich_demo_dashboard(db):
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': 'demo@dachapply.com', 'password': 'DemoApply2026!'}, format='json')
    assert r.status_code == 200
    demo = User.objects.get(username='demo@dachapply.com')
    jobs = JobLead.objects.filter(Q(created_by=demo) | Q(submitted_for=demo)).distinct()
    assert jobs.count() >= 9
    assert jobs.filter(status='interview').count() >= 4
    assert jobs.filter(submitted_for=demo, source='friend').count() >= 3
    anna_job=jobs.get(url='https://demo.dachapply.local/referrals/green-energy-analytics')
    assert anna_job.created_by.username=='anna.referrer@example.com' and anna_job.submitted_for==demo
    from jobradar.serializers import JobLeadSerializer
    assert JobLeadSerializer(anna_job).data['created_by_email']=='anna.referrer@example.com'
    assert not JobLead.objects.filter(url__startswith='https://demo.dachapply.local/', created_by__isnull=False).exclude(Q(created_by=demo)|Q(submitted_for=demo)).exists()
    assert UserProfile.objects.filter(requested_submit_for=demo, submit_for__isnull=True).exists()
    assert JobEvaluation.objects.filter(job__in=jobs).count() >= jobs.count()
    assert FollowUp.objects.filter(job__in=jobs).exists()


def test_demo_seed_removes_demo_jobs_from_other_accounts(db):
    from jobradar.services.demo_data import ensure_demo_user

    other = User.objects.create_user('ermis.chorinopoulos@gmail.com')
    JobLead.objects.create(company='Leaked Demo', title='Leak', url='https://demo.dachapply.local/jobs/leak', source='demo', created_by=other)
    JobLead.objects.create(company='Dynatrace', title='Python Backend Engineer', url='https://example.com/jobs/dynatrace', source='seed', created_by=other)

    demo, _jobs = ensure_demo_user()

    assert not JobLead.objects.filter(created_by=other, url__startswith='https://demo.dachapply.local/').exists()
    assert not JobLead.objects.filter(created_by=other, url='https://example.com/jobs/dynatrace', source='seed').exists()
    demo_jobs=JobLead.objects.filter(Q(created_by=demo)|Q(submitted_for=demo), url__startswith='https://demo.dachapply.local/').distinct()
    assert demo_jobs.count() >= 9
    assert not JobLead.objects.filter(url__startswith='https://demo.dachapply.local/', created_by__isnull=False).exclude(Q(created_by=demo)|Q(submitted_for=demo)).exists()


def test_regular_user_can_archive_owned_leaked_demo_job(client):
    job = make_job(client, company='Leaked Demo', title='Leak', url='https://demo.dachapply.local/jobs/leak', source='demo')

    r = client.patch(f'/api/jobs/{job.id}/', {'status': 'archived'}, format='json')

    assert r.status_code == 200
    job.refresh_from_db()
    assert job.status == 'archived'


def test_regular_user_cannot_create_demo_jobs(client):
    payload = {'company': 'Demo', 'title': 'Demo role', 'url': 'https://demo.dachapply.local/jobs/python-backend', 'source': 'demo'}

    r = client.post('/api/jobs/', payload, format='json')

    assert r.status_code == 400
    assert not JobLead.objects.filter(created_by=client.user, source='demo').exists()

    job = make_job(client, company='Normal', title='Role')
    r = client.patch(f'/api/jobs/{job.id}/', payload, format='json')
    assert r.status_code == 400

    r = client.post('/api/evaluations/import/', {'json': json.dumps({'jobs': [payload]})}, format='json')

    assert r.status_code == 400
    assert 'demo jobs are only available in the demo account' in str(r.data).lower()
    assert not JobLead.objects.filter(created_by=client.user, url__startswith='https://demo.dachapply.local/').exists()


def test_admin_user_changelist_shows_demo_users_separately(db):
    from jobradar.services.demo_data import ensure_demo_user

    ensure_demo_user()
    User.objects.create_user('real-admin-visible@example.test', email='real-admin-visible@example.test')
    User.objects.create_superuser('admin@example.test', email='admin@example.test', password='secret123')
    c = Client()
    c.post('/admin/login/', {'username': 'admin@example.test', 'password': 'secret123', 'next': '/admin/auth/user/'})

    r = c.get('/admin/auth/user/')

    assert r.status_code == 200
    html = r.content.decode()
    main_users_html = html.split('id="demo-users-table"', 1)[0]
    assert 'Demo users' in html
    assert 'real-admin-visible@example.test' in main_users_html
    assert 'demo@dachapply.com' not in main_users_html
    assert 'demo@dachapply.com' in html
    assert 'anna.referrer@example.com' in html
    assert '/admin/auth/user/' in html


def test_demo_login_tracks_unique_visitor_and_demo_click(db):
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': 'demo@dachapply.com', 'password': 'DemoApply2026!'}, format='json')
    assert r.status_code == 200
    assert SiteVisitor.objects.count() == 1
    visitor = SiteVisitor.objects.get()
    assert visitor.request_count == 1
    assert visitor.had_anonymous is True
    assert visitor.had_authenticated is False
    assert visitor.demo_click_count == 1
    assert VisitorDailyUsage.objects.filter(visitor=visitor, request_count=1, demo_click_count=1, had_anonymous=True, had_authenticated=False).exists()
    assert not UserDailyUsage.objects.filter(user__username='demo@dachapply.com').exists()
    daily = SiteDailyUsage.objects.get(date=timezone.localdate())
    assert daily.unique_visitor_count == 1
    assert daily.authenticated_count == 0
    assert daily.anonymous_count == 1
    assert daily.demo_click_count == 1
    assert daily.demo_unique_visitor_count == 1


def test_same_visitor_collects_authenticated_anonymous_and_demo_flags(db):
    user = User.objects.create_user('flag-user@example.test', email='flag-user@example.test', password='secret123')
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': user.username, 'password': 'secret123'}, format='json')
    assert r.status_code == 200
    r = c.post('/api/auth/logout/', {}, format='json')
    assert r.status_code == 200
    r = c.post('/api/auth/login/', {'username': 'demo@dachapply.com', 'password': 'DemoApply2026!'}, format='json')
    assert r.status_code == 200

    assert SiteVisitor.objects.count() == 1
    visitor = SiteVisitor.objects.get()
    assert visitor.had_authenticated is True
    assert visitor.had_anonymous is True
    assert visitor.demo_click_count == 1
    daily = VisitorDailyUsage.objects.get(visitor=visitor, date=timezone.localdate())
    assert daily.had_authenticated is True
    assert daily.had_anonymous is True
    assert daily.demo_click_count == 1


def test_login_rate_limit_returns_429(db):
    User.objects.create_user('limit-login@example.test', email='limit-login@example.test', password='correct-password')
    c = APIClient()
    with throttled_rest_framework(login_ip='2/minute', login_account='2/minute'):
        cache.clear()
        for _ in range(2):
            r = c.post('/api/auth/login/', {'username': 'limit-login@example.test', 'password': 'wrong'}, format='json')
            assert r.status_code == 400
        assert_rate_limited(c.post('/api/auth/login/', {'username': 'limit-login@example.test', 'password': 'wrong'}, format='json'))


def test_register_rate_limit_returns_429(db):
    c = APIClient()
    with throttled_rest_framework(register_ip='1/minute'):
        cache.clear()
        r = c.post('/api/auth/register/', {'email': 'register-limit-1@example.test', 'password': 'secret1'}, format='json')
        assert r.status_code == 201
        assert_rate_limited(c.post('/api/auth/register/', {'email': 'register-limit-2@example.test', 'password': 'secret2'}, format='json'))


def test_password_reset_request_rate_limit_returns_429(db):
    User.objects.create_user('reset-limit@example.test', email='reset-limit@example.test', password='pw')
    c = APIClient()
    with throttled_rest_framework(password_reset_ip='1/minute', password_reset_email='10/minute'):
        cache.clear()
        r = c.post('/api/auth/password-reset/', {'email': 'reset-limit@example.test'}, format='json')
        assert r.status_code == 200
        assert_rate_limited(c.post('/api/auth/password-reset/', {'email': 'other-reset-limit@example.test'}, format='json'))


def test_public_submit_rate_limit_returns_429(db):
    InviteCode.objects.create(code='RATE-LIMIT')
    c = APIClient()
    with throttled_rest_framework(public_submit_ip='1/minute'):
        cache.clear()
        r = c.post('/api/public/submit/', {'invite_code': 'RATE-LIMIT', 'company': 'C', 'title': 'T', 'url': 'https://rate-limit.test/1'}, format='json')
        assert r.status_code == 201
        assert_rate_limited(c.post('/api/public/submit/', {'invite_code': 'RATE-LIMIT', 'company': 'C2', 'title': 'T2', 'url': 'https://rate-limit.test/2'}, format='json'))


def test_import_endpoint_rate_limit_returns_429(client):
    with throttled_rest_framework(import_user='1/minute'):
        cache.clear()
        r = client.post('/api/evaluations/import/', {'json': '{"evaluations":[{}]}'}, format='json')
        assert r.status_code == 400
        assert_rate_limited(client.post('/api/evaluations/import/', {'json': '{"evaluations":[{}]}'}, format='json'))


def test_user_data_import_rate_limit_returns_429(client):
    with throttled_rest_framework(import_user='1/minute'):
        cache.clear()
        r = client.post('/api/import/', data='not-json', content_type='application/json')
        assert r.status_code == 400
        assert_rate_limited(client.post('/api/import/', data='not-json', content_type='application/json'))


def test_account_deletion_deletes_current_user_data_and_account(db):
    user = User.objects.create_user('delete-me@example.test', email='delete-me@example.test', password='secretpw')
    other = User.objects.create_user('keep-me@example.test', password='pw')
    UserProfile.objects.create(user=user, candidate_profile='DELETE_PROFILE')
    job = JobLead.objects.create(company='DeleteCo', title='Delete Role', created_by=user)
    JobEvaluation.objects.create(job=job, fit_score=80, priority='high', recommendation='apply', summary='delete', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    ApplicationNote.objects.create(job=job, note='delete note', created_by=user)
    FollowUp.objects.create(job=job, follow_up_date=timezone.localdate(), reason='delete followup')
    other_job = JobLead.objects.create(company='KeepCo', title='Keep Role', created_by=other)

    c = APIClient(); c.force_authenticate(user)
    r = c.delete('/api/auth/account/', {'password': 'wrong'}, format='json')
    assert r.status_code == 400
    assert User.objects.filter(username='delete-me@example.test').exists()

    r = c.delete('/api/auth/account/', {'password': 'secretpw'}, format='json')
    assert r.status_code == 200
    assert r.data['deleted']['jobs'] == 1
    assert not User.objects.filter(username='delete-me@example.test').exists()
    assert not UserProfile.objects.filter(candidate_profile='DELETE_PROFILE').exists()
    assert not JobLead.objects.filter(company='DeleteCo').exists()
    assert not JobEvaluation.objects.filter(summary='delete').exists()
    assert not ApplicationNote.objects.filter(note='delete note').exists()
    assert not FollowUp.objects.filter(reason='delete followup').exists()
    assert JobLead.objects.filter(id=other_job.id, company='KeepCo').exists()


def test_export_before_account_delete_contains_user_data_then_delete_removes_it(db):
    user = User.objects.create_user('export-delete@example.test', email='export-delete@example.test', password='secretpw')
    UserProfile.objects.create(user=user, candidate_profile='EXPORT_DELETE_PROFILE')
    job = JobLead.objects.create(company='ExportDeleteCo', title='Role', url='https://export-delete.test/job', created_by=user)
    JobEvaluation.objects.create(job=job, fit_score=92, priority='high', recommendation='apply', summary='export delete eval', main_match_reasons=['Python'], main_gaps=[], required_skills=['Python'], nice_to_have_skills=[], matched_skills=['Python'], missing_skills=[])
    ApplicationNote.objects.create(job=job, note='export delete note', created_by=user)
    FollowUp.objects.create(job=job, follow_up_date=timezone.localdate(), reason='export delete followup')

    c = APIClient(); c.force_authenticate(user)
    exported = c.get('/api/export/')
    assert exported.status_code == 200
    assert exported.data['data']['profile'][0]['candidate_profile'] == 'EXPORT_DELETE_PROFILE'
    assert exported.data['data']['jobs'][0]['company'] == 'ExportDeleteCo'
    assert exported.data['data']['evaluations'][0]['summary'] == 'export delete eval'
    assert exported.data['data']['notes'][0]['note'] == 'export delete note'
    assert exported.data['data']['followups'][0]['reason'] == 'export delete followup'

    r = c.delete('/api/auth/account/', {'password': 'secretpw'}, format='json')
    assert r.status_code == 200
    assert not User.objects.filter(username='export-delete@example.test').exists()
    assert not JobLead.objects.filter(company='ExportDeleteCo').exists()
