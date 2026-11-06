"""TASK-356: the database usage panel's data, for the configured account only."""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import db_usage


@api_view(['GET'])
def db_usage_status(request):
    """Reads the local state file, so opening the panel costs no query beyond authentication."""
    if not db_usage.is_owner(request.user):
        return Response({'detail': 'Not found.'}, status=404)
    return Response(db_usage.public_state())
