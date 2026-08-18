"""TASK-115: parsing and masking for UserProfile.mailbox_calendar_ics_urls.

Deliberately its own module rather than living in services/mailbox.py -- a parallel session had
154 uncommitted lines in mailbox.py at the time this was written, and mailbox.py's own
calendar_busy_now()/_effective_*() will import parse_calendar_ics_urls from here once that
session's work lands.
"""
import re
from urllib.parse import urlsplit, urlunsplit

_BRACKET_STRIP_RE = re.compile(r'^\[|\]$')
_PRIVATE_TOKEN_RE = re.compile(r'private-[^/]+')
_MASK_MARKER = '••'  # the '••' bullets used by mask_calendar_ics_url below


def parse_calendar_ics_urls(raw):
    """AC8: turn stored/pasted text into a list of ICS URLs.

    Tolerates:
      - one bare URL
      - several separated by newlines and/or commas
      - a pasted bracketed list literal `[a, b, c]` -- including with a missing closing bracket,
        which is exactly the shape TASK-115 was filed over (someone naturally typed the several
        URLs as `[<url>, <url>, <url>`) -- and surrounding single/double quotes around each entry

    Getting this wrong fails open and silent: calendar_busy_now() treats a misparsed value as one
    URL, the fetch/parse raises, and the caller's fail-open design (TASK-109 AC7) swallows it
    without a trace. So this is deliberately permissive rather than validating strictly and erroring.
    """
    text = (raw or '').strip()
    if not text:
        return []
    text = _BRACKET_STRIP_RE.sub('', text).strip()
    urls = []
    for part in re.split(r'[\n,]+', text):
        url = part.strip().strip('\'"').strip()
        if url:
            urls.append(url)
    return urls


def mask_calendar_ics_url(url):
    """AC5/AC6 -- owner decision 2026-08-18: masked read, full write. Keeps the calendar-owner
    portion of the URL visible (host, path, the ical/<email> segment) so the right entry can be
    recognised and replaced, while the private-<hash> secret itself never leaves the server after
    being saved. Falls back to masking everything past the host for a URL that doesn't carry
    Google's private-<hash> shape, rather than ever returning an unrecognised secret verbatim.
    """
    url = (url or '').strip()
    if not url:
        return url
    masked, count = _PRIVATE_TOKEN_RE.subn(f'private-{_MASK_MARKER*4}', url)
    if count:
        return masked
    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        return urlunsplit((parts.scheme, parts.netloc, f'/{_MASK_MARKER*4}', '', ''))
    return _MASK_MARKER * 4


def mask_calendar_ics_urls_text(raw):
    """The GET-response shape: one masked URL per line, same layout the textarea edits."""
    return '\n'.join(mask_calendar_ics_url(url) for url in parse_calendar_ics_urls(raw))


def merge_calendar_ics_urls(existing_raw, incoming_raw):
    """Guards the masked-read/full-write round trip. The settings page always GETs
    mask_calendar_ics_urls_text()'s output into the textarea; if the owner saves the form without
    touching that field, the PATCH echoes the masked placeholders back verbatim. Storing that as-is
    would overwrite every real secret with '••••••••' and the feature would die silently -- exactly
    the failure mode this task exists to prevent, just moved from the parser to the write path.

    For an incoming entry that still carries the '••' mask marker, keep whichever previously-stored
    URL shares its visible prefix (everything before 'private-'); drop the entry if nothing matches
    rather than inventing a URL that was never stored.
    """
    existing = parse_calendar_ics_urls(existing_raw)
    incoming = parse_calendar_ics_urls(incoming_raw)
    resolved = []
    for url in incoming:
        if _MASK_MARKER in url:
            prefix = url.split('private-', 1)[0]
            match = next((e for e in existing if e.startswith(prefix)), None)
            if match:
                resolved.append(match)
            continue
        resolved.append(url)
    return '\n'.join(resolved)
