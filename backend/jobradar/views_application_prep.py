"""TASK-280.2: a job's automatic document preparation -- read its progress, or retry what failed.
TASK-280.3: review it (keep / discard / restore / select the final package), adjust one variant, and
copy or download a variant or the package. TASK-299: the board's compact progress overlay.
TASK-312: the cross-job preparation queue and its cancel / retry / move-to-front actions.

Its own module, like views_invites.py, so this feature does not touch views.py.
"""
from django.http import FileResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from .models import JobLead
from .services import application_prep
from .services.access import accessible_jobs
from .services.application_prep import prepare, public_state
from .services.cv_generator import is_cv_owner
from .throttles import CVGenerationUserThrottle


def _job(request, job_id):
    return accessible_jobs(request.user).filter(id=job_id).first() if is_cv_owner(request.user) else None


def _not_found():
    return Response({'detail': 'Not found.'}, status=404)


@api_view(['GET'])
def application_prep_status(request, job_id):
    job = _job(request, job_id)
    if not job:
        return _not_found()
    return Response(public_state(job, request.user))


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def application_prep_retry(request, job_id):
    """Prepare now, or re-run only the failed variants. Never touches a ready or running one."""
    job = _job(request, job_id)
    if not job:
        return _not_found()
    state = prepare(job.id, request.user, retry=True)
    if state is None:
        return Response({'detail': 'CV generation is unavailable on this server.'}, status=503)
    return Response(state)


@api_view(['POST'])
def application_prep_review(request, job_id):
    """{action: keep|discard|restore, key} or {action: select, keys: [...]} or {action: clear}."""
    job = _job(request, job_id)
    if not job:
        return _not_found()
    try:
        return Response(application_prep.review(job, request.user, request.data.get('action'), request.data.get('key') or '', request.data.get('keys')))
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def application_prep_adjust(request, job_id):
    """{key, instructions[, provider, model, effort, speed]}: readjust that one variant."""
    job = _job(request, job_id)
    if not job:
        return _not_found()
    choice = {field: request.data.get(field) for field in ('provider', 'model', 'effort', 'speed') if request.data.get(field)}
    try:
        return Response(application_prep.adjust(job, request.user, request.data.get('key') or '', request.data.get('instructions'), choice), status=202)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    except RuntimeError as exc:
        return Response({'detail': str(exc)}, status=503)


@api_view(['GET'])
def application_prep_export(request, job_id):
    """?key=<variant> (else the selected package) &as=zip|tex|pdf (not ?format=, which DRF reserves for content negotiation). Paths come from the job's own
    sidecar, never from the request; pdf (one variant) is served inline so it previews in a tab."""
    job = _job(request, job_id)
    if not job:
        return _not_found()
    key, kind = request.query_params.get('key', ''), request.query_params.get('as', 'zip')
    try:
        variants = application_prep.export_variants(job, request.user, key)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    if kind == 'tex':
        return Response({'text': application_prep.copy_text(job, variants)})
    if kind == 'pdf':
        pdf = next((path for name, path in variants[0]['files'].items() if name.endswith('_pdf')), None) if key else None
        if not pdf:
            return Response({'detail': 'Choose one document to preview.'}, status=400)
        return FileResponse(open(pdf, 'rb'), content_type='application/pdf', filename=application_prep.export_name(variants[0], pdf))
    archive, filename = application_prep.package_zip(job, request.user, variants, single=bool(key))
    response = HttpResponse(archive, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['GET'])
def application_prep_active(request):
    """TASK-299: {job_id: {running, done, failed, progress}} for the board. Preparation lives in the
    workspace sidecar, not the database, so it stays out of the cached board rows (TASK-283.2); the
    board polls this instead. Only unapplied jobs are read -- TASK-312 added New and Reviewed, which
    an imported apply/maybe evaluation now prepares too."""
    if not is_cv_owner(request.user):
        return _not_found()
    jobs = accessible_jobs(request.user).filter(status__in=JobLead.UNAPPLIED_STATUSES).only('id')
    summaries = {job.id: application_prep.board_summary(job, request.user) for job in jobs}
    return Response({job_id: summary for job_id, summary in summaries.items() if summary})


@api_view(['GET'])
def application_prep_queue(request):
    """TASK-312 AC4: {concurrency, items: [...]} -- every prepared variant across the owner's jobs."""
    if not is_cv_owner(request.user):
        return _not_found()
    return Response(application_prep.queue_state(request.user))


@api_view(['POST'])
def application_prep_queue_action(request):
    """TASK-312 AC5: {job_id, key, action: cancel|retry|first|continue (TASK-322)}; answers the queue as GET does."""
    if not is_cv_owner(request.user):
        return _not_found()
    try:
        return Response(application_prep.queue_action(request.user, request.data.get('job_id'), request.data.get('key') or '', request.data.get('action')))
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
