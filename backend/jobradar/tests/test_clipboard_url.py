"""TASK-250: the copied TeX carries the job's listing URL as a LaTeX comment.

Hermetic: no provider runs, no LaTeX compiles and no clipboard is touched -- generate_cv_package,
recompile_generated_package and _copy_to_clipboard are all replaced, and the .tex files are fixtures
under tmp_path. The worker bodies (_run, _run_compile) are called in-thread on purpose: dispatching
them through start_cv_task would put the database write in another connection than this test's
transaction, which is the same reason test_api.py calls _run directly.
"""
from threading import Event

import pytest
from django.contrib.auth.models import User

from jobradar.models import JobLead
from jobradar.services import cv_tasks

URL = 'https://jobs.example.com/apply?ref=a%20b&id=7_8#top'  # %, &, _ and # all inside one comment


@pytest.fixture
def owner(db):
    return User.objects.create_user('clipboard-owner', password='pw')


@pytest.fixture
def job(db, owner):
    return JobLead.objects.create(company='ACME', title='Python Engineer', url=URL, created_by=owner)


@pytest.fixture
def sources(tmp_path):
    cv = tmp_path / 'cv.tex'; cv.write_text('CV BODY', encoding='utf-8')
    letter = tmp_path / 'letter.tex'; letter.write_text('LETTER BODY', encoding='utf-8')
    return {'cv_tex': str(cv), 'letter_tex': str(letter)}


def _run_generation(job, sources, monkeypatch, **kwargs):
    """Drive _run (the generation *and* readjustment worker) and return what reached the clipboard."""
    copied = []
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: copied.append(text) or True)
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', lambda *a, **k: (b'zip', 'a.zip', dict(sources)))
    cv_tasks._run('task', job.id, job.created_by_id, 'profile', 'en', 'motivation_letter', True,
                  'openai', 'gpt-5.5', 'medium', 'normal', cancel_event=Event(), **kwargs)
    assert copied, 'nothing was copied -- the worker failed before the clipboard step'
    return copied[0]


def test_generation_and_readjustment_clipboards_start_with_the_listing_url(job, sources, monkeypatch):
    """AC1 (generation + readjustment), AC2: a '%' comment line, then today's contents untouched."""
    expected = f'% Job listing: {URL}\n\n{cv_tasks._clipboard_contents(sources)}'
    assert _run_generation(job, sources, monkeypatch) == expected
    readjusted = _run_generation(job, sources, monkeypatch,
                                 source_cv=sources['cv_tex'], revision_instructions='shorten the summary')
    assert readjusted == expected
    # The two-file header structure and both documents survive the added line.
    assert '% ===== cv.tex =====\nCV BODY' in expected and '% ===== letter.tex =====\nLETTER BODY' in expected


def test_recompile_clipboard_starts_with_the_listing_url(job, sources, monkeypatch):
    """AC1 (recompile): the path that never calls a model still carries the URL."""
    copied = []
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: copied.append(text) or True)
    monkeypatch.setattr(cv_tasks, 'recompile_generated_package', lambda *a, **k: (b'zip', 'a.zip', dict(sources)))
    cv_tasks._run_compile('task', job.id, job.created_by_id, 'en', sources['cv_tex'], sources['letter_tex'],
                          {}, None, Event())
    assert copied == [f'% Job listing: {URL}\n\n{cv_tasks._clipboard_contents(sources)}']


def test_single_file_clipboard_gains_the_url_line(job, sources):
    """AC4: the branch that returns one file verbatim gets the line too."""
    only_cv = {'cv_tex': sources['cv_tex']}
    assert cv_tasks._clipboard_payload(only_cv, job.url) == f'% Job listing: {URL}\n\nCV BODY'


def test_a_job_without_a_url_produces_the_clipboard_exactly_as_before(db, owner, sources, monkeypatch):
    """AC3: no label, no placeholder, no leading blank lines -- byte-identical to _clipboard_contents."""
    job = JobLead.objects.create(company='ACME', title='Python Engineer', created_by=owner)
    assert job.url == ''
    assert _run_generation(job, sources, monkeypatch) == cv_tasks._clipboard_contents(sources)
    assert cv_tasks._clipboard_payload({'cv_tex': sources['cv_tex']}, job.url) == 'CV BODY'


def test_the_no_change_path_carries_the_url_and_stays_one_comment_line(job, sources, monkeypatch):
    """Sibling call site: 'no further CV changes required' also offers the copy button.

    Also pins the newline guard -- a URL with a stray newline would otherwise end the comment and
    leave the rest of the link as LaTeX source.
    """
    task = cv_tasks.get_cv_task(cv_tasks.start_cv_noop_task(job.id, job.created_by_id, sources), job.created_by_id)
    assert task['clipboard_tex'].startswith(f'% Job listing: {URL}\n\n')
    job.url = 'https://jobs.example.com/a\nb'
    assert cv_tasks._clipboard_payload(sources, job.url).splitlines()[0] == '% Job listing: https://jobs.example.com/a b'
