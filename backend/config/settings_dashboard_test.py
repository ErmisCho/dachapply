"""Disposable settings for the real-server integration harness, never production."""
import os
from .settings_test import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ['DACHAPPLY_TEST_DATABASE']}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ADMINS = []
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
CODEX_CV_WORKSPACE = os.environ.get('DACHAPPLY_TEST_WORKSPACE', CODEX_CV_WORKSPACE)
CODEX_CV_OPEN_OUTPUT_FOLDER = False
INSTALLED_APPS = ['jobradar.tests.runtime_app.IsolatedRuntimeConfig' if app == 'jobradar.apps.JobradarConfig' else app for app in INSTALLED_APPS]
