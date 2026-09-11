"""TASK-226: reaching the local server from another device on the home network.

What these tests defend, criterion by criterion:
  AC2 -- the bind is configurable and loopback stays the default for anyone who does not opt in.
  AC3 -- with the flag on, the host's LAN address passes host validation and its :8000 origin passes
         CSRF, so a login POST from the phone is not refused.
  AC4 -- the firewall rule that has to exist is written down, verbatim, in the repository.
  Plus the obstacle the other three hide: with the frontend build missing, / redirects to
  FRONTEND_URL (http://localhost:5173), and a phone resolves that `localhost` to ITSELF. A perfect
  bind and a perfect ALLOWED_HOSTS still serve that device nothing.

AC1 -- a second physical device completing a login -- is NOT tested here and cannot be: it needs the
owner's phone or laptop. Nothing below is a substitute for it, and a request from this host to its
own LAN address would not be one either.

Hermetic: no socket is bound, nothing is listened on and no request leaves the machine. The single
call that reaches the OS (`lan_addresses()` with no override) is a name lookup, and it is asserted
on as a property of whatever it returns -- CI's interfaces are not the owner's, and both must pass.
"""
import importlib
import ipaddress
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.test import RequestFactory
from django.urls import clear_url_caches, resolve

from config.settings import lan_addresses, lan_widened

ROOT = Path(__file__).resolve().parents[3]

# What settings.py hands out with nothing opted in. Spelled literally rather than imported, so that
# a change to either default has to be made here too, deliberately.
DEFAULT_HOSTS = ['localhost', '127.0.0.1', 'testserver']
DEFAULT_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173',
                   'http://localhost:8000', 'http://127.0.0.1:8000']

# Measured on the owner's machine, 2026-09-11: `ipconfig` reports three IPv4 addresses. Only the
# first is one a phone can reach; the other two are WSL/Hyper-V virtual adapters, and
# socket.gethostbyname_ex returns them ahead of it. Hence "take them all", never "pick one".
LAN_IP = '192.168.8.130'
VIRTUAL_IPS = ['172.21.208.1', '172.22.48.1']


def test_the_suite_is_the_un_opted_in_path_and_nothing_widened_it():
    """AC2. The flag lives in the repo-root .env, which config.settings reads at import time, so a
    machine that has opted in would otherwise run a different suite from CI (which ships no .env) --
    the same portability trap config/settings_test.py already pins GMAIL_IMAP_USER against. If this
    ever fails, add `LAN_ACCESS = False` to config/settings_test.py rather than editing here.
    """
    assert django_settings.LAN_ACCESS is False
    # Django's own setup_test_environment() appends a second 'testserver' to the live list, so the
    # comparison is against everything that is NOT that -- which is the whole of the real default.
    assert [host for host in django_settings.ALLOWED_HOSTS if host != 'testserver'] == ['localhost', '127.0.0.1']
    assert django_settings.CSRF_TRUSTED_ORIGINS == DEFAULT_ORIGINS


def test_with_no_addresses_the_two_lists_come_back_untouched():
    """AC2. The opt-in is a no-op when it finds nothing, never a fallback to something wider."""
    assert lan_widened(DEFAULT_HOSTS, DEFAULT_ORIGINS, []) == (DEFAULT_HOSTS, DEFAULT_ORIGINS)


def test_every_address_of_the_host_is_added_as_a_host_and_as_an_http_8000_origin():
    """AC3. All three measured addresses, appended in place, with the defaults kept ahead of them."""
    hosts, origins = lan_widened(DEFAULT_HOSTS, DEFAULT_ORIGINS, [LAN_IP] + VIRTUAL_IPS)

    assert hosts == DEFAULT_HOSTS + [LAN_IP] + VIRTUAL_IPS
    assert origins == DEFAULT_ORIGINS + [f'http://{ip}:8000' for ip in [LAN_IP] + VIRTUAL_IPS]
    assert lan_widened(hosts, origins, [LAN_IP]) == (hosts, origins)  # applied twice, no duplicates


def test_the_lan_address_passes_django_host_validation(client, settings, db):
    """AC3, as far as this machine can take it: an HTTP request carrying the phone's Host header is
    answered rather than refused with a 400 DisallowedHost. It is still this host talking to itself,
    which is exactly why it is not evidence for AC1.
    """
    settings.ALLOWED_HOSTS, _ = lan_widened(DEFAULT_HOSTS, DEFAULT_ORIGINS, [LAN_IP])

    assert client.get('/api/health/', HTTP_HOST=f'{LAN_IP}:8000').status_code == 200
    assert client.get('/api/health/', HTTP_HOST='192.168.8.99:8000').status_code == 400


def csrf_verdict(settings, host, origin):
    """Run Django's own CsrfViewMiddleware over a token-carrying POST. None means it was accepted."""
    factory = RequestFactory()
    token = get_token(factory.get('/'))
    request = factory.post('/', {'csrfmiddlewaretoken': token}, HTTP_HOST=host, HTTP_ORIGIN=origin)
    request.COOKIES[settings.CSRF_COOKIE_NAME] = token
    middleware = CsrfViewMiddleware(lambda _request: HttpResponse())
    middleware.process_request(request)
    return middleware.process_view(request, lambda _request: HttpResponse(), (), {})


def test_a_login_post_from_the_lan_address_is_csrf_accepted_and_a_foreign_origin_is_not(settings):
    """AC3. The accepted case is same-origin -- host and Origin are both the LAN address on :8000 --
    which is precisely the shape the fix aims for: Django serves the app and takes the POST on one
    origin, so nothing about CSRF has to be relaxed. The refusal shows the widening is not a hole.
    """
    settings.ALLOWED_HOSTS, settings.CSRF_TRUSTED_ORIGINS = lan_widened(
        DEFAULT_HOSTS, DEFAULT_ORIGINS, [LAN_IP])

    assert f'http://{LAN_IP}:8000' in settings.CSRF_TRUSTED_ORIGINS
    assert csrf_verdict(settings, f'{LAN_IP}:8000', f'http://{LAN_IP}:8000') is None
    assert csrf_verdict(settings, f'{LAN_IP}:8000', 'http://attacker.example').status_code == 403


