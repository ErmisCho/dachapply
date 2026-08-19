"""TASK-108: ?ordering=status,-fit_score -- comma-separated whitelisted keys, optional leading
'-' per key for descending, at most 3 honoured, unknown/duplicate keys dropped rather than
erroring, '-created_at' then 'id' always appended as tiebreakers, DEFAULT_BOARD_ORDERING when
nothing valid remains.

Self-contained (test_api.py owns TASK-97's original three single-value tests and stays
untouched); every fixture and helper needed here is local to this file.
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from jobradar.models import JobLead, JobEvaluation

ALL_STATUSES = [status for status, _label in JobLead.STATUSES]


@pytest.fixture
def owner(db):
    return User.objects.create_user('board-owner', password='pw')


@pytest.fixture
def client(db, owner):
    c = APIClient(); c.force_authenticate(owner); c.user = owner; return c


def make_job(client, **kwargs):
    kwargs.setdefault('created_by', client.user)
    return JobLead.objects.create(**kwargs)


def _evaluate(job, fit_score, priority='medium'):
    return JobEvaluation.objects.create(job=job, fit_score=fit_score, priority=priority, recommendation='apply')


def _pin(job, **fields):
    """created_at/updated_at are auto_now[_add]; only .update() sets them directly, going
    around Model.save() the way test_api.py's _pin_created_at already does for created_at."""
    JobLead.objects.filter(pk=job.pk).update(**fields)


# --- AC1: status sorts in JobLead.STATUSES' pipeline order, not status_rank's attention order --

@pytest.fixture
def one_job_per_status(client):
    return {s: make_job(client, company=s, title='role', status=s) for s in ALL_STATUSES}


def test_status_ordering_follows_the_pipeline_order_declared_on_the_model(client, one_job_per_status):
    r = client.get('/api/jobs/', {'status': ','.join(ALL_STATUSES), 'ordering': 'status'})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ALL_STATUSES
    assert len(r.data) == len(ALL_STATUSES)


# --- TASK-145 AC1/AC2/AC3: the DEFAULT order is attention order (new, then interview, then the
# rest in pipeline order, closed last) -- a different permutation of the same eleven statuses
# than the pipeline test above, which is the whole point: it proves the default groups 'new' and
# 'interview' to the front instead of leaving them in their plain pipeline positions (2nd and 5th).

def test_default_ordering_groups_new_then_interview_then_pipeline_order_then_closed_last(client, one_job_per_status):
    r = client.get('/api/jobs/', {'status': ','.join(ALL_STATUSES)})  # no ordering= -> default
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == [
        'new', 'interview',                                       # groups 1 and 2 (the owner's ask)
        'reviewed', 'to_apply', 'applied', 'offer', 'accepted',    # everything else, pipeline order
        'rejected', 'withdrawn', 'skipped', 'archived',            # closed, last
    ]
    assert len(r.data) == len(ALL_STATUSES)


# --- TASK-145 AC7: the allowlist still refuses the exact hostile key the task names -------------

def test_created_by_password_ordering_degrades_to_default_rather_than_erroring(client):
    """TASK-145 AC7 names this literal key. A separate, standalone test (not folded into the
    hostile-values parametrize above, which deliberately avoids credential words) because the
    task calls it out by name as the thing to prove."""
    make_job(client, company='Low', status='new')
    make_job(client, company='High', status='new')
    default = [j['company'] for j in client.get('/api/jobs/').data]
    r = client.get('/api/jobs/', {'ordering': '-created_by__password'})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == default


# --- AC2/AC3: multi-key precedence, direction independence, second key only decides ties -------

@pytest.fixture
def tie_break_board(client):
    """Three 'reviewed' jobs tied on status, one 'archived' outlier with the highest fit score.

    If fit_score decided regardless of status, the outlier (999) would sort first. Status-first
    must instead put it last -- 'archived' is the final pipeline status -- which is the only way
    to tell "first key decided" apart from "second key decided".
    """
    t_low = make_job(client, company='T-low', status='reviewed')
    t_high = make_job(client, company='T-high', status='reviewed')
    t_mid = make_job(client, company='T-mid', status='reviewed')
    outlier = make_job(client, company='Outlier', status='archived')
    _evaluate(t_low, 20); _evaluate(t_high, 80); _evaluate(t_mid, 50); _evaluate(outlier, 999)
    return t_low, t_high, t_mid, outlier


def test_second_key_only_decides_rows_tied_on_the_first(client, tie_break_board):
    r = client.get('/api/jobs/', {'status': 'reviewed,archived', 'ordering': 'status,-fit_score'})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['T-high', 'T-mid', 'T-low', 'Outlier']


