"""TASK-276: one tick of the in-app mailbox loop runs the check_mailbox logic, cadence-gated."""
from django.contrib.auth import get_user_model

from jobradar.services import mailbox, mailbox_loop
from jobradar.services.mailbox import MailboxCheckInProgress, pending_mailbox_check_request, queue_mailbox_check_request


def test_tick_runs_the_cadence_gated_check(db, monkeypatch):
    calls = []
    monkeypatch.setattr(mailbox, 'run_check', lambda force=False: calls.append(force))
    mailbox_loop.tick()
    assert calls == [False]


def test_tick_handles_a_pending_manual_request_first(db, monkeypatch):
    calls = []
    monkeypatch.setattr(mailbox, 'run_check', lambda force=False: calls.append(force))
    request = queue_mailbox_check_request(get_user_model().objects.create_user('owner', password='pw'))
    mailbox_loop.tick()
    request.refresh_from_db()
    assert calls == [True]
    assert request.handled_at is not None
    assert pending_mailbox_check_request() is None


def test_tick_never_raises(db, monkeypatch):
    def boom(force=False):
        raise RuntimeError('gmail down')
    monkeypatch.setattr(mailbox, 'run_check', boom)
    mailbox_loop.tick()

    def busy(force=False):
        raise MailboxCheckInProgress('A mailbox check is already running.')
    monkeypatch.setattr(mailbox, 'run_check', busy)
    mailbox_loop.tick()
