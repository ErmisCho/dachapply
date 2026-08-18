"""TASK-115 (platform-configuration half): the multi-calendar parser (AC8), the masked-read
serializer behaviour (AC5), and the proof that masking is verified against a real API response
rather than by reading the serializer (AC6). The reading/fetching side of TASK-115 (calendar_busy_now
honouring several URLs, the any-calendar-busy rule, partial-failure handling) lives in
services/mailbox.py and is out of scope here -- see the task's Implementation Notes.

Every URL below is obviously fake (calendar.google.com/.../fake*%40example.test/private-<fake>/...)
-- never a real ICS "secret address", per this task's own point.
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import UserProfile
from jobradar.services.calendar_ics import (
    mask_calendar_ics_url,
    mask_calendar_ics_urls_text,
    merge_calendar_ics_urls,
    parse_calendar_ics_urls,
)

FAKE_URL_1 = 'https://calendar.google.com/calendar/ical/fake1%40example.test/private-abc123def456/basic.ics'
FAKE_URL_2 = 'https://calendar.google.com/calendar/ical/fake2%40example.test/private-987654fedcba/basic.ics'
FAKE_URL_3 = 'https://calendar.google.com/calendar/ical/fake3%40example.test/private-000111222333/basic.ics'


@pytest.fixture
def owner(db):
    user = User.objects.create_user('calendar-ics-owner', password='pw')
    UserProfile.objects.create(user=user)
    return user


@pytest.fixture
def client(db, owner):
    c = APIClient(); c.force_authenticate(owner); c.user = owner; return c


# --- parse_calendar_ics_urls (AC8) --------------------------------------------------------------

def test_parse_bare_url():
    assert parse_calendar_ics_urls(FAKE_URL_1) == [FAKE_URL_1]


def test_parse_newline_separated():
    raw = f'{FAKE_URL_1}\n{FAKE_URL_2}\n{FAKE_URL_3}'
    assert parse_calendar_ics_urls(raw) == [FAKE_URL_1, FAKE_URL_2, FAKE_URL_3]


def test_parse_comma_separated():
    raw = f'{FAKE_URL_1}, {FAKE_URL_2}, {FAKE_URL_3}'
    assert parse_calendar_ics_urls(raw) == [FAKE_URL_1, FAKE_URL_2, FAKE_URL_3]


def test_parse_mixed_newline_and_comma():
    raw = f'{FAKE_URL_1},{FAKE_URL_2}\n{FAKE_URL_3}'
    assert parse_calendar_ics_urls(raw) == [FAKE_URL_1, FAKE_URL_2, FAKE_URL_3]


def test_parse_bracketed_list_literal_with_closing_bracket():
    raw = f'[{FAKE_URL_1}, {FAKE_URL_2}, {FAKE_URL_3}]'
    assert parse_calendar_ics_urls(raw) == [FAKE_URL_1, FAKE_URL_2, FAKE_URL_3]


def test_parse_bracketed_list_literal_missing_closing_bracket():
    # The exact shape the task was filed over: GMAIL_CALENDAR_ICS_URL=[<url>, <url>, <url>
    raw = f'[{FAKE_URL_1}, {FAKE_URL_2}, {FAKE_URL_3}'
    assert parse_calendar_ics_urls(raw) == [FAKE_URL_1, FAKE_URL_2, FAKE_URL_3]


def test_parse_quoted_entries():
    raw = f"'{FAKE_URL_1}', \"{FAKE_URL_2}\""
    assert parse_calendar_ics_urls(raw) == [FAKE_URL_1, FAKE_URL_2]


def test_parse_bracketed_and_quoted_together():
    raw = f"['{FAKE_URL_1}', '{FAKE_URL_2}']"
    assert parse_calendar_ics_urls(raw) == [FAKE_URL_1, FAKE_URL_2]


@pytest.mark.parametrize('raw', ['', '   ', None, '[]', "''"])
def test_parse_empty(raw):
    assert parse_calendar_ics_urls(raw) == []


# --- mask_calendar_ics_url (AC5) ------------------------------------------------------------------

def test_mask_keeps_owner_portion_hides_secret_hash():
    masked = mask_calendar_ics_url(FAKE_URL_1)
    assert masked.startswith('https://calendar.google.com/calendar/ical/fake1%40example.test/private-')
    assert masked.endswith('/basic.ics')
    assert 'abc123def456' not in masked
    assert '••••' in masked


def test_mask_urls_text_masks_every_line():
    raw = f'{FAKE_URL_1}\n{FAKE_URL_2}'
    masked = mask_calendar_ics_urls_text(raw)
    lines = masked.splitlines()
    assert len(lines) == 2
    assert 'abc123def456' not in masked and '987654fedcba' not in masked


def test_mask_falls_back_when_url_has_no_private_token():
    masked = mask_calendar_ics_url('https://example.test/some/other/calendar.ics')
    assert masked.startswith('https://example.test/')
    assert 'calendar.ics' not in masked  # never echo an unrecognised secret shape verbatim


# --- merge_calendar_ics_urls: the masked round trip (AC5) -----------------------------------------

def test_merge_resolves_masked_entries_back_to_the_real_stored_url():
    existing_raw = f'{FAKE_URL_1}\n{FAKE_URL_2}'
    masked_text = mask_calendar_ics_urls_text(existing_raw)
    assert merge_calendar_ics_urls(existing_raw, masked_text) == existing_raw


def test_merge_drops_a_masked_entry_with_no_matching_stored_url():
    merged = merge_calendar_ics_urls('', mask_calendar_ics_url(FAKE_URL_1))
    assert merged == ''


def test_merge_passes_through_real_new_urls_untouched():
    assert merge_calendar_ics_urls(FAKE_URL_1, FAKE_URL_2) == FAKE_URL_2


# --- API: masking proven against a real response body (AC6) ---------------------------------------

def test_profile_get_masks_calendar_urls_in_the_actual_response(client):
    raw = f'{FAKE_URL_1}\n{FAKE_URL_2}'
    saved = client.patch('/api/profile/', {'mailbox_calendar_ics_urls': raw}, format='json')
    assert saved.status_code == 200

    r = client.get('/api/profile/')
    assert r.status_code == 200
    body = r.content.decode('utf-8')
    # AC6: measured against the response body itself, not by reading the serializer.
    assert 'private-abc123def456' not in body
    assert 'private-987654fedcba' not in body
    # The calendar-owner portion stays visible so the right entry can be told apart from the others.
    assert 'fake1%40example.test' in body
    assert 'fake2%40example.test' in body
    urls = r.data['mailbox_calendar_ics_urls'].splitlines()
    assert len(urls) == 2
    assert all('••••' in u for u in urls)


def test_masked_value_saved_back_does_not_overwrite_the_real_secret(client):
    raw = f'{FAKE_URL_1}\n{FAKE_URL_2}'
    assert client.patch('/api/profile/', {'mailbox_calendar_ics_urls': raw}, format='json').status_code == 200

    masked = client.get('/api/profile/').data['mailbox_calendar_ics_urls']
    assert '••••' in masked

    # Simulates the real UI round trip: the form GETs masked values into the textarea, then PATCHes
    # the whole object back -- including this field unchanged -- because the owner edited something
    # else on the same page.
    resp = client.patch(
        '/api/profile/',
        {'mailbox_calendar_ics_urls': masked, 'mailbox_check_cadence_minutes': 30},
        format='json',
    )
    assert resp.status_code == 200

    stored = UserProfile.objects.get(user=client.user).mailbox_calendar_ics_urls
    assert 'private-abc123def456' in stored
    assert 'private-987654fedcba' in stored
    assert '••' not in stored


def test_pasting_a_new_full_url_replaces_the_stored_one(client):
    assert client.patch('/api/profile/', {'mailbox_calendar_ics_urls': FAKE_URL_1}, format='json').status_code == 200
    resp = client.patch('/api/profile/', {'mailbox_calendar_ics_urls': FAKE_URL_3}, format='json')
    assert resp.status_code == 200
    assert UserProfile.objects.get(user=client.user).mailbox_calendar_ics_urls == FAKE_URL_3
