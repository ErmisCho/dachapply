"""TASK-280.1: application language and document requirements -- the model classifies, the app checks evidence."""
import pytest
from django.contrib.auth.models import User

from jobradar.models import JobLead
from jobradar.services.application_requirements import normalize_application_requirements
from jobradar.services.json_importer import import_jobs_data
from jobradar.services.prompt_builder import (APPLICATION_REQUIREMENTS_RULES, BULK_LINKS_SCHEMA, COMBINED_SCHEMA, ENRICHMENT_SCHEMA,
                                              build_bulk_links_prompt, build_combined_prompt, build_enrichment_prompt)
from jobradar.services.user_data_portability import build_user_export, import_user_export

EN_REQUIRED = '''Overview: Backend engineer for our payments platform in Vienna.
Required experience
- 3+ years of Python and Django
Other details (benefits, application process)
Please send your CV together with a   cover letter
explaining why you want to join us.'''
EN_NOT_WANTED = '''Overview: Platform engineer, remote within Austria.
Other details (benefits, application process)
Apply with your CV only. Please do not send a cover letter.'''
DE_NO_LETTER = '''Überblick: Backend-Entwickler (m/w/d) in Graz.
Anforderungen
- Erfahrung mit Python
Sonstiges (Bewerbung)
Kein Anschreiben erforderlich – ein kurzer Lebenslauf genügt.'''
DE_SILENT = '''Überblick: Softwareentwickler (m/w/d) in Linz.
Anforderungen
- Gute Kenntnisse in Java und Spring'''
CONTRADICTORY = '''Overview: Data engineer in Munich.
Application: A cover letter is required.
FAQ: Do I need a cover letter? No cover letter needed, your CV is enough.'''
MIXED = '''Overview: We build logistics software in Zurich and are hiring a Senior Python Engineer.
Required experience
- Python, PostgreSQL, AWS
Sonstiges
Bitte senden Sie uns Ihre Bewerbung auf Deutsch, inklusive eines kurzen Motivationsschreibens.'''


def job_with(text):
    return JobLead(original_source_text=text)


def doc(type_, status, quote='', name=''):
    return {'type': type_, 'name': name, 'status': status, 'quote': quote}


def analysis(documents, posting_language='en', application_language='', application_language_quote=''):
    return {'posting_language': posting_language, 'application_language': application_language,
            'application_language_quote': application_language_quote, 'documents': documents}


def test_clear_english_requirement_is_kept_when_its_quote_matches_despite_whitespace_case_and_quote_marks():
    quote = '“please send your CV together with a cover letter explaining why you want to join us.”'
    result = normalize_application_requirements(analysis([doc('cover_letter', 'required', quote)]), job_with(EN_REQUIRED))
    assert result == {'posting_language': 'en', 'application_language': '', 'application_language_quote': '',
                      'documents': [doc('cover_letter', 'required', quote)], 'source': 'analysis'}


def test_explicitly_unwanted_letter_is_not_accepted_and_german_negation_is_optional_not_required():
    unwanted = normalize_application_requirements(analysis([doc('cover_letter', 'not_accepted', 'Please do not send a cover letter.')]), job_with(EN_NOT_WANTED))
    assert unwanted['documents'][0]['status'] == 'not_accepted'
    no_letter = normalize_application_requirements(
        analysis([doc('cover_letter', 'optional', 'Kein Anschreiben erforderlich – ein kurzer Lebenslauf genügt.')], posting_language='de'),
        job_with(DE_NO_LETTER))
    assert no_letter['posting_language'] == 'de'
    assert no_letter['documents'] == [doc('cover_letter', 'optional', 'Kein Anschreiben erforderlich – ein kurzer Lebenslauf genügt.')]


def test_not_mentioned_keeps_no_quote_and_needs_no_evidence():
    result = normalize_application_requirements(
        analysis([doc('cover_letter', 'not_mentioned', 'Gute Kenntnisse in Java'), doc('short_message', 'not_mentioned')], posting_language='de'),
        job_with(DE_SILENT))
    assert result['documents'] == [doc('cover_letter', 'not_mentioned'), doc('short_message', 'not_mentioned')]


