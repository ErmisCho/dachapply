from django.db.models import Q

from jobradar.models import JobLead


def is_staff_user(user):
    return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))


def owned_by(user):
    """The one definition of "this user's job": theirs to read in full and to mutate.

    A job belongs to the person it was submitted *for*; when it was submitted for nobody it
    belongs to whoever created it. Creating a job for someone else is a handover, not ownership --
    before TASK-84 this was `created_by OR submitted_for`, so a friend who forwarded a link kept
    full read and write access to the recipient's evaluations, notes and follow-ups forever.

    submitted_for matches on the recipient alone, so a submission with no `created_by` at all
    (an anonymous invite-code submission) is still fully visible to the person it was sent to.
    """
    return Q(submitted_for=user) | Q(created_by=user, submitted_for__isnull=True)


def accessible_jobs(user):
    """Jobs a request user may read in full or mutate.

    Every consumer routes through here -- the board list, /api/stats/, the dashboard panels, the
    exports, every nested note/evaluation/follow-up and every mailbox row scoped through a job --
    so this is the one place the board's scope is decided.

    TASK-184: there is no staff exemption. It used to return the whole table for staff, which put
    the demo account's and the referral fixtures' jobs on the owner's board (measured: 93 rows
    accessible, 83 owned) and would have put every future signup's jobs there too. That is the same
    argument followup_digest.owned_jobs' docstring already made for the reminder email -- "that
    grants staff every row in the table, which is right for the admin API and very wrong for a
    personal" view -- and the board is a personal view. Staff oversight lives in Django admin
    (jobradar.admin.JobLeadAdmin) and in /api/export/, which still adds legacy unowned rows for
    staff (services.user_data_portability.owned_jobs); neither goes through here.
    """
    if not getattr(user, 'is_authenticated', False):
        return JobLead.objects.none()
    return JobLead.objects.filter(owned_by(user)).distinct()


def submitted_away_jobs(user):
    """Jobs this user submitted for somebody else: proof of submission, never a workspace.

    Read-only and deliberately narrow -- callers must project these rows down to the submission
    itself (see views.submission_row). TASK-184: no staff exemption here either -- it used to be
    empty for staff because accessible_jobs already returned everything for them, and once that
    stopped being true, keeping this empty would have made a staff user's own handed-off
    submissions the one thing they could no longer see anywhere on their board.
    """
    if not getattr(user, 'is_authenticated', False):
        return JobLead.objects.none()
    # distinct() only so this can be OR-combined with accessible_jobs, which is distinct itself.
    return JobLead.objects.filter(created_by=user, submitted_for__isnull=False).exclude(submitted_for=user).distinct()


def friend_submission_target(user):
    profile = getattr(user, 'jobradar_profile', None)
    if profile and profile.submit_for_id:
        return profile.submit_for
    return None


def job_create_defaults(user):
    defaults = {'created_by': user}
    target = friend_submission_target(user)
    if target and not is_staff_user(user):
        defaults['submitted_for'] = target
        defaults['source'] = 'friend'
    return defaults
