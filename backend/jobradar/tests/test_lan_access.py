"""TASK-226: reaching the local server from another device on the home network.

What these tests defend, criterion by criterion:
  AC2 -- the bind is configurable and loopback stays the default for anyone who does not opt in.
  AC3 -- with the flag on, the host's LAN address passes host validation and its :8000 origin passes
         CSRF, so a login POST from the phone is not refused.
  AC4 -- the firewall rule that has to exist is written down, verbatim, in the repository.
  Plus the obstacle the other three hide: with the frontend build missing, / redirects to
  FRONTEND_URL (http://localhost:5173), and a phone resolves that `localhost` to ITSELF. A perfect
  bind and a perfect ALLOWED_HOSTS still serve that device nothing.

TASK-241 adds the same thing by NAME, because an IP has to be looked up and moves with DHCP:
  AC2 -- the trusted names are derived from this host (hostname, FQDN, <hostname>.local) and
         DACHAPPLY_LAN_HOSTS still replaces detection outright.
  AC3 -- flag unset, the two lists are what they always were; DEBUG=False is never widened.
  AC4 -- a name that is not this host's is refused, and no wildcard ('*', '.local', '*.local') can
         reach either list.
  AC5 -- the README says which name forms work and what to do when a phone cannot resolve .local.

AC1 of both tasks -- a second physical device completing a login -- is NOT tested here and cannot
be: it needs the owner's phone or laptop. Nothing below is a substitute for it, and a request from
this host to its own LAN address or name would not be one either.

Hermetic: no socket is bound, nothing is listened on and no request leaves the machine. The two
calls that reach the OS (`lan_addresses()` and `lan_names()` with no override) are name lookups,
and they are asserted on as properties of whatever they return -- CI's interfaces and CI's hostname
are not the owner's, and both must pass.
"""
import importlib
import ipaddress
import re
import socket
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.test import RequestFactory
from django.urls import clear_url_caches, resolve

from config.settings import lan_addresses, lan_hosts, lan_names, lan_widened

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

# TASK-241, measured on the owner's machine 2026-09-21: socket.gethostname() -> 'Caren',
# socket.getfqdn() -> 'Caren.lan', so detection yields ['caren', 'caren.lan', 'caren.local'].
# Used below as a FIXTURE, never as an expectation of what detection returns here: CI's hostname is
# not 'Caren', so anything asserted about real detection is asserted as a property (see
# test_the_derived_names_are_this_hosts_own_and_never_a_pattern).
HOST_NAME = 'caren.local'


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


@pytest.mark.parametrize('sent_host', [
    f'{HOST_NAME}:8000',        # what a phone sends
    f'{HOST_NAME.upper()}:8000',   # ALLOWED_HOSTS matching is case-insensitive on BOTH sides
    'Caren.Local:8000',
    f'{HOST_NAME}.:8000',       # a fully-qualified name with the root dot browsers sometimes keep
    HOST_NAME,                  # and without the port, in case something reaches :80
])
def test_the_hosts_name_passes_host_validation_in_every_form_a_client_may_send_it(
        client, settings, db, sent_host):
    """TASK-241 AC3. Django lowercases the Host header and strips the port and one trailing dot in
    split_domain_port(), then lowercases the pattern in is_same_domain() -- so the single lowercase
    entry answers all of these. Driven through the real request path rather than read off that
    source, because 'Caren' vs 'caren' is exactly the kind of thing that looks right and still
    refuses the phone.
    """
    settings.ALLOWED_HOSTS, _ = lan_widened(DEFAULT_HOSTS, DEFAULT_ORIGINS, [HOST_NAME])

    assert client.get('/api/health/', HTTP_HOST=sent_host).status_code == 200


