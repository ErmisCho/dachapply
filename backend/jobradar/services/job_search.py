"""TASK-362: the board's ?search= -- every word must match somewhere, umlaut spellings are equal, and a
small typo in a company or title word still finds the job.

Company/title/location are matched in Python over one values_list() of the already-filtered queryset
(a board is ~1-3k rows), because umlaut folding and typo distance are not portable between Postgres and
sqlite. The posting text stays in SQL: one boolean annotation per word, all in that same single query.
"""
import re
import unicodedata
from difflib import SequenceMatcher

from django.db.models import BooleanField, Case, ExpressionWrapper, IntegerField, Q, Value, When

POSTING_FIELDS = ('original_source_text', 'raw_description', 'url')
FUZZY_MIN_LEN = 4  # shorter words ("data", "ai", "sap") only match exactly
FUZZY_MIN_RATIO = 0.8  # one typo in a 6+ letter word; two-letter swaps in a 4-5 letter word do not pass
_TO_ASCII = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'}
_TO_UMLAUT = {'a': 'ä', 'o': 'ö', 'u': 'ü'}


def fold(text):
    """Lowercase, accents stripped and ae/oe/ue collapsed, so Zühlke, Zuehlke and Zuhlke compare equal."""
    text = unicodedata.normalize('NFKD', (text or '').lower().replace('ß', 'ss'))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'([aou])e', r'\1', text)


def _spellings(word):
    """The word as typed, with umlauts spelled out, and with ae/oe/ue written as umlauts -- for SQL icontains."""
    ascii_word = word
    for umlaut, spelled in _TO_ASCII.items():
        ascii_word = ascii_word.replace(umlaut, spelled)
    umlaut_word = re.sub(r'([aou])e', lambda m: _TO_UMLAUT[m[1]], ascii_word)
    # shortcut: all-or-nothing replacement, so a word mixing spelled-out and real umlauts in the posting misses there
    return {word, ascii_word, umlaut_word, umlaut_word.replace('ss', 'ß')}


def _posting_q(word):
    q = Q()
    for spelling in _spellings(word):
        for field in POSTING_FIELDS:
            q |= Q(**{f'{field}__icontains': spelling})
    return q


def _is_typo_of(word, tokens):
    return len(word) >= FUZZY_MIN_LEN and any(
        len(token) >= FUZZY_MIN_LEN and SequenceMatcher(None, word, token).ratio() >= FUZZY_MIN_RATIO for token in tokens)


def search_jobs(qs, query):
    """`qs` narrowed to jobs where every word of `query` matches company/title/location, the posting, or
    (typo-tolerant) a company/title word. One database query, however many jobs or words."""
    words = query.lower().split()
    if not words:
        return qs
    posting = {f'search_posting_{i}': ExpressionWrapper(_posting_q(w), output_field=BooleanField()) for i, w in enumerate(words)}
    folded_words = [fold(w) for w in words]
    exact, typo = set(), set()
    for pk, company, title, location, *in_posting in qs.prefetch_related(None).annotate(**posting).values_list('id', 'company', 'title', 'location', *posting):
        fields = fold(f'{company}\n{title}\n{location}')
        tokens = re.findall(r'\w+', fold(f'{company} {title}'))
        plain = [w in fields or hit for w, hit in zip(folded_words, in_posting)]
        if all(plain):
            exact.add(pk)
        elif all(ok or _is_typo_of(w, tokens) for w, ok in zip(folded_words, plain)):
            typo.add(pk)
    # search_typo: 0 exact, 1 typo-only; the board orders by it first, then by the owner's chosen order
    return qs.filter(id__in=exact | typo).annotate(search_typo=Case(When(id__in=typo, then=Value(1)), default=Value(0), output_field=IntegerField()))
