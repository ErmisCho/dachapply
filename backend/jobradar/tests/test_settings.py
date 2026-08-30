import importlib

from django.test import RequestFactory
from django.urls import clear_url_caches, resolve

from config.settings import normalize_smtp_password


def test_normalize_smtp_password_removes_gmail_app_password_group_spaces():
    assert normalize_smtp_password('smtp.gmail.com', 'abcd efgh ijkl mnop') == 'abcdefghijklmnop'


def test_normalize_smtp_password_preserves_non_gmail_password_spaces():
    password = 'keep spaces for another provider'
    assert normalize_smtp_password('smtp.example.com', password) == password


def test_normalize_smtp_password_preserves_non_app_password_shape():
    password = 'not a 16 char app password'
    assert normalize_smtp_password('smtp.gmail.com', password) == password


def test_local_root_redirects_to_vite_when_frontend_build_is_missing(settings, tmp_path):
    import config.urls

    original_debug, original_dist, original_url = settings.DEBUG, settings.FRONTEND_DIST, settings.FRONTEND_URL
    try:
        settings.DEBUG = True
        settings.FRONTEND_DIST = tmp_path / 'missing'
        settings.FRONTEND_URL = 'http://localhost:5173'
        importlib.reload(config.urls)
        clear_url_caches()

        request = RequestFactory().get('/')
        response = resolve('/', urlconf=config.urls).func(request)

        assert response.status_code == 302
        assert response.url == settings.FRONTEND_URL
        assert resolve('/admin', urlconf=config.urls).func(request).url == '/admin/'
    finally:
        settings.DEBUG, settings.FRONTEND_DIST, settings.FRONTEND_URL = original_debug, original_dist, original_url
        importlib.reload(config.urls)
        clear_url_caches()