@pytest.mark.parametrize('sent_host', [
    'notcaren.local:8000',      # no suffix match
    'evil.caren.local:8000',    # no subdomain wildcard: the entry has no leading dot
    'caren.local.attacker.example:8000',
    'caren.lan:8000',           # a real form of THIS host, but not the one that was trusted
    'phone.local:8000',         # no blanket '.local'
])
def test_a_name_that_is_not_the_trusted_one_is_refused(client, settings, db, sent_host):
    """TASK-241 AC4, measured as a status code rather than argued from the list contents."""
    settings.ALLOWED_HOSTS, _ = lan_widened(DEFAULT_HOSTS, DEFAULT_ORIGINS, [HOST_NAME])

    assert client.get('/api/health/', HTTP_HOST=sent_host).status_code == 400


def test_a_login_post_from_the_hosts_name_is_csrf_accepted_and_a_lookalike_is_not(settings):
    """TASK-241 AC3. The name needs its http://<name>:8000 origin for the same reason the address
    does -- without it the board loads and the login POST is the thing that fails, which is the
    half-working state this task exists to avoid. CSRF_TRUSTED_ORIGINS is matched as an exact
    string (CsrfViewMiddleware.allowed_origins_exact), and browsers lowercase the host when they
    build Origin, which is why the stored form is lowercase.
    """
    settings.ALLOWED_HOSTS, settings.CSRF_TRUSTED_ORIGINS = lan_widened(
        DEFAULT_HOSTS, DEFAULT_ORIGINS, [HOST_NAME])

    assert f'http://{HOST_NAME}:8000' in settings.CSRF_TRUSTED_ORIGINS
    assert csrf_verdict(settings, f'{HOST_NAME}:8000', f'http://{HOST_NAME}:8000') is None
    assert csrf_verdict(settings, f'{HOST_NAME}:8000', 'http://evil.caren.local:8000').status_code == 403
    assert csrf_verdict(settings, f'{HOST_NAME}:8000', 'http://caren.local.evil:8000').status_code == 403


def test_a_name_is_added_to_both_lists_exactly_like_an_address_is():
    hosts, origins = lan_widened(DEFAULT_HOSTS, DEFAULT_ORIGINS, [LAN_IP, 'caren', HOST_NAME])

    assert hosts == DEFAULT_HOSTS + [LAN_IP, 'caren', HOST_NAME]
    assert origins == DEFAULT_ORIGINS + [f'http://{LAN_IP}:8000', 'http://caren:8000',
                                         f'http://{HOST_NAME}:8000']
    assert lan_widened(hosts, origins, ['caren']) == (hosts, origins)  # twice, no duplicates


def test_the_whole_mechanism_stays_gated_on_debug():
    """AC3's second half. Read out of the source for the same reason the launcher's bind is (see
    below): the gate is decided at import time, and the one thing that must never happen is a
    DEBUG=False process -- the deployed container -- being widened by a stray env var. Measured to
    hold as well: with DEBUG=0, DACHAPPLY_LAN_ACCESS=1 and DACHAPPLY_LAN_HOSTS=caren.local, a fresh
    import yields LAN_ACCESS False and ALLOWED_HOSTS exactly what ALLOWED_HOSTS was set to.
    """
    source = (ROOT / 'backend' / 'config' / 'settings.py').read_text(encoding='utf-8')

    assert "LAN_ACCESS = DEBUG and env_bool('DACHAPPLY_LAN_ACCESS', False)" in source
    assert source.count('lan_hosts(env_list(') == 1  # one call site, and it is inside `if LAN_ACCESS`