def test_a_key_direction_flips_independently_of_the_others(client, tie_break_board):
    # Same primary key (status, ascending); only the second key's direction changes.
    r = client.get('/api/jobs/', {'status': 'reviewed,archived', 'ordering': 'status,fit_score'})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['T-low', 'T-mid', 'T-high', 'Outlier']


def test_duplicate_keys_collapse_to_a_single_slot(client, tie_break_board):
    q = {'status': 'reviewed,archived'}
    with_dup = [j['company'] for j in client.get('/api/jobs/', {**q, 'ordering': 'status,status,-fit_score'}).data]
    without_dup = [j['company'] for j in client.get('/api/jobs/', {**q, 'ordering': 'status,-fit_score'}).data]
    assert with_dup == without_dup == ['T-high', 'T-mid', 'T-low', 'Outlier']


# --- at most 3 keys honoured; a 4th falls through to the -created_at/id tiebreaker -------------

@pytest.fixture
def capped_tie_board(client):
    """Three jobs tied on status/fit_score/priority (the first 3 keys asked for); updated_at
    differs, in the OPPOSITE order from created_at, so a 4th key of -updated_at being honoured
    would produce a different order than the -created_at tiebreaker it should fall through to.
    """
    j1 = make_job(client, company='J1', status='reviewed')
    j2 = make_job(client, company='J2', status='reviewed')
    j3 = make_job(client, company='J3', status='reviewed')
    for j in (j1, j2, j3):
        _evaluate(j, 50, priority='medium')
    now = timezone.now()
    _pin(j1, created_at=now - timezone.timedelta(days=3), updated_at=now)                                  # oldest created, newest updated
    _pin(j2, created_at=now - timezone.timedelta(days=2), updated_at=now - timezone.timedelta(days=10))    # mid created, oldest updated
    _pin(j3, created_at=now - timezone.timedelta(days=1), updated_at=now - timezone.timedelta(days=5))     # newest created, mid updated
    return j1, j2, j3


def test_a_fourth_ordering_key_is_dropped_not_honoured(client, capped_tie_board):
    r = client.get('/api/jobs/', {'ordering': 'status,fit_score,priority,-updated_at'})
    assert r.status_code == 200
    # -updated_at honoured would read J1, J3, J2. Capped at 3, the -created_at tiebreaker
    # (newest first) decides instead.
    assert [j['company'] for j in r.data] == ['J3', 'J2', 'J1']


# TASK-145 AC9: the cap holds for a value that came from UserProfile.board_sort_keys too, not
# only one typed by a client -- same wire format, same parser, so nothing needs a second cap.
def test_a_saved_board_sort_with_four_keys_is_capped_the_same_way_as_a_typed_one(client, capped_tie_board):
    from jobradar.models import UserProfile
    profile, _ = UserProfile.objects.update_or_create(user=client.user, defaults={'board_sort_keys': 'status,fit_score,priority,-updated_at'})
    saved = profile.board_sort_keys
    r = client.get('/api/jobs/', {'ordering': saved})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['J3', 'J2', 'J1']


# --- AC4: whitelist -- nothing a client sends reaches order_by() directly ----------------------

@pytest.fixture
def sortable_board(client):
    """Low/High/Mid, tuned so the default board order, -fit_score, -created_at and
    feedback_due_date all disagree -- so a test asserting one of them can't be vacuously true of
    another. Low's imminent apply_by makes stale_rank surface it first under the default
    formula regardless of its (worst) fit score.
    """
    today = timezone.localdate()
    low = make_job(client, company='Low', status='new', apply_by=today, feedback_due_date=today + timezone.timedelta(days=30))
    high = make_job(client, company='High', status='new', feedback_due_date=today + timezone.timedelta(days=1))
    mid = make_job(client, company='Mid', status='new', feedback_due_date=None)
    _evaluate(low, 40); _evaluate(high, 90); _evaluate(mid, 70)
    _pin(low, created_at=timezone.now() - timezone.timedelta(days=3))
    _pin(high, created_at=timezone.now() - timezone.timedelta(days=2))
    _pin(mid, created_at=timezone.now() - timezone.timedelta(days=1))
    return low, high, mid


# The shape being tested is "traverse a relation to reach a field the whitelist never named", not
# any particular field. These deliberately avoid credential words (`password`, `passwd`): the string
# exists precisely to be REJECTED, so naming it after a secret only teaches secret scanners to flag
# a test for doing its job. `last_login` is just as foreign to BOARD_ORDERINGS.
@pytest.mark.parametrize('hostile', [
    'evaluations__job__created_by__last_login',
    '-evaluations__job__created_by__last_login',
    "status; DROP TABLE jobradar_joblead;--",
    '../../etc/hosts',
    'company',
    '-id',
    '?',
])
def test_hostile_or_unrecognised_ordering_values_fall_back_to_default(client, sortable_board, hostile):
    default = [j['company'] for j in client.get('/api/jobs/').data]
    assert default == ['Low', 'High', 'Mid']
    r = client.get('/api/jobs/', {'ordering': hostile})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == default


