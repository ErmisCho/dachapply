"""TASK-237: read the actual posting body from a job's URL.

Stdlib only -- urllib + html.parser, the same shape as services/mailbox.py's urlopen calls. A job
link is not worth a new runtime dependency, and a whole-page text dump is the honest answer here:
this is not a readability engine, it shows the user what the page actually says so they can decide
whether the stored text (which may be a ChatGPT summary, not the posting) is worth replacing.

The URL is user data and this process runs inside a cloud network, so every hop is resolved and
checked before it is dialled -- an unguarded fetch here is an SSRF hole into the metadata service
and every private peer the container can see.
"""
import gzip
import io
import ipaddress
import json
import re
import socket
import zlib
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

TIMEOUT_SECONDS = 10
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
USER_AGENT = 'Mozilla/5.0 (compatible; DachApply/1.0; job posting reader)'
ALLOWED_CONTENT_TYPES = ('text/html', 'text/plain')

# Nothing inside these is page text; svg/head carry markup that reads as gibberish once flattened.
_SKIP_TAGS = {'script', 'style', 'noscript', 'svg', 'head', 'template'}
_BLOCK_TAGS = {
    'address', 'article', 'aside', 'blockquote', 'br', 'dd', 'div', 'dl', 'dt', 'fieldset',
    'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hr',
    'label', 'li', 'main', 'nav', 'ol', 'option', 'p', 'pre', 'section', 'table', 'td', 'th', 'tr',
    'ul',
}


class _Refused(Exception):
    """Something this fetcher will not return. Its message is what the user is shown."""


