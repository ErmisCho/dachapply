"""Disposable subprocess fixture for the real cancellation lifecycle regression."""
import json
from pathlib import Path

import django

django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from jobradar.models import JobLead, UserProfile
from jobradar.services import cv_tasks
from jobradar.services.processing_control import store

assert store().mode() == 'paused'
user = get_user_model().objects.create_user('cancel-fixture', email='cancel@example.test', password='fixture-password-123')
profile, _ = UserProfile.objects.get_or_create(user=user)
profile.can_generate_cv = True
profile.save()
job = JobLead.objects.create(created_by=user, company='Fixture', title='Cancelled compilation', status='new')
source = Path(settings.CODEX_CV_WORKSPACE) / 'cancelled.tex'
source.parent.mkdir(parents=True, exist_ok=True)
source.write_text(r'\documentclass{article}\begin{document}Cancelled work.\end{document}')
task = cv_tasks.start_cv_compile_task(job.pk, user.pk, 'en', source_cv=str(source))
print(json.dumps({'task': task}), flush=True)
