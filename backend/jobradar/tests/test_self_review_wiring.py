"""TASK-385: the self-review pass inside generate_cv_package."""
from pathlib import Path

import pytest
from django.contrib.auth.models import User

from jobradar.models import JobLead
from jobradar.services import cv_generator
from jobradar.services.cv_generator import RecoverableGenerationError, generate_cv_package
from jobradar.services.self_review import harden_findings
from jobradar.tests.test_cv_assets import GENERATED, GERMAN_SOURCE, VALID_TEX, _fake_pdflatex


@pytest.fixture
def run(db, tmp_path, monkeypatch, settings, cv_assets):
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_CACHE = False; settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir()
    user = User.objects.create_user('rev@example.test', email='rev@example.test')
    cv_assets(user, cv_source='TEMPLATE', photo=b'p')
    job = JobLead.objects.create(company='Firma', title='Entwickler', raw_description=GERMAN_SOURCE, created_by=user)
    _fake_pdflatex(monkeypatch, GENERATED)
    calls = []

    def go(findings=(), **kwargs):
        def fake_review(documents, *args, **kw):
            calls.append((documents, args))
            if isinstance(findings, Exception):
                raise findings
            return list(findings)
        monkeypatch.setattr('jobradar.services.self_review.review_documents', fake_review)
        _, _, saved = generate_cv_package(job, 'profile', 'de', '', False, 'openai', 'gpt-5.5', 'medium', user_id=user.id, **kwargs)
        return saved, calls
    return go


def fix(old, new, category='posting_fit'):
    return {'severity': 'improve', 'category': category, 'file': 'cv', 'explanation': 'x', 'old': old, 'new': new}


def test_review_called_once_and_valid_fix_applied(run):
    saved, calls = run([fix('tailored', 'tailored Erfahrung')])
    assert len(calls) == 1 and calls[0][1][1:5] == ('profile', 'openai', 'gpt-5.5', 'medium')
    assert 'tailored Erfahrung' in Path(saved['cv_tex']).read_text(encoding='utf-8')
    assert any(line.startswith('Self-review: 1 fixes applied (posting_fit), 0 dropped') for line in saved['report']['main_changes'])
    assert len(saved['report']['self_review']['applied']) == 1


def test_unsupported_word_and_wildcard_are_dropped(run):
    saved, _ = run([fix('tailored', 'tailored Kubernetes'), fix('\\begin{document}\n...\n', 'x')])
    assert Path(saved['cv_tex']).read_text(encoding='utf-8') == VALID_TEX
    reasons = [item['reason'] for item in saved['report']['self_review']['dropped']]
    assert any('kubernetes' in reason for reason in reasons) and 'wildcard OLD' in reasons


def test_failed_revalidation_restores_exact_files(run, monkeypatch):
    original = cv_generator._compile_pdf
    count = []

    def compile_then_fail(*args, **kwargs):
        count.append(1)
        if len(count) > 1:
            raise RecoverableGenerationError('page limit')
        return original(*args, **kwargs)
    monkeypatch.setattr(cv_generator, '_compile_pdf', compile_then_fail)
    saved, _ = run([fix('tailored', 'tailored Erfahrung')])
    assert len(count) == 2
    assert Path(saved['cv_tex']).read_bytes() == VALID_TEX.encode('utf-8')
    assert 'reverted' in saved['report']['self_review']


def test_reviewer_exception_does_not_fail_the_run(run):
    saved, _ = run(RuntimeError('boom'))
    assert Path(saved['cv_tex']).read_text(encoding='utf-8') == VALID_TEX


def test_not_called_on_revision(run, tmp_path, monkeypatch):
    first, _ = run([])
    saved, calls = run([fix('tailored', 'tailored Erfahrung')], source_cv=first['cv_tex'], revision_instructions='shorten')
    assert len(calls) == 1  # only the fresh run's call


def test_not_called_when_setting_off(run, settings):
    settings.CODEX_CV_SELF_REVIEW = False
    _, calls = run([fix('tailored', 'tailored Erfahrung')])
    assert calls == []


def test_harden_findings_unit():
    kept, dropped = harden_findings([fix('a b', 'a b c'), fix('a b', 'a')], 'c', '')
    assert len(kept) == 2 and not dropped
