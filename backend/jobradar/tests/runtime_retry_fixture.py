"""Disposable daily/Retry runtime; only model analysis and generation are local fixtures."""
import json
import sys
import threading
from pathlib import Path

import django

django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from jobradar.models import JobLead, UserProfile
from jobradar.services import application_prep as prep, cv_tasks
from jobradar.services.processing_control import store

root = Path(settings.CODEX_CV_WORKSPACE)
root.mkdir(parents=True, exist_ok=True)
settings.CODEX_CV_ENABLED = True
requirements = {'posting_language': 'en', 'documents': [], 'source': 'owner'}

if sys.argv[1] == 'seed':
    user = get_user_model().objects.create_user('retry-fixture', password='fixture-password-123')
    UserProfile.objects.update_or_create(user=user, defaults={'can_generate_cv': True})
    job = JobLead.objects.create(created_by=user, company='Fixture', title='Retry', status='reviewed')
    store().enqueue('daily-document', {'args': [job.pk, user.pk], 'kwargs': {}})
    (root / 'block').touch()
    print(json.dumps({'job': job.pk, 'owner': user.pk}), flush=True)
else:
    def analyse(job):
        if (root / 'block').exists():
            (root / 'analysis-started').touch()
            threading.Event().wait()  # Parent kills this disposable runtime at this boundary.
        return requirements

    def gate(job, user):
        variants, reason = prep.plan_variants(job.application_requirements)
        return reason, variants, 'Fixture evidence', {
            'provider': 'openai', 'model': 'fixture', 'effort': 'medium', 'speed': 'normal'}

    def generate(*args, **kwargs):
        tex = root / 'fixture.tex'
        tex.write_text('Fixture document', encoding='utf-8')
        tex.with_suffix('.pdf').write_bytes(b'%PDF fixture')
        return b'fixture archive', 'fixture.zip', {'cv_tex': str(tex), 'cv_pdf': str(tex.with_suffix('.pdf'))}

    prep._analyse = analyse
    prep._gate = gate
    prep.load_candidate_evidence = lambda *args: 'Fixture evidence'
    cv_tasks.generate_cv_package = generate
    call_command('dashboard_runtime', port=int(sys.argv[2]), control_port=int(sys.argv[3]))