@pytest.mark.parametrize('override', [
    ['*'],                      # the thing that must never work
    ['*.local'],
    ['0.0.0.0'],                # binds everything; as a Host header it means nothing
    ['127.0.0.1'],              # loopback is already in the list and is not a LAN address
    ['169.254.13.7'],           # what Windows keeps when DHCP failed
    ['8.8.8.8'],                # public
    ['not-an-address'],
    ['', '   '],
])
def test_nothing_outside_a_private_ipv4_of_this_host_can_get_in(override):
    """AC3's other half: no override widens either list to a wildcard or to anything off this host.
    A wholly unusable override raises rather than quietly widening nothing, because "configured and
    still refuses the phone" is the failure mode this task exists to remove.
    """
    with pytest.raises(Exception) as caught:
        lan_addresses(override)
    assert 'DACHAPPLY_LAN_HOSTS' in str(caught.value)


def test_a_usable_override_is_kept_and_the_junk_beside_it_is_dropped():
    assert lan_addresses([LAN_IP, '*', '8.8.8.8', ' 172.21.208.1 ']) == ['172.21.208.1', LAN_IP]


def test_auto_detection_only_ever_reports_private_addresses_of_this_host():
    """Asserted as a property, not as an expected list: CI's interfaces are not the owner's."""
    detected = lan_addresses()

    assert '*' not in detected
    assert detected == sorted(set(detected))
    for address in detected:
        parsed = ipaddress.IPv4Address(address)
        assert parsed.is_private and not parsed.is_loopback and not parsed.is_link_local


def rebuild_urls(settings, dist, lan_access):
    import config.urls
    settings.DEBUG = True
    settings.FRONTEND_URL = 'http://localhost:5173'
    settings.FRONTEND_DIST = dist
    settings.LAN_ACCESS = lan_access
    importlib.reload(config.urls)
    clear_url_caches()
    return config.urls


@pytest.fixture
def urlconf():
    """Rebuild config.urls under the given settings, then put it back. Mirrors test_settings.py."""
    yield rebuild_urls
    import config.urls
    importlib.reload(config.urls)
    clear_url_caches()


def test_without_the_opt_in_the_root_url_still_redirects_to_vite(settings, urlconf, tmp_path):
    """AC2: the un-opted-in root URL keeps behaving exactly as it did."""
    urls = urlconf(settings, tmp_path / 'missing', False)
    response = resolve('/', urlconf=urls).func(RequestFactory().get('/'))

    assert response.status_code == 302
    assert response.url == 'http://localhost:5173'


def test_a_lan_device_is_never_redirected_to_a_host_relative_address(settings, urlconf, tmp_path):
    """The obstacle a correct bind and a correct ALLOWED_HOSTS both hide. http://localhost:5173 is
    resolved by the phone to the phone, so following it lands nowhere. With LAN access on and no
    build to serve, / says so with a 503 instead of sending the device into that dead end.
    """
    urls = urlconf(settings, tmp_path / 'missing', True)
    response = resolve('/', urlconf=urls).func(RequestFactory().get('/', HTTP_HOST=f'{LAN_IP}:8000'))

    assert response.status_code == 503
    assert 'localhost' not in response.content.decode()


def test_a_lan_device_is_served_the_app_itself_from_the_root_url(settings, urlconf, tmp_path):
    """How the LAN device actually gets an app: the launcher builds frontend/dist, so config.urls
    takes its SPA branch and Django serves index.html at / on :8000 -- same origin, no redirect.
    """
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<!doctype html><title>DACHApply</title>')
    settings.TEMPLATES = [{**django_settings.TEMPLATES[0], 'DIRS': [dist]}]

    urls = urlconf(settings, dist, True)
    response = resolve('/', urlconf=urls).func(RequestFactory().get('/', HTTP_HOST=f'{LAN_IP}:8000'))

    assert response.status_code == 200
    assert b'DACHApply' in response.render().content


def test_the_launcher_binds_loopback_unless_the_flag_says_otherwise():
    """AC2. Same static reading as test_local_runtime_launcher.py: the .cmd cannot be run here."""
    launcher = (ROOT / 'scripts' / 'dachapply-local-runtime.cmd').read_text()

    assert 'set "BIND=127.0.0.1:8000"' in launcher
    assert 'runserver !BIND!' in launcher
    assert 'runserver 0.0.0.0' not in launcher
    # 0.0.0.0 is reachable only through the flag, and the build that makes / serviceable comes first.
    assert launcher.index('DACHAPPLY_LAN_ACCESS') < launcher.index('set "BIND=0.0.0.0:8000"')
    assert launcher.index('npm run build') < launcher.index('runserver !BIND!')


def test_the_firewall_rule_is_written_down_verbatim_with_its_removal():
    """AC4. The port is closed on this machine today (measured: `netsh advfirewall firewall show
    rule name=all` matches nothing on 8000), so opting in means creating a rule, not editing one.
    A rule added this way is persistent, which is what makes the setup survive AC4's reboot.
    """
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')

    assert ('netsh advfirewall firewall add rule name="DACHApply LAN 8000" dir=in action=allow '
            'protocol=TCP localport=8000 profile=private remoteip=localsubnet') in readme
    assert 'netsh advfirewall firewall delete rule name="DACHApply LAN 8000"' in readme
