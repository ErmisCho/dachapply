"""TASK-280.2: a job's automatic document preparation -- read its progress, or retry what failed.

Its own module, like views_invites.py, so this feature does not touch views.py.
"""
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from .services.access import accessible_jobs
from .services.application_prep import prepare, public_state
from .services.cv_generator import is_cv_owner
from .throttles import CVGenerationUserThrottle


@api_view(['GET'])
def application_prep_status(request, job_id):
    job = accessible_jobs(request.user).filter(id=job_id).first() if is_cv_owner(request.user) else None
    if not job:
        return Response({'detail': 'Not found.'}, status=404)
    return Response(public_state(job, request.user))


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def application_prep_retry(request, job_id):
    """Prepare now, or re-run only the failed variants. Never touches a ready or running one."""
    job = accessible_jobs(request.user).filter(id=job_id).first() if is_cv_owner(request.user) else None
    if not job:
        return Response({'detail': 'Not found.'}, status=404)
    state = prepare(job.id, request.user, retry=True)
    if state is None:
        return Response({'detail': 'CV generation is unavailable on this server.'}, status=503)
    return Response(state)