def test_contradictory_instructions_for_the_same_document_become_unclear():
    result = normalize_application_requirements(analysis([
        doc('cover_letter', 'required', 'A cover letter is required.'),
        doc('cover_letter', 'optional', 'No cover letter needed, your CV is enough.'),
        doc('cover_letter', 'not_mentioned'),
    ]), job_with(CONTRADICTORY))
    assert result['documents'] == [doc('cover_letter', 'unclear')]


def test_application_language_outranks_posting_language_in_a_mixed_posting():
    quote = 'Bitte senden Sie uns Ihre Bewerbung auf Deutsch'
    result = normalize_application_requirements(analysis(
        [doc('motivation_letter', 'required', 'inklusive eines kurzen Motivationsschreibens'), doc('cover_letter', 'not_mentioned')],
        posting_language='mixed', application_language='de', application_language_quote=quote), job_with(MIXED))
    assert (result['posting_language'], result['application_language'], result['application_language_quote']) == ('mixed', 'de', quote)
    assert result['documents'][0]['status'] == 'required'


def test_fabricated_quotes_are_never_presented_as_required_or_preferred():
    result = normalize_application_requirements(analysis(
        [doc('cover_letter', 'required', 'A cover letter is mandatory.'), doc('short_message', 'preferred'),
         doc('other', 'required', 'Please attach your Arbeitszeugnisse.', name='Arbeitszeugnisse')],
        application_language='en', application_language_quote='Please apply in English.'), job_with(EN_REQUIRED))
    assert result['application_language'] == '' and result['application_language_quote'] == ''
    assert result['documents'] == [doc('cover_letter', 'unclear'), doc('short_message', 'unclear'), doc('other', 'unclear', name='Arbeitszeugnisse')]


def test_bad_enums_are_coerced_and_analysis_cannot_pose_as_an_owner_edit():
    value = {**analysis([doc('CV-letter', 'Mandatory', 'x'), 'not a dict']), 'posting_language': 'french', 'source': 'owner'}
    result = normalize_application_requirements(value, job_with(EN_REQUIRED), source='analysis')
    assert result == {'posting_language': 'unclear', 'application_language': '', 'application_language_quote': '',
                      'documents': [doc('other', 'unclear')], 'source': 'analysis'}
    # The owner's own edit is trusted without a posting quote; its enums are still enforced.
    owner = normalize_application_requirements({**analysis([doc('cover_letter', 'required')], application_language='de'), 'source': 'owner'}, job_with(DE_SILENT))
    assert owner['documents'] == [doc('cover_letter', 'required')] and owner['application_language'] == 'de' and owner['source'] == 'owner'
    assert normalize_application_requirements(None, job_with(EN_REQUIRED)) == {}


@pytest.mark.django_db
def test_import_stores_verified_requirements_and_old_json_imports_unchanged():
    payload = {'jobs': [
        {'company': 'Pay Co', 'title': 'Backend Engineer', 'original_source_text': EN_REQUIRED,
         'application_requirements': analysis([doc('cover_letter', 'required', 'Please send your CV together with a cover letter'),
                                                doc('short_message', 'preferred', 'Send us a short note.')])},
        {'company': 'Old Co', 'title': 'Engineer', 'original_source_text': DE_SILENT},
    ]}
    result = import_jobs_data(payload)
    assert result['ok'], result
    new, old = JobLead.objects.get(company='Pay Co'), JobLead.objects.get(company='Old Co')
    assert [d['status'] for d in new.application_requirements['documents']] == ['required', 'unclear']
    assert 'application_requirements' in result['jobs'][0]['updated_fields']
    assert old.application_requirements == {} and 'application_requirements' not in result['jobs'][1]['updated_fields']


