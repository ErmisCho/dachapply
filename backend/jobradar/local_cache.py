"""TASK-283.1: the logged-in user row and the profile's two board columns from an in-process cache.

Only on the pooled local runtime (settings adds CACHES['local'] under cached_sessions_enabled): one
threaded runserver process, so the signal receivers below invalidate the only copy there is. The
deployed site runs several gunicorn workers, where a save in one worker would leave the others
stale -- there CACHES has no 'local' alias and every function here falls through to the database.
Changes made by another process (the deployed site shares the Neon database, manage.py shell) are
not seen here until CACHES['local'] TIMEOUT expires.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.conf import settings
from django.core.cache import caches
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import UserProfile


def local_cache():
    """The process-local cache, or None where it is not enabled."""
    return caches['local'] if 'local' in settings.CACHES else None


def _user_key(user_id):
    return f'auth-user:{user_id}'


def _board_key(user_id):
    return f'board-settings:{user_id}'


class CachedModelBackend(ModelBackend):
    """ModelBackend whose get_user() -- the auth_user SELECT on every logged-in request -- reads the
    local cache. Django still compares the session's auth hash with the (cached) user's password
    hash, and set_password() + save() evicts the entry, so a password change logs other sessions out
    on their next request. Inactive users are never cached (ModelBackend.get_user returns None)."""

    def get_user(self, user_id):
        cache = local_cache()
        if cache is None:
            return super().get_user(user_id)
        user = cache.get(_user_key(user_id))
        if user is None:
            user = super().get_user(user_id)
            if user is not None:
                cache.set(_user_key(user_id), user)
        return user


def board_settings(user):
    """(board_sort_keys, board_status_order) for `user`; ('', '') without a profile."""
    cache = local_cache()
    values = cache.get(_board_key(user.pk)) if cache is not None else None
    if values is None:
        profile = UserProfile.objects.filter(user=user).only('board_sort_keys', 'board_status_order').first()
        values = (profile.board_sort_keys, profile.board_status_order) if profile else ('', '')
        if cache is not None:
            cache.set(_board_key(user.pk), values)
    return values


def _evict(key):
    cache = local_cache()
    if cache is not None:
        cache.delete(key)
        # Again after commit: a request that read the old row before this transaction committed may
        # have cached it in between.
        # ponytail: a reader that loads the old row before commit and stores it after this second
        # delete stays stale until TIMEOUT; versioned keys if that window ever matters.
        transaction.on_commit(lambda: cache.delete(key))


@receiver([post_save, post_delete], sender=get_user_model(), dispatch_uid='local_cache_user')
def _evict_user(sender, instance, **kwargs):
    _evict(_user_key(instance.pk))


@receiver([post_save, post_delete], sender=UserProfile, dispatch_uid='local_cache_board')
def _evict_board(sender, instance, **kwargs):
    _evict(_board_key(instance.user_id))
