"""Integration-only app config: prevent disposable compile tests changing the owner's clipboard."""
from jobradar.apps import JobradarConfig


class IsolatedRuntimeConfig(JobradarConfig):
    def ready(self):
        super().ready()
        from jobradar.services import cv_tasks
        cv_tasks._copy_to_clipboard = lambda text: False