@pytest.mark.django_db
def test_reanalysis_updates_analysis_but_not_an_owner_edit():
    job = JobLead.objects.create(company='Edit Co', title='Engineer', original_source_text=EN_NOT_WANTED)
    update = {'job_updates': [{'job_id': job.id, 'application_requirements': analysis([doc('cover_letter', 'not_accepted', 'Please do not send a cover letter.')])}]}
    assert import_jobs_data(update)['ok']
    job.refresh_from_db(); assert job.application_requirements['documents'][0]['status'] == 'not_accepted'
    owner_value = {**analysis([doc('cover_letter', 'required')]), 'source': 'owner'}
    JobLead.objects.filter(pk=job.pk).update(application_requirements=owner_value)
    assert import_jobs_data(update)['ok']
    job.refresh_from_db(); assert job.application_requirements == owner_value


@pytest.mark.django_db
def test_export_and_reimport_round_trip_requirements():
    owner = User.objects.create_user('req-owner')
    stored = normalize_application_requirements(analysis(
        [doc('motivation_letter', 'required', 'inklusive eines kurzen Motivationsschreibens')],
        posting_language='mixed', application_language='de', application_language_quote='Bewerbung auf Deutsch'), job_with(MIXED))
    JobLead.objects.create(company='Zurich Co', title='Senior Python Engineer', original_source_text=MIXED, application_requirements=stored, created_by=owner)
    exported = build_user_export(owner)
    assert exported['data']['jobs'][0]['application_requirements'] == stored
    other = User.objects.create_user('req-importer')
    assert not import_user_export(other, exported)['errors']
    assert JobLead.objects.get(created_by=other).application_requirements == stored


@pytest.mark.django_db
def test_analysis_prompts_ask_for_requirements_in_the_same_call():
    job = JobLead.objects.create(company='Prompt Co', title='Engineer', original_source_text=MIXED)
    for schema in (COMBINED_SCHEMA, ENRICHMENT_SCHEMA, BULK_LINKS_SCHEMA):
        assert '"application_requirements":{"posting_language"' in schema
    for prompt in (build_combined_prompt([job], candidate_profile='Backend engineer'),
                   build_enrichment_prompt([job], candidate_profile='Backend engineer'),
                   build_bulk_links_prompt(['https://example.test/job'], candidate_profile='Backend engineer')):
        assert APPLICATION_REQUIREMENTS_RULES in prompt and '"application_requirements"' in prompt


@pytest.mark.django_db
def test_csv_round_trip_and_null_requirements_import():
    from io import BytesIO
    from jobradar.services.user_data_portability import _payload_from_csv_file, export_user_data_csv
    owner = User.objects.create_user('req-csv-owner')
    stored = normalize_application_requirements(analysis(
        [doc('motivation_letter', 'required', 'inklusive eines kurzen Motivationsschreibens')], posting_language='mixed'), job_with(MIXED))
    JobLead.objects.create(company='Zurich Co', title='Senior Python Engineer', original_source_text=MIXED, application_requirements=stored, created_by=owner)
    payload = _payload_from_csv_file(BytesIO(export_user_data_csv(owner).encode('utf-8')))
    other = User.objects.create_user('req-csv-importer')
    assert not import_user_export(other, payload)['errors']
    assert JobLead.objects.get(created_by=other).application_requirements == stored
    third = User.objects.create_user('req-null-importer')
    exported = build_user_export(owner)
    exported['data']['jobs'][0]['application_requirements'] = None
    assert not import_user_export(third, exported)['errors']
    assert JobLead.objects.get(created_by=third).application_requirements == {}


@pytest.mark.django_db
def test_replacing_a_duplicate_drops_requirements_quoted_from_the_old_posting():
    from jobradar.services.job_replace import replace_job_with_supplied_data
    job = JobLead.objects.create(company='Zurich Co', title='Senior Python Engineer', original_source_text=MIXED,
                                 application_requirements={'posting_language': 'mixed', 'documents': [], 'source': 'owner'})
    replace_job_with_supplied_data(job, {'company': 'New Co', 'title': 'Engineer', 'url': 'https://example.test/new'})
    job.refresh_from_db()
    assert job.application_requirements == {}
