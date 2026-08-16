import secrets

from rest_framework import viewsets
from rest_framework.response import Response

from .models import InviteCode
from .serializers import InviteCodeSerializer
from .services.email_verification import unverified_email_response


class InviteCodeViewSet(viewsets.ModelViewSet):
    """A user's own invite codes: list, mint, revoke.

    DELETE revokes rather than deletes. Dropping the row would orphan nothing (JobLead has no
    FK to InviteCode) but it would erase the record of who a friend submitted through, so the
    code is flipped inactive instead: is_valid() rejects new submissions, and the jobs already
    submitted through it keep submitted_for=owner.
    """
    serializer_class = InviteCodeSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return InviteCode.objects.filter(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        # TASK-93 AC1: a code routes anonymous submissions onto the minter's board, which is exactly
        # the "invite/code feature" the verification gate exists for -- an unproven address must not
        # be able to mint one and start collecting other people's job links. Listing and revoking
        # stay open: one shows you what you already have, the other only takes access away.
        return unverified_email_response(request.user) or super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # token_urlsafe(9) is 12 url-safe chars / 72 bits. No custom strength logic (TASK-92).
        serializer.save(owner=self.request.user, code=secrets.token_urlsafe(9))

    def destroy(self, request, pk=None):
        invite = self.get_object()
        InviteCode.objects.filter(pk=invite.pk).update(active=False)
        return Response(status=204)
