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

    Every consumer routes through here, so restricting it is what removes a submitter's access to
    the recipient's later workflow everywhere at once. Staff/superusers keep administrative
    access, including legacy unowned rows.
    """
    qs = JobLead.objects.all()
    if not getattr(user, 'is_authenticated', False):
        return qs.none()
    if is_staff_user(user):
        return qs
    return qs.filter(owned_by(user)).distinct()


def submitted_away_jobs(user):
    """Jobs this user submitted for somebody else: proof of submission, never a workspace.

    Read-only and deliberately narrow -- callers must project these rows down to the submission
    itself (see views.submission_row). Empty for staff, whose accessible_jobs already covers
    everything in full.
    """
    if not getattr(user, 'is_authenticated', False) or is_staff_user(user):
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
