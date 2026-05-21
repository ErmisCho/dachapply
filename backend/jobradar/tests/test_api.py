import json
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from jobradar.models import InviteCode, JobLead, JobEvaluation

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

def test_normalizes_pasted_hyphen_url(client):
    r=client.post('/api/jobs/', {'url':'https-www.karriere.at-jobs-7794074'}, format='json')
    assert r.status_code==201 and r.data['url']=='https://www.karriere.at/jobs/7794074'

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

def test_generate_prompt(client, job):
    r=client.post('/api/prompts/generate/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'CANDIDATE PROFILE' in r.data['generated_prompt']

def test_generate_enrichment_prompt(client, job):
    r=client.post('/api/prompts/enrich/', {'job_ids':[job.id]}, format='json')
    assert r.status_code==200 and 'job_updates' in r.data['generated_prompt']

def test_generate_bulk_links_prompt(client):
    r=client.post('/api/prompts/bulk-links/', {'links':'https-www.karriere.at-jobs-7794074\nhttps://example.com/job'}, format='json')
    assert r.status_code==200 and 'EXPECTED JSON SCHEMA' in r.data['generated_prompt'] and 'evaluation' in r.data['generated_prompt']

def valid_payload(job):
    return {'evaluations':[{'job_id':job.id,'company':job.company,'title':job.title,'fit_score':90,'priority':'high','recommendation':'apply','summary':'Good','main_match_reasons':['Python'],'main_gaps':['None'],'required_skills':['Python'],'nice_to_have_skills':['Django'],'matched_skills':['Python'],'missing_skills':[],'cv_adjustment_notes':'Tune CV','interview_prep_notes':'Prep','risk_notes':'Low','next_action':'Apply'}]}

def test_import_valid_evaluation(client, job):
    r=client.post('/api/evaluations/import/', {'json':json.dumps(valid_payload(job))}, format='json')
    assert r.status_code==201 and JobEvaluation.objects.count()==1

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

def test_import_bulk_job_moves_company_url_to_url(client):
    payload={'jobs':[{'company':'https-www.karriere.at-jobs-7794074','title':'Unknown'}]}
    r=client.post('/api/evaluations/import/', {'json':json.dumps(payload)}, format='json')
    job=JobLead.objects.get(title='Unknown')
    assert r.status_code==201 and job.url=='https://www.karriere.at/jobs/7794074' and job.company=='Unknown company'

def test_export_jobs(client, job): assert client.get('/api/export/jobs.json').status_code==200

def test_filtering_jobs(client, job):
    JobLead.objects.create(company='Other', title='Java')
    r=client.get('/api/jobs/?search=ACME')
    assert len(r.data)==1