@pytest.mark.parametrize('override', [
    ['*'],                      # the thing that must never work
    ['*.local'],
    ['.local'],                 # TASK-241: a LEADING DOT is Django's subdomain wildcard, not a name
    ['0.0.0.0'],                # binds everything; as a Host header it means nothing
    ['127.0.0.1'],              # loopback is already in the list and is not a LAN address
    ['169.254.13.7'],           # what Windows keeps when DHCP failed
    ['8.8.8.8'],                # public -- and it must not come back in through the name filter
    ['not a name'],             # a space is in no hostname
    ['exa_mple', 'ünlaut'],     # nor an underscore, nor a non-ASCII character
    ['', '   '],
])
def test_nothing_outside_a_private_ipv4_or_a_name_can_get_in(override):
    """AC3's other half: no override widens either list to a wildcard or to anything unusable.
    A wholly unusable override raises rather than quietly widening nothing, because "configured and
    still refuses the phone" is the failure mode this task exists to remove.

    TASK-241 moved this raise from lan_addresses() to lan_hosts(), and the case that forced the
    move is 'not-an-address' -- which used to belong in the list above and is now simply a host
    name. One variable feeds both filters, so only an override that survives NEITHER is a typo.
    """
    with pytest.raises(Exception) as caught:
        lan_hosts(override)
    assert 'DACHAPPLY_LAN_HOSTS' in str(caught.value)


def test_a_usable_override_is_kept_and_the_junk_beside_it_is_dropped():
    assert lan_addresses([LAN_IP, '*', '8.8.8.8', ' 172.21.208.1 ']) == ['172.21.208.1', LAN_IP]


def test_an_override_replaces_detection_and_takes_addresses_and_names_together():
    """AC2. DACHAPPLY_LAN_HOSTS is the escape hatch for detection being wrong (a VPN, a second NIC,
    a name only the router knows), so it is trusted for what the operator typed -- exactly as it
    already is for addresses, which are likewise never checked against what this host holds. What
    it cannot do is smuggle in a pattern: '*', '*.local' and '.local' are dropped here, addresses
    that are public/loopback/link-local are dropped by lan_addresses, and an address spelled into
    the name slot is dropped rather than skipping those checks.
    """
    assert lan_hosts([LAN_IP, 'Caren', ' caren.local. ', '*', '*.local', '.local', '8.8.8.8',
                      'caren']) == [LAN_IP, 'caren', 'caren.local']


def test_the_derived_names_are_this_hosts_own_and_never_a_pattern():
    """AC2/AC4, asserted as a property: CI's hostname is not 'Caren'. What must hold everywhere is
    that every name is derived from THIS host's own hostname/FQDN, is lowercase, is free of
    duplicates, and is never something Django would read as a wildcard.
    """
    detected = lan_names()
    hostname = socket.gethostname().lower()

    assert detected == list(dict.fromkeys(detected))  # deduped, order preserved
    assert f"{hostname.split('.')[0]}.local" in detected  # the form a phone resolves over mDNS
    for name in detected:
        assert name == name.lower()
        assert not name.startswith('.') and '*' not in name
        assert re.fullmatch(r'[a-z0-9-]+(\.[a-z0-9-]+)*', name)
        # Derived from this host, not from anything else: every name is the hostname, the FQDN, or
        # the first label of the hostname plus .local.
        assert name in {hostname, socket.getfqdn().lower().rstrip('.'),
                        f"{hostname.split('.')[0]}.local"}


def test_an_address_never_reaches_the_two_lists_through_the_name_filter():
    """socket.getfqdn() can hand back an address when reverse DNS is odd. Addresses belong to
    lan_addresses(), which is where the private/loopback/link-local checks live; a literal arriving
    through the name path would skip all three, so it is dropped instead.
    """
    assert lan_names(['8.8.8.8', '127.0.0.1', '169.254.13.7', LAN_IP]) == []


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


def test_the_readme_says_which_name_forms_work_and_what_to_do_when_none_resolve():
    """TASK-241 AC5. The three forms are a server-side fact; whether a phone resolves any of them is
    not, so the workaround has to be written down rather than implied. Asserted on the README
    because that is where the owner will look at 9pm with a phone that says "cannot open page".
    """
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    names_section = readme[readme.index('### Which name forms work'):]

    for form in ['bare hostname', '.local', 'FQDN']:
        assert form in names_section
    assert 'no server change will fix it' in names_section
    assert 'hosts' in names_section and '192.168.8.130' in names_section
