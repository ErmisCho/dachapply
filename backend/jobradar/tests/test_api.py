import json
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from jobradar.models import InviteCode, JobLead, JobEvaluation, ApplicationNote, FollowUp, UserProfile


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

def test_update_job_status(client, job):
    r=client.patch(f'/api/jobs/{job.id}/', {'status':'to_apply'}, format='json')
    assert r.status_code==200 and r.data['status']=='to_apply'

def test_applied_status_sets_status_date(client, job):
    r=client.patch(f'/api/jobs/{job.id}/', {'status':'applied'}, format='json')
    assert r.status_code==200 and r.data['status_date'] is not None

def test_can_override_status_date(client, job):
    r=client.patch(f'/api/jobs/{job.id}/', {'status':'interview','status_date':'2026-01-02'}, format='json')
    assert r.status_code==200 and r.data['status_date']=='2026-01-02'

def test_generate_prompt(client, job):
    r=client.post('/api/prompts/generate/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'CANDIDATE PROFILE' in r.data['generated_prompt']

def test_generate_enrichment_prompt(client, job):
    r=client.post('/api/prompts/enrich/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'job_updates' in r.data['generated_prompt']

def test_generate_combined_prompt(client, job):
    r=client.post('/api/prompts/combined/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'evaluation' in r.data['generated_prompt'] and 'job_id' in r.data['generated_prompt']

def test_generate_bulk_links_prompt(client):
    r=client.post('/api/prompts/bulk-links/', {'links':'https-www.karriere.at-jobs-7794074\nhttps://example.com/job'}, format='json')
    assert r.status_code==200 and 'EXPECTED JSON SCHEMA' in r.data['generated_prompt'] and 'evaluation' in r.data['generated_prompt']

def valid_payload(job):
    return {'evaluations':[{'job_id':job.id,'company':job.company,'title':job.title,'fit_score':90,'priority':'high','recommendation':'apply','summary':'Good','main_match_reasons':['Python'],'main_gaps':['None'],'required_skills':['Python'],'nice_to_have_skills':['Django'],'matched_skills':['Python'],'missing_skills':[],'cv_adjustment_notes':'Tune CV','interview_prep_notes':'Prep','risk_notes':'Low','next_action':'Apply'}]}

def test_import_valid_evaluation(client, job):
    r=client.post('/api/evaluations/import/', {'json':json.dumps(valid_payload(job))}, format='json')
    assert r.status_code==201 and JobEvaluation.objects.count()==1

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

def test_import_bulk_jobs_with_evaluations(client):
    payload={'jobs':[{'url':'https-www.karriere.at-jobs-7794074','company':'Karriere Co','title':'Python Engineer','location':'Vienna','work_mode':'hybrid','raw_description':'Python Django','evaluation':{'fit_score':82,'priority':'high','recommendation':'apply','summary':'Good fit','main_match_reasons':['Python'],'main_gaps':['Unknown cloud depth'],'required_skills':['Python'],'nice_to_have_skills':['Django'],'matched_skills':['Python'],'missing_skills':[],'cv_adjustment_notes':'Emphasize backend','interview_prep_notes':'APIs','risk_notes':'Low','next_action':'Apply'}}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==201 and JobLead.objects.filter(company='Karriere Co').exists() and JobEvaluation.objects.count()==1
    assert r.data['jobs_found']==1
    assert r.data['imported_jobs'][0]['company']=='Karriere Co'
    assert r.data['imported_jobs'][0]['title']=='Python Engineer'

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
    assert UserProfile.objects.filter(requested_submit_for=demo, submit_for__isnull=True).exists()
    assert JobEvaluation.objects.filter(job__in=jobs).count() >= jobs.count()
    assert FollowUp.objects.filter(job__in=jobs).exists()


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
