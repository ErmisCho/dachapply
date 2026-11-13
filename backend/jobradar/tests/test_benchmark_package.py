"""TASK-369: hermetic package experiment contracts."""
from pathlib import Path

import pytest
from django.core.management.base import CommandError

from jobradar.services import benchmark as bench, benchmark_package as package, cv_generator as gen
from jobradar.tests.test_benchmark import exported


@pytest.mark.django_db
@pytest.mark.parametrize('failure', [None, RuntimeError('failed'), gen.GenerationCancelled()])
def test_package_comparison_alternatives_retry_and_review(exported, tmp_path, settings, monkeypatch, failure):  # TASK-369
    from jobradar.models import JobLead
    fixture, user = exported
    jobs = list(JobLead.objects.filter(created_by=user))
    calls = []
    options = [{'provider': 'openai', 'key': gen.CV_DEFAULT_MODEL[1], 'efforts': ['high'], 'default_effort': 'high'}]
    monkeypatch.setattr(package.prep, 'available_model_options', lambda: options)
    monkeypatch.setattr(package.prep, 'validate_model_capability', lambda *a, **kw: None)
    def generate(job, profile, cv_key, letter_key, create_letter, provider, model, effort, speed='normal', create_cv=True, user_id=None, **kwargs):
        calls.append((Path(settings.CODEX_CV_WORKSPACE).name, job.pk, create_cv, create_letter, letter_key, user_id, profile, model, effort))
        if create_cv and create_letter and failure:
            raise failure
        saved = {}
        for kind in (['cv'] if create_cv else []) + (['letter'] if create_letter else []):
            for extension in ('tex', 'pdf'):
                path = Path(settings.CODEX_CV_WORKSPACE) / f'{user_id}-{job.pk}-{kind}-{letter_key}.{extension}'
                path.write_text('fake')
                saved[kind+'_'+extension] = str(path)
        return b'zip', 'package.zip', saved
    recorder = bench.Recorder(settings.CODEX_CV_WORKSPACE)
    monkeypatch.setattr(package.cv_tasks, 'generate_cv_package', recorder.generate(generate))
    states = package.package(jobs, user, 1, None)
    assert len([c for c in calls if c[0] == 'separate']) == 6
    assert len([c for c in calls if c[0] == 'combined']) == 4
    assert all(c[5] == user.pk for c in calls)
    assert len({(c[6], c[7], c[8]) for c in calls}) == 1
    assert recorder.overwrite_check({j.pk: user.pk for j in jobs})['ok']
    before = {a['path']: Path(a['path']).read_bytes() for a in recorder.artifacts}
    for state in states:
        assert len(state['variants']) == 6
        assert state['variants']['combined:letter-en-alternative']['status'] == 'ready'
        assert state['variants']['combined:cv-en']['status'] == ('cancelled' if isinstance(failure, gen.GenerationCancelled) else 'failed' if failure else 'ready')
    calls.clear()
    package.package(jobs, user, 1, None)
    assert len(calls) == (2 if failure else 0)
    assert all(Path(path).read_bytes() == content for path, content in before.items())
    result = dict(states=states, requests=[], artifacts=recorder.artifacts, job_mapping={j.pk: j.pk for j in jobs})
    package.review(result, tmp_path)
    review = (tmp_path/'review.md').read_text()
    assert '| Document | separate | combined |' in review
    assert 'Manual corrections' in review and 'page limit met' in review and 'language en' in review
    assert all(a['path'] in review for a in recorder.artifacts if a['kind'].endswith('_pdf'))


def test_package_registry_and_invalid_variant():  # TASK-369
    assert bench.EXPERIMENTS['package'] is package.package
    with pytest.raises(CommandError, match='variants'):
        package.package([], None, 1, 'invalid')


@pytest.mark.django_db
def test_real_generator_combined_repairs_and_preserves_templates(exported, tmp_path, settings, monkeypatch):  # TASK-369
    from types import SimpleNamespace
    from jobradar.models import JobLead
    fixture, user = exported
    settings.CODEX_CV_CACHE = False
    options = [{'provider': 'openai', 'key': gen.CV_DEFAULT_MODEL[1], 'efforts': ['high'], 'default_effort': 'high'}]
    monkeypatch.setattr(package.prep, 'available_model_options', lambda: options)
    monkeypatch.setattr(package.prep, 'validate_model_capability', lambda *a, **kw: None)
    monkeypatch.setattr(gen, 'validate_model_capability', lambda *a, **kw: {})
    monkeypatch.setattr(gen.shutil, 'which', lambda name: name)
    monkeypatch.setattr(gen, '_pdf_pages', lambda path: 1)
    calls = []
    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        calls.append(prompt)
        if len(calls) == 7:
            return {}  # TASK-369: first combined response needs the real validation/repair loop.
        return {'cv_tex': r'\documentclass{article}\begin{document}CV\end{document}',
                'letter_tex': r'\documentclass{article}\begin{document}Letter\end{document}',
                'changed_files': [], 'main_changes': [], 'unsupported_requirements_not_claimed': [], 'confirmations': {}}
    def command(command, cancelled=None, **kwargs):
        if command[0] == 'pdflatex':
            (Path(kwargs['cwd']) / Path(command[-1]).with_suffix('.pdf')).write_bytes(b'%PDF-fake')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(gen, 'run_structured_model', model)
    monkeypatch.setattr(gen, '_run_command', command)
    JobLead.objects.filter(created_by=user).delete()
    user.delete()
    result = bench.run_fixture(fixture, 'package', None, 1, tmp_path/'results')
    states = result['states']
    assert len(calls) == 11
    assert 'AUTOMATIC REPAIR ATTEMPT' in calls[7]
    assert all(v['status'] == 'ready' for s in states for v in s['variants'].values())
    files = [p for s in states for v in s['variants'].values() for p in v['files'].values()]
    assert len(files) == len(set(files)) == 24
    assert all(Path(p).is_file() for p in files)
    assert result['overwrite_check']['ok'], result['overwrite_check']
    assert len(result['requests']) == 11 and sum(r['repair'] for r in result['requests']) == 1
    assert {r['package_arm'] for r in result['requests']} == {'separate', 'combined'}
    assert (tmp_path/'results'/'review.md').exists()
    import io
    import zipfile
    from django.test.utils import override_settings
    job = JobLead.objects.get(pk=next(iter(result['job_mapping'].values())))
    for arm in ('separate', 'combined'):
        with override_settings(CODEX_CV_WORKSPACE=str(Path(result['workspace'])/arm)):
            variants = package.prep._state(job, job.created_by)['variants']
            keys = ['cv-en', 'letter-en-alternative']
            package.prep._check_package(job, variants, keys)
            chosen = [variants[key] for key in keys]
            assert package.prep.export_name(chosen[1], chosen[1]['files']['letter_tex']) in package.prep.copy_text(job, chosen)
            archive, _ = package.prep.package_zip(job, job.created_by, chosen, False)
            with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                assert len(bundle.namelist()) == 4 and len(set(bundle.namelist())) == 4
    import shutil
    shutil.rmtree(result['workspace'])  # TASK-369: only the retained workspace this test created.
