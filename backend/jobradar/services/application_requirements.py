"""TASK-280.1: the one normaliser for JobLead.application_requirements.

The analysis model classifies; this module checks its evidence. Every write path (pasted analysis
JSON, data-portability import, the owner's edit) goes through normalize_application_requirements,
so a requirement can only be stored as required/preferred/optional/not_accepted, or an application
language as requested, when its quote actually occurs in the job's stored posting text.

Stored shape:
{"posting_language": "en"|"de"|"mixed"|"unclear",
 "application_language": "en"|"de"|"",
 "application_language_quote": "...",
 "documents": [{"type": "cover_letter"|"motivation_letter"|"short_message"|"other",
                "name": "...", "status": "required"|"preferred"|"optional"|"not_accepted"|"not_mentioned"|"unclear",
                "quote": "..."}],
 "source": "analysis"|"owner"}
"""
import re

POSTING_LANGUAGES = ('en', 'de', 'mixed', 'unclear')
APPLICATION_LANGUAGES = ('en', 'de')
DOCUMENT_TYPES = ('cover_letter', 'motivation_letter', 'short_message', 'other')
DOCUMENT_STATUSES = ('required', 'preferred', 'optional', 'not_accepted', 'not_mentioned', 'unclear')
# Statuses that claim the posting says something; each needs a quote found in the posting text.
EXPLICIT_STATUSES = ('required', 'preferred', 'optional', 'not_accepted')
SOURCES = ('analysis', 'owner')

_QUOTE_CHARS = str.maketrans({c: "'" for c in '"“”„‟«»‘’‚‛‹›`´'}
                             | {c: '-' for c in '‐‑‒–—−'}
                             | {'­': None})


def _match_text(text):
    """Whitespace, case, quote marks and dashes do not count as differences; words do."""
    return re.sub(r'\s+', ' ', str(text or '').translate(_QUOTE_CHARS).casefold()).strip()


def _quote_in(quote, posting):
    # A model often wraps the quote in quote marks or ends it with a period the posting has mid-sentence.
    # Whole words only, so a fragment like "x" cannot hide inside "explaining".
    # ponytail: proves the words are in the posting, not that they mean the status; the prompt owns that.
    needle = _match_text(quote).strip(" '.…")
    return bool(needle) and re.search(rf'(?<!\w){re.escape(needle)}(?!\w)', posting) is not None


def _enum(value, allowed, default):
    value = str(value or '').strip().lower()
    return value if value in allowed else default


def normalize_application_requirements(value, job, source=None):
    """Return the stored shape for `value`, verified against `job`'s posting text.

    `source` forces the origin: the analysis importer passes 'analysis' so pasted JSON cannot
    claim to be an owner edit; None keeps the value's own (data-portability round-trips).
    Owner-sourced explicit statuses are the owner's own knowledge and skip the quote check; their
    enums are still enforced. Anything that is not a non-empty dict normalises to {} (not analysed).
    """
    if not isinstance(value, dict) or not value:
        return {}
    source = _enum(source or value.get('source'), SOURCES, 'analysis')
    # The same stored posting the app shows and prompts with: original_source_text, else raw_description.
    posting = _match_text(job.source_text)
    verify = source == 'analysis'

    def evidenced(quote):
        return not verify or _quote_in(quote, posting)

    application_language = _enum(value.get('application_language'), APPLICATION_LANGUAGES, '')
    language_quote = str(value.get('application_language_quote') or '').strip()
    if application_language and not evidenced(language_quote):
        application_language = ''
    if not application_language:
        language_quote = ''

    merged = {}  # (type, name) -> item; first occurrence keeps its position
    for raw in value.get('documents') or []:
        if not isinstance(raw, dict):
            continue
        doc_type = _enum(raw.get('type'), DOCUMENT_TYPES, 'other')
        name = str(raw.get('name') or '').strip() if doc_type == 'other' else ''
        status = _enum(raw.get('status'), DOCUMENT_STATUSES, 'unclear')
        quote = str(raw.get('quote') or '').strip()
        if status in EXPLICIT_STATUSES and not evidenced(quote):
            status, quote = 'unclear', ''
        if status == 'not_mentioned' or (quote and not evidenced(quote)):
            quote = ''
        key = (doc_type, name.casefold())
        item = {'type': doc_type, 'name': name, 'status': status, 'quote': quote}
        previous = merged.get(key)
        if previous is None or previous['status'] == 'not_mentioned':
            merged[key] = item
        elif status not in ('not_mentioned', previous['status']):
            # Two different answers for the same document: say so rather than pick one.
            merged[key] = {**previous, 'status': 'unclear', 'quote': ''}

    return {
        'posting_language': _enum(value.get('posting_language'), POSTING_LANGUAGES, 'unclear'),
        'application_language': application_language,
        'application_language_quote': language_quote,
        'documents': list(merged.values()),
        'source': source,
    }
