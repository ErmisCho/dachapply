import json
import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from jobradar.models import InviteCode, JobLead, JobEvaluation, ApplicationNote

@pytest.fixture
def client(db):
    u=User.objects.create_user('owner', password='pw')
    c=APIClient(); c.force_authenticate(u); return c

@pytest.fixture
def job(db): return JobLead.objects.create(company='ACME', title='Python Engineer', raw_description='Python Django SQL')

def test_create_job(client):
    r=client.post('/api/jobs/', {'company':'X','title':'Backend','url':'https://x.test'}, format='json')
    assert r.status_code==201 and r.data['company']=='X'

def test_create_url_only_job(client):
    r=client.post('/api/jobs/', {'url':'https://x.test/job'}, format='json')
    assert r.status_code==201 and r.data['company']=='Unknown company' and r.data['title']=='Untitled role'

def test_manual_duplicate_job_requires_choice(client):
    JobLead.objects.create(company='A', title='T', url='https://manual.test/job')
    r=client.post('/api/jobs/', {'company':'B','title':'T2','url':'https://manual.test/job'}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts'

def test_manual_duplicate_job_detects_trailing_slash_and_query(client):
    JobLead.objects.create(company='A', title='T', url='https://manual.test/job')
    r=client.post('/api/jobs/', {'company':'B','title':'T2','url':'https://manual.test/job/?utm=x'}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts'

def test_manual_duplicate_job_can_duplicate(client):
    JobLead.objects.create(company='A', title='T', url='https://manual.test/job')
    r=client.post('/api/jobs/', {'company':'B','title':'T','url':'https://manual.test/job','duplicate_action':'duplicate'}, format='json')
    assert r.status_code==201 and r.data['title']=='T (1)'

def test_bulk_create_multiple_links_from_notes(client):
    r=client.post('/api/jobs/bulk-create/', {'raw_description':'https://a.test/job1\nhttps://b.test/job2'}, format='json')
    assert r.status_code==201 and r.data['count']==2 and JobLead.objects.filter(url__in=['https://a.test/job1','https://b.test/job2']).count()==2

def test_bulk_create_duplicate_requires_choice(client):
    JobLead.objects.create(company='A', title='T', url='https://a.test/job1')
    r=client.post('/api/jobs/bulk-create/', {'url':'https://a.test/job1\nhttps://b.test/job2'}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts' and JobLead.objects.filter(url='https://b.test/job2').count()==0

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

def test_import_bulk_jobs_with_evaluations(client):
    payload={'jobs':[{'url':'https-www.karriere.at-jobs-7794074','company':'Karriere Co','title':'Python Engineer','location':'Vienna','work_mode':'hybrid','raw_description':'Python Django','evaluation':{'fit_score':82,'priority':'high','recommendation':'apply','summary':'Good fit','main_match_reasons':['Python'],'main_gaps':['Unknown cloud depth'],'required_skills':['Python'],'nice_to_have_skills':['Django'],'matched_skills':['Python'],'missing_skills':[],'cv_adjustment_notes':'Emphasize backend','interview_prep_notes':'APIs','risk_notes':'Low','next_action':'Apply'}}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==201 and JobLead.objects.filter(company='Karriere Co').exists() and JobEvaluation.objects.count()==1

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
    JobLead.objects.create(company='A', title='T', url='https://dup.test/job')
    payload={'jobs':[{'company':'B','title':'T2','url':'https://dup.test/job'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==400 and r.data['type']=='duplicate_conflicts'

def test_bulk_import_duplicate_can_duplicate(client):
    JobLead.objects.create(company='A', title='T', url='https://dup.test/job')
    payload={'duplicate_strategy':'duplicate','jobs':[{'company':'B','title':'T','url':'https://dup.test/job'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    assert r.status_code==201 and JobLead.objects.filter(url='https://dup.test/job').count()==2 and JobLead.objects.filter(title='T (1)').exists()

def test_bulk_import_duplicate_can_override(client):
    existing=JobLead.objects.create(company='A', title='T', url='https://dup.test/job')
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
    JobLead.objects.create(company='Other', title='Java')
    r=client.get('/api/jobs/?search=ACME')
    assert len(r.data)==1

def test_default_sort_new_first_then_priority_and_fit(client):
    old=JobLead.objects.create(company='Old', title='Applied', status='applied')
    low=JobLead.objects.create(company='Low', title='New low', status='new')
    high=JobLead.objects.create(company='High', title='New high', status='new')
    JobEvaluation.objects.create(job=old, fit_score=99, priority='high', recommendation='apply', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    JobEvaluation.objects.create(job=low, fit_score=20, priority='low', recommendation='skip', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    JobEvaluation.objects.create(job=high, fit_score=90, priority='high', recommendation='apply', summary='', main_match_reasons=[], main_gaps=[], required_skills=[], nice_to_have_skills=[], matched_skills=[], missing_skills=[])
    r=client.get('/api/jobs/')
    ids=[x['id'] for x in r.data]
    assert ids.index(high.id) < ids.index(low.id) < ids.index(old.id)
