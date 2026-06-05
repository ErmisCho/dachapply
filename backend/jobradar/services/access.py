from django.db.models import Q

from jobradar.models import JobLead


def is_staff_user(user):
    return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))


def accessible_jobs(user):
    """Jobs a request user may read or mutate.

    Regular users may access jobs they created and jobs explicitly submitted for
    them by approved friend submitters. Staff/superusers keep administrative
    access, including legacy unowned rows.
    """
    qs = JobLead.objects.all()
    if not getattr(user, 'is_authenticated', False):
        return qs.none()
    if is_staff_user(user):
        return qs
    return qs.filter(Q(created_by=user) | Q(submitted_for=user)).distinct()


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