def _check_host(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https'):
        raise _Refused('Only http and https links can be opened.')
    if not parts.hostname:
        raise _Refused('That link has no address to open.')
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise _Refused('The address could not be resolved.') from None
    for info in infos:
        # ponytail: checked at resolve time, so a DNS rebind between this call and urllib's own
        # resolution still wins. Closing that needs a pinned-IP connector; the threat here is a
        # pasted job link, not a determined attacker with a rebinding server.
        address = ipaddress.ip_address(info[4][0])
        if (address.is_loopback or address.is_private or address.is_link_local
                or address.is_reserved or address.is_multicast or address.is_unspecified):
            raise _Refused('Refused: that link resolves to a private network address.')


class _GuardedRedirect(HTTPRedirectHandler):
    """urllib follows redirects silently, so the check above has to run on every hop too --
    a public host answering 302 to http://169.254.169.254/ is the whole trick."""

    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _decompress(raw, encoding):
    """urllib never decompresses, and a CDN gzips whether or not the request asked it to.

    Measured against https://www.python.org/jobs/ while building this: it answered
    `content-encoding: gzip` to a request carrying no Accept-Encoding at all, and decoding those
    bytes as text produced 10664 characters of U+FFFD that the endpoint would have presented as the
    real posting -- precisely the failure TASK-237 exists to stop. Capped on the way out as well:
    2 MB of gzip expands to gigabytes if the other end wants it to.
    """
    try:
        if encoding in ('', 'identity'):
            return raw
        if encoding == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as unzipped:
                return unzipped.read(MAX_BYTES)
        if encoding in ('deflate', 'zlib'):
            return zlib.decompressobj().decompress(raw, MAX_BYTES)
    except (OSError, EOFError, zlib.error):
        raise _Refused('The page arrived damaged and could not be unpacked.') from None
    raise _Refused(f'The page arrived {encoding}-compressed, which this reader cannot open.')


def _failed(error):
    return {'ok': False, 'text': '', 'error': error, 'final_url': ''}


def fetch_posting_text(url):
    url = (url or '').strip()
    try:
        _check_host(url)
        request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
        with build_opener(_GuardedRedirect).open(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            if content_type and not content_type.startswith(ALLOWED_CONTENT_TYPES):
                return _failed(f'The link returned {content_type}, not a readable web page.')
            # Read capped, never unbounded: the other end decides the size and a job board serving
            # a 4 GB file must not be able to decide this process's memory.
            raw = _decompress(response.read(MAX_BYTES + 1)[:MAX_BYTES], (response.headers.get('Content-Encoding') or '').lower().strip())
            charset = response.headers.get_content_charset() or 'utf-8'
            final_url = response.geturl()
    except _Refused as exc:
        return _failed(str(exc))
    except HTTPError as exc:
        return _failed(f'The site answered {exc.code} {exc.reason}.')
    except (TimeoutError, socket.timeout):
        return _failed(f'No response within {TIMEOUT_SECONDS} seconds.')
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return _failed(f'No response within {TIMEOUT_SECONDS} seconds.')
        if isinstance(exc.reason, socket.gaierror):
            return _failed('The address could not be resolved.')
        return _failed(f'The site could not be reached: {exc.reason}.')
    try:
        body = raw.decode(charset, errors='replace')
    except LookupError:
        body = raw.decode('utf-8', errors='replace')
    text = posting_text(body)
    if not text:
        return _failed('The page returned no readable text — it may require JavaScript.')
    return {'ok': True, 'text': text, 'error': '', 'final_url': final_url}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.json_ld = []
        self._skipping = 0
        self._in_json_ld = False

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and (dict(attrs).get('type') or '').strip().lower() == 'application/ld+json':
            self._in_json_ld = True
            self.json_ld.append('')
        if tag in _SKIP_TAGS:
            self._skipping += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'script':
            self._in_json_ld = False
        if tag in _SKIP_TAGS:
            self._skipping = max(0, self._skipping - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data):
        if self._in_json_ld:
            self.json_ld[-1] += data
        elif not self._skipping:
            self.parts.append(data)


def _parse(html):
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return parser


def _tidy(raw):
    lines = [' '.join(line.split()) for line in raw.splitlines()]
    # One blank line between blocks, never a run of them: the dump has to stay readable enough that
    # a human can compare it against the stored text at a glance.
    kept = []
    for line in lines:
        if line or (kept and kept[-1]):
            kept.append(line)
    return '\n'.join(kept).strip()


def extract_text(html):
    return _tidy(''.join(_parse(html).parts))


def _job_postings(node):
    """Every schema.org JobPosting in a JSON-LD value: a bare object, an array, or an @graph."""
    if isinstance(node, list):
        for item in node:
            yield from _job_postings(item)
    elif isinstance(node, dict):
        kind = node.get('@type')
        if kind == 'JobPosting' or (isinstance(kind, list) and 'JobPosting' in kind):
            yield node
        yield from _job_postings(node.get('@graph'))


_UNITS = {'HOUR': 'Stunde', 'DAY': 'Tag', 'WEEK': 'Woche', 'MONTH': 'Monat', 'YEAR': 'Jahr'}


def _salary_line(salary):
    if not isinstance(salary, dict):
        return ''
    value = salary.get('value')
    if not isinstance(value, dict):
        value = {'value': value}
    low, high, exact = value.get('minValue'), value.get('maxValue'), value.get('value')
    if low not in (None, '') and high not in (None, ''):
        amount = f'{low} - {high}'
    elif low not in (None, ''):
        amount = f'ab {low}'
    elif high not in (None, ''):
        amount = f'bis {high}'
    elif exact not in (None, ''):
        amount = str(exact)
    else:
        return ''
    line = f"Gehalt: {amount} {salary.get('currency') or ''}".rstrip()
    unit = str(value.get('unitText') or '').upper()
    return f'{line} / {_UNITS.get(unit, unit.lower())}' if unit else line


def _location_line(location):
    places = location if isinstance(location, list) else [location]
    names = []
    for place in places:
        address = place.get('address') if isinstance(place, dict) else None
        if isinstance(address, dict):
            country = address.get('addressCountry')
            if isinstance(country, dict):
                country = country.get('name')
            town = ' '.join(str(address.get(k) or '') for k in ('postalCode', 'addressLocality')).strip()
            name = ', '.join(str(p) for p in (address.get('streetAddress'), town, country) if p)
        elif isinstance(address, str):
            name = address
        else:
            name = place.get('name', '') if isinstance(place, dict) else ''
        if name and name not in names:
            names.append(name)
    return f"Ort: {'; '.join(names)}" if names else ''


def posting_text(html):
    """TASK-305: the job ad, not the careers page around it.

    A page carrying a schema.org JobPosting is read from that block -- title, the posting's own
    description, pay and location -- so site menus and share buttons never reach the text. Any
    page without one (or with JSON-LD that does not parse) keeps the whole-page dump.
    """
    parser = _parse(html)
    for block in parser.json_ld:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for posting in _job_postings(data):
            description = posting.get('description')
            if not isinstance(description, str):
                continue
            if '<' not in description:
                # A tag-less description is a stripped list: PORR serves 'Tiefe.Setup, Betrieb ...'
                # and 'aussieht.Dein Profil'. Break where a sentence ends hard against a capital.
                # ponytail: heuristic -- also splits a rare 'Ing.Max'; drop it if that shows up.
                description = re.sub(r'(?<=[a-zäöüß)][.!?:])(?=[A-ZÄÖÜ])', '<br>', description)
            body = extract_text(description)
            if not body:
                continue
            title = posting.get('title')
            lines = [title.strip() if isinstance(title, str) else '', body,
                     _salary_line(posting.get('baseSalary')), _location_line(posting.get('jobLocation'))]
            return '\n\n'.join(line for line in lines if line)
    return _tidy(''.join(parser.parts))


def normalized(text):
    """Whitespace-insensitive form -- the stored text and a freshly extracted page differ in
    wrapping long before they differ in content, so comparing raw bytes would always say 'differs'."""
    return ' '.join((text or '').split())
