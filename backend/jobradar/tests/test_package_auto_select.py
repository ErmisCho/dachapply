"""TASK-389: the final package is selected without a click when only one is possible, and survives an Adjust."""
import pytest

from jobradar.models import JobLead
from jobradar.services import application_prep
from jobradar.tests.test_application_package import _review, _status, prepared  # noqa: F401 -- fixture
from jobradar.tests.test_application_prep import _job, _move, _req, _state, client, generator, owner, workspace  # noqa: F401 -- fixtures


@pytest.fixture
def single(client, owner, generator, django_capture_on_commit_callbacks):
    job = _job(owner, requirements=_req('en', 'en', cover_letter='required'))
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    assert set(_state(client, job)[0]) == {'cv-en', 'letter-en'}
    return job


def _selection(client, job):
    return _state(client, job)[1]['selection']


def test_one_cv_and_one_letter_in_one_language_are_selected_without_a_click(client, single):
    assert _selection(client, single) == ['cv-en', 'letter-en'] and _status(single) == 'ready_to_submit'


def test_two_cvs_are_not_auto_selected(client, prepared):
    assert _selection(client, prepared) == []


def test_mixed_languages_are_not_auto_selected(client, prepared):
    _review(client, prepared, action='discard', key='cv-en')
    _review(client, prepared, action='discard', key='letter-de')  # leaves cv-de and letter-en
    job = JobLead.objects.get(pk=prepared.pk)
    result = []
    application_prep._save(job, job.created_by_id, lambda prep: result.append(application_prep._auto_select(job, prep)))
    assert result == [False] and _selection(client, prepared) == []


def test_the_selection_survives_an_adjust_of_a_selected_variant(client, single):
    response = client.post(f'/api/jobs/{single.id}/application-prep/adjust/', {'key': 'cv-en', 'instructions': 'Shorten it.'}, format='json')
    assert response.status_code == 202
    payload = _state(client, single)[1]
    assert payload['selection'] == ['cv-en', 'letter-en'] and not payload['invalidated'] and _status(single) == 'ready_to_submit'


def test_a_discard_still_clears_the_selection(client, single):
    payload = _review(client, single, action='discard', key='cv-en').json()
    assert payload['selection'] == [] and 'discarded' in payload['invalidated'] and _status(single) == 'to_apply'
