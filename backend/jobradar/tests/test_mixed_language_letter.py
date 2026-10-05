"""TASK-262: a letter template may be in another language than the CV."""
import pytest
from django.contrib.auth.models import User

from jobradar.models import CvAsset, JobLead
from jobradar.services import cv_generator
from jobradar.services.cv_generator import generate_cv_package, generation_preview
from jobradar.tests.test_cv_assets import GENERATED, VALID_TEX, _fake_pdflatex


def test_english_cv_with_german_letter_writes_the_letter_in_german(db, tmp_path, monkeypatch, settings, cv_assets):
    """AC3. Before TASK-262 this raised 'Select a letter template matching the CV language.'"""
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_CACHE = False; settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir(); (tmp_path / 'output').mkdir()
    user = User.objects.create_user('mixed@example.test')
    cv_assets(user)
    CvAsset.objects.filter(user=user, kind=CvAsset.KIND_LETTER, key='anschreiben').update(source='DEUTSCHES ANSCHREIBEN')
    job = JobLead.objects.create(company='Acme', title='Engineer', raw_description='We are looking for a person with experience and skills for the responsibilities.', created_by=user)
    seen = _fake_pdflatex(monkeypatch, {**GENERATED, 'letter_tex': VALID_TEX})
    prompts = []
    real_prompt = cv_generator._prompt
    monkeypatch.setattr(cv_generator, '_prompt', lambda *args, **kwargs: prompts.append(real_prompt(*args, **kwargs)) or prompts[-1])

    _, _, saved = generate_cv_package(job, 'profile', 'en', 'anschreiben', True, 'openai', 'gpt-5.5', 'medium', user_id=user.id)

    assert saved['base_templates']['letter'] == ['anschreiben.tex'] and saved['letter_template'] == 'anschreiben'
    assert 'DEUTSCHES ANSCHREIBEN' in seen['tex'][-1]
    assert 'Required CV language: English' in prompts[-1] and 'Required letter language: German' in prompts[-1]

    # The trust boundary stays: a key that is in none of this account's templates is refused.
    with pytest.raises(ValueError, match='Select a letter template'):
        generate_cv_package(job, 'profile', 'en', 'no_such_letter', True, 'openai', 'gpt-5.5', 'medium', user_id=user.id)
    # ...including another account's letter key.
    other = User.objects.create_user('other@example.test')
    CvAsset.objects.create(user=other, kind=CvAsset.KIND_LETTER, key='foreign_letter', language='de', filename='f.tex', source='x')
    with pytest.raises(ValueError, match='Select a letter template'):
        generate_cv_package(job, 'profile', 'en', 'foreign_letter', True, 'openai', 'gpt-5.5', 'medium', user_id=user.id)


def test_default_letter_is_still_the_cv_languages_first(db, cv_assets):
    """AC4: widening the lookup must not move the preselected letter."""
    user = User.objects.create_user('defaults@example.test')
    cv_assets(user)
    english = JobLead.objects.create(company='Acme', title='Engineer', raw_description='We are looking for a person with experience and skills.', created_by=user)
    german = JobLead.objects.create(company='Firma', title='Entwickler', raw_description='Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben.', created_by=user)
    assert (generation_preview(english, user)['selected_cv'], generation_preview(english, user)['selected_letter']) == ('en', 'motivation_letter')
    assert (generation_preview(german, user)['selected_cv'], generation_preview(german, user)['selected_letter']) == ('de', 'anschreiben')  # CvAsset Meta ordering is by key
