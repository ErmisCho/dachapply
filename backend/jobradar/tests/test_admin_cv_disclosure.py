"""TASK-112: the can_generate_cv help_text must actually render on the admin page

where the flag is granted, not merely exist on the model. `can_generate_cv` is edited
through UserProfileInline (admin.py:22-31), which is an inline on the User admin -- so
this loads the User change page (not a standalone UserProfile page) and asserts the
disclosure text is present in the rendered HTML.
"""
from django.contrib.auth.models import User
from django.test import Client

from jobradar.models import UserProfile


def test_can_generate_cv_help_text_renders_on_user_admin_page(db):
    admin_user = User.objects.create_superuser('cv-disclosure-admin', 'admin@example.test', 'pw')
    target = User.objects.create_user('cv-disclosure-target', password='pw')
    # UserProfile is get_or_create()d elsewhere in the app; create it directly here so the
    # inline has a row to render fields for.
    UserProfile.objects.get_or_create(user=target)

    # config.middleware.SplitAdminSessionMiddleware keys the session cookie off the request
    # path ('admin_sessionid' under /admin, 'app_sessionid' elsewhere), so Client.force_login()
    # -- which only sets the default 'sessionid' cookie -- would authenticate the app session,
    # not the admin one. Logging in through the admin login view itself gets the right cookie.
    client = Client()
    login = client.post('/admin/login/', {'username': admin_user.username, 'password': 'pw'})
    assert login.status_code == 302, login.content.decode('utf-8')
    response = client.get(f'/admin/auth/user/{target.pk}/change/')

    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert "the site owner's private LaTeX templates" in html
    assert 'photograph' in html
    assert 'shared output directory' in html
