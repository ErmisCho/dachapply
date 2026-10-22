"""TASK-338: the daily reminder digest never goes to the demo account or an RFC 2606 example domain
(2026-10-22: a digest to demo@dachapply.com bounced back to the owner)."""
import pytest
from django.contrib.auth.models import User

from jobradar.services.demo_data import DEMO_USERNAME
from jobradar.services.followup_digest import undeliverable


@pytest.mark.parametrize('username,email,skipped', [
    (DEMO_USERNAME, DEMO_USERNAME, True),
    ('tester', 'tester@example.com', True),
    ('tester2', 'someone@mail.example.org', False),  # only the exact example.* domains are reserved
    ('tester3', 'someone@host.invalid', True),
    ('tester4', 'owner@gmail.com', False),
])
def test_demo_and_reserved_addresses_are_never_mailed(db, username, email, skipped):
    user = User.objects.create_user(username, email=email, password='pw')
    assert undeliverable(user) is skipped
