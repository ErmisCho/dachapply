"""TASK-108: ?ordering=status,-fit_score -- comma-separated whitelisted keys, optional leading
'-' per key for descending, at most 3 honoured, unknown/duplicate keys dropped rather than
erroring, '-created_at' then 'id' always appended as tiebreakers, DEFAULT_BOARD_ORDERING when
nothing valid remains.

Self-contained (test_api.py owns TASK-97's original three single-value tests and stays
untouched); every fixture and helper needed here is local to this file.
"""
import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
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
        'reviewed', 'to_apply', 'ready_to_submit', 'applied', 'offer', 'accepted',  # everything else, pipeline order
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
    another. Low is the only 'new' job, so the default's status grouping puts it first regardless
    of its (worst) fit score. (Before TASK-277 an imminent apply_by did this; urgency no longer
    reorders the default, so High/Mid moved to 'reviewed' to keep the orders distinct.)
    """
    today = timezone.localdate()
    low = make_job(client, company='Low', status='new', feedback_due_date=today + timezone.timedelta(days=30))
    high = make_job(client, company='High', status='reviewed', feedback_due_date=today + timezone.timedelta(days=1))
    mid = make_job(client, company='Mid', status='reviewed', feedback_due_date=None)
    _evaluate(low, 40); _evaluate(high, 90); _evaluate(mid, 70)
    _pin(low, created_at=timezone.now() - timezone.timedelta(days=3))
    _pin(high, created_at=timezone.now() - timezone.timedelta(days=2))
    _pin(mid, created_at=timezone.now() - timezone.timedelta(days=1))
    return low, high, mid


# The shape being tested is "traverse a relation to reach a field the whitelist never named", not
# any particular field. These deliberately avoid credential words (`password`, `passwd`): the string
# exists precisely to be REJECTED, so naming it after a secret only teaches secret scanners to flag
# a test for doing its job. `last_login` is just as foreign to BOARD_ORDERINGS.
# Module-level so the TASK-145 AC4 saved-value test below reuses the same hostile values instead of
# retyping them.
HOSTILE_ORDERING_VALUES = [
    'evaluations__job__created_by__last_login',
    '-evaluations__job__created_by__last_login',
    "status; DROP TABLE jobradar_joblead;--",
    '../../etc/hosts',
    'company',
    '-id',
    '?',
]


@pytest.mark.parametrize('hostile', HOSTILE_ORDERING_VALUES)
def test_hostile_or_unrecognised_ordering_values_fall_back_to_default(client, sortable_board, hostile):
    default = [j['company'] for j in client.get('/api/jobs/').data]
    assert default == ['Low', 'High', 'Mid']
    r = client.get('/api/jobs/', {'ordering': hostile})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == default


# --- TASK-145 AC4: the saved sort actually APPLIES when the board loads -- the cap test above
# only proves the wire format/parser is shared once a client echoes the saved value back as
# ?ordering=; these prove the server reads UserProfile.board_sort_keys itself when the request
# carries no ordering= param at all. ---------------------------------------------------------

def test_saved_board_sort_orders_the_board_when_no_ordering_param_is_sent(client, tie_break_board):
    from jobradar.models import UserProfile
    UserProfile.objects.update_or_create(user=client.user, defaults={'board_sort_keys': 'status,-fit_score'})
    r = client.get('/api/jobs/', {'status': 'reviewed,archived'})  # no ordering= key at all
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['T-high', 'T-mid', 'T-low', 'Outlier']


def test_an_explicit_ordering_param_beats_the_saved_value(client, tie_break_board):
    from jobradar.models import UserProfile
    UserProfile.objects.update_or_create(user=client.user, defaults={'board_sort_keys': 'status,-fit_score'})
    r = client.get('/api/jobs/', {'status': 'reviewed,archived', 'ordering': 'status,fit_score'})
    assert r.status_code == 200
    # If the saved value had won this would read T-high, T-mid, T-low, Outlier instead.
    assert [j['company'] for j in r.data] == ['T-low', 'T-mid', 'T-high', 'Outlier']


@pytest.mark.parametrize('hostile', HOSTILE_ORDERING_VALUES)
def test_hostile_saved_board_sort_degrades_to_default_instead_of_erroring(client, sortable_board, hostile):
    from jobradar.models import UserProfile
    UserProfile.objects.update_or_create(user=client.user, defaults={'board_sort_keys': hostile})
    r = client.get('/api/jobs/')  # no ordering= key -> reads the (hostile) saved value
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['Low', 'High', 'Mid']  # same default as sortable_board's known order


def test_blank_saved_board_sort_yields_the_default_attention_ordering(client, sortable_board):
    """Distinct from test_no_ordering_param_yields_the_default_board_ordering above: that test's
    owner has no UserProfile row at all, this one has a row whose board_sort_keys is explicitly ''
    -- the AC8 "clear without editing the database" path -- so both must land on the default.
    """
    from jobradar.models import UserProfile
    UserProfile.objects.update_or_create(user=client.user, defaults={'board_sort_keys': ''})
    r = client.get('/api/jobs/')
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['Low', 'High', 'Mid']


def test_mixing_one_valid_key_with_junk_still_honours_the_valid_one(client, sortable_board):
    r = client.get('/api/jobs/', {'ordering': 'evaluations__job__created_by__last_login,-fit_score'})
    assert r.status_code == 200
    assert [j['company'] for j in r.data] == ['Low', 'High', 'Mid']  # TASK-329: Low is the only 'new' job


def test_no_ordering_param_yields_the_default_board_ordering(client, sortable_board):
    assert [j['company'] for j in client.get('/api/jobs/').data] == ['Low', 'High', 'Mid']


# --- AC8: the three pre-existing single-value orderings still behave as before -----------------

def test_legacy_single_value_orderings_still_work(client, sortable_board):
    get = lambda ordering: [j['company'] for j in client.get('/api/jobs/', {'ordering': ordering}).data]
    # TASK-329: each sort applies inside the status groups -- Low, the only 'new' job, leads.
    assert get('-fit_score') == ['Low', 'High', 'Mid']
    assert get('-created_at') == ['Low', 'Mid', 'High']
    assert get('feedback_due_date') == ['Low', 'High', 'Mid']  # ascending, nulls last


def test_a_column_sort_runs_inside_the_saved_status_order(client, sortable_board):
    """TASK-329 (owner 2026-10-21: Applied jobs led a Fit score sort although Applied is after New and
    To apply in the saved order). The saved order decides the groups; the column sorts inside them."""
    from jobradar.models import UserProfile
    get = lambda ordering: [j['company'] for j in client.get('/api/jobs/', {'ordering': ordering}).data]
    UserProfile.objects.update_or_create(user=client.user, defaults={'board_status_order': 'reviewed,new'})
    assert get('-fit_score') == ['High', 'Mid', 'Low'] and get('fit_score') == ['Mid', 'High', 'Low']
    assert get('-status,-fit_score')[0] == 'High'  # an explicit Status sort is not regrouped


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
    if key != 'status':  # TASK-329: other keys sort inside a status group, so put all three in one
        JobLead.objects.filter(pk__in=[job.pk for job in all_keys_board]).update(status='new')
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


# --- TASK-277: Sort: recommended = status group, then fit (nulls last), priority, newest; urgency
# never reorders a group; ?ordering=recommended is the explicit token for it. -------------------

def _ids(client, **params):
    r = client.get('/api/jobs/', params)
    assert r.status_code == 200
    return [j['id'] for j in r.data]


def test_parse_board_ordering_maps_the_recommended_token_to_the_default_and_never_passes_it_through():
    from jobradar.views import DEFAULT_BOARD_ORDERING, parse_board_ordering
    assert parse_board_ordering('recommended') == DEFAULT_BOARD_ORDERING
    assert parse_board_ordering(' recommended ,-fit_score') == DEFAULT_BOARD_ORDERING
    # Not first -> just an unknown key, dropped like any other.
    assert 'recommended' not in parse_board_ordering('-fit_score,recommended')


def test_recommended_orders_groups_then_fit_then_priority_then_newest(client):
    now = timezone.now()
    jobs = {}
    for name, status, fit, prio, days in [
        ('n_fit90_high', 'new', 90, 'high', 5),
        ('n_fit90_med', 'new', 90, 'medium', 1),     # ties n_fit90_high on fit -> priority decides
        ('n_fit70_old', 'new', 70, 'high', 4),
        ('n_fit70_new', 'new', 70, 'high', 2),       # ties n_fit70_old on fit AND priority -> newest
        ('i_fit95_low', 'interview', 95, 'low', 1),  # best fit overall, but a later group
        ('i_fit60_high', 'interview', 60, 'high', 1),
    ]:
        jobs[name] = make_job(client, company=name, status=status)
        _evaluate(jobs[name], fit, prio)
        _pin(jobs[name], created_at=now - timezone.timedelta(days=days))
    expected = [jobs[n].id for n in ('n_fit90_high', 'n_fit90_med', 'n_fit70_new', 'n_fit70_old', 'i_fit95_low', 'i_fit60_high')]
    assert _ids(client, ordering='recommended') == expected
    assert _ids(client) == expected  # absent ordering, no saved sort -> the same default


def test_recommended_puts_unscored_jobs_after_every_scored_job_of_their_group(client):
    """Pins NULL placement rather than trusting the DB default. The row-order assertion alone
    can't: SQLite already sorts NULLs last on DESC, PostgreSQL (production) sorts them FIRST -- so
    the emitted SQL must carry an explicit NULLS LAST, which is what PostgreSQL would execute."""
    unscored = make_job(client, company='unscored', status='new')
    low = make_job(client, company='low', status='new'); _evaluate(low, 10, 'low')
    mid = make_job(client, company='mid', status='new'); _evaluate(mid, 50, 'low')
    interview = make_job(client, company='interview', status='interview'); _evaluate(interview, 99, 'high')
    now = timezone.now()
    _pin(unscored, created_at=now); _pin(low, created_at=now - timezone.timedelta(days=2)); _pin(mid, created_at=now - timezone.timedelta(days=3))
    with CaptureQueriesContext(connection) as queries:
        assert _ids(client, ordering='recommended') == [mid.id, low.id, unscored.id, interview.id]
    # TASK-284: the fit sort is now the latest_fit_score annotation, which Django orders by column
    # position ('30 DESC NULLS LAST'), so pin the clause itself -- the fit key is its only user.
    assert any('DESC NULLS LAST' in q['sql'] for q in queries.captured_queries)


def test_recommended_ignores_deadline_and_staleness_within_a_group(client):
    today = timezone.localdate()
    due_soon = make_job(client, company='due_soon', status='new', apply_by=today + timezone.timedelta(days=JobLead.DEADLINE_SOON_DAYS - 1))
    stale = make_job(client, company='stale', status='new')
    _evaluate(due_soon, 40, 'medium'); _evaluate(stale, 90, 'medium')
    _pin(stale, created_at=timezone.now() - timezone.timedelta(days=JobLead.STALE_UNAPPLIED_DAYS + 5))
    # Pre-TASK-277 stale_rank put due_soon first and sank stale; now fit alone decides.
    assert _ids(client, ordering='recommended') == [stale.id, due_soon.id]


def test_explicit_recommended_beats_the_saved_sort_but_an_absent_ordering_still_uses_it(client):
    from jobradar.models import UserProfile
    # TASK-329: one status group, since every sort now runs inside the status groups.
    new_low = make_job(client, company='new_low', status='new'); _evaluate(new_low, 50, 'low')
    int_high = make_job(client, company='int_high', status='new'); _evaluate(int_high, 90, 'high')
    UserProfile.objects.update_or_create(user=client.user, defaults={'board_sort_keys': 'fit_score,priority'})
    assert _ids(client) == [new_low.id, int_high.id]                         # saved sort applies
    assert _ids(client, ordering='recommended') == [int_high.id, new_low.id]  # explicit token wins