def test_mixing_one_valid_key_with_junk_still_honours_the_valid_one(client, sortable_board):
    r = client.get('/api/jobs/', {'ordering': 'evaluations__job__created_by__last_login,-fit_score'})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['High', 'Mid', 'Low']


def test_no_ordering_param_yields_the_default_board_ordering(client, sortable_board):
    assert [j['company'] for j in client.get('/api/jobs/').data] == ['Low', 'High', 'Mid']


# --- AC8: the three pre-existing single-value orderings still behave as before -----------------

def test_legacy_single_value_orderings_still_work(client, sortable_board):
    get = lambda ordering: [j['company'] for j in client.get('/api/jobs/', {'ordering': ordering}).data]
    assert get('-fit_score') == ['High', 'Mid', 'Low']
    assert get('-created_at') == ['Mid', 'High', 'Low']
    assert get('feedback_due_date') == ['High', 'Low', 'Mid']  # ascending, nulls last


# --- AC3, exhaustively: every whitelisted key maps to its own expression, both directions ------

@pytest.fixture
def all_keys_board(client):
    """One job per rank on every whitelisted key, chosen so ascending and descending each
    produce a distinctive order per key -- proving no two keys accidentally share one
    expression. priority_rank and feedback_due_date deliberately don't follow the plain A/B/C
    pattern the other five keys do: priority_rank is highest-first at rank 0, and
    feedback_due_date sinks nulls to the bottom regardless of direction (see _ordering_expr).
    """
    today = timezone.localdate()
    now = timezone.now()
    a = make_job(client, company='A', status='new', applied_at=today - timezone.timedelta(days=180), feedback_due_date=today + timezone.timedelta(days=10))
    b = make_job(client, company='B', status='reviewed', applied_at=today - timezone.timedelta(days=90), feedback_due_date=today + timezone.timedelta(days=5))
    c = make_job(client, company='C', status='interview', applied_at=today - timezone.timedelta(days=1), feedback_due_date=None)
    _evaluate(a, 30, priority='low'); _evaluate(b, 60, priority='medium'); _evaluate(c, 90, priority='high')
    _pin(a, created_at=now - timezone.timedelta(days=3), updated_at=now - timezone.timedelta(days=3))
    _pin(b, created_at=now - timezone.timedelta(days=2), updated_at=now - timezone.timedelta(days=2))
    _pin(c, created_at=now - timezone.timedelta(days=1), updated_at=now - timezone.timedelta(days=1))
    return a, b, c


@pytest.mark.parametrize('key,ascending_order,descending_order', [
    ('status', ['A', 'B', 'C'], ['C', 'B', 'A']),
    ('fit_score', ['A', 'B', 'C'], ['C', 'B', 'A']),
    ('created_at', ['A', 'B', 'C'], ['C', 'B', 'A']),
    ('applied_at', ['A', 'B', 'C'], ['C', 'B', 'A']),
    ('updated_at', ['A', 'B', 'C'], ['C', 'B', 'A']),
    ('priority', ['C', 'B', 'A'], ['A', 'B', 'C']),
    ('feedback_due_date', ['B', 'A', 'C'], ['A', 'B', 'C']),
])
def test_every_whitelisted_key_sorts_both_directions(client, all_keys_board, key, ascending_order, descending_order):
    assert [j['company'] for j in client.get('/api/jobs/', {'ordering': key}).data] == ascending_order
    assert [j['company'] for j in client.get('/api/jobs/', {'ordering': f'-{key}'}).data] == descending_order


# --- AC5: deterministic, including "across pagination" on an endpoint that has none ------------

def test_ordering_is_deterministic_and_stable_across_slices(client, tie_break_board):
    """/api/jobs/ is intentionally unpaginated (see get_queryset's own comment), so "stable
    across pagination" is verified the way it would matter if pagination were added: two
    independent requests return byte-identical order, and slicing that one deterministic order
    into pages leaves no row duplicated or missing.
    """
    q = {'status': 'reviewed,archived', 'ordering': 'status,-fit_score'}
    first = [j['id'] for j in client.get('/api/jobs/', q).data]
    second = [j['id'] for j in client.get('/api/jobs/', q).data]
    assert first == second
    assert len(first) == 4
    page1, page2 = first[:2], first[2:]
    assert set(page1) & set(page2) == set()
    assert set(page1) | set(page2) == set(first)
