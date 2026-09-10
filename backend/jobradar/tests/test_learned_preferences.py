"""TASK-225: bound the append-only learned-preferences field, without touching the stored field.

Hermetic by construction: no provider is launched, nothing reads or writes the real database or the
owner's real evidence/preferences (CLAUDE.md), and every field below is a fixture string built to
known, checkable lengths.
"""
import re

import pytest

from jobradar.services import cv_generator
from jobradar.services.cv_generator import bound_learned_preferences

TODAY_HEADER = 'LEARNED ACCOUNT APPLICATION PREFERENCES (newer entries override older ones):'


def _entries(n, length):
    """`n` fixture entries of exactly `length` chars each, oldest first -- the order the field stores
    them in (cv_tasks._learn_application_preference appends with `'\\n'.join([*lines, entry])`)."""
    return [f'- [CV] entry {i:03d} '.ljust(length, 'x') for i in range(n)]


def test_the_budget_holds_when_the_field_is_far_over_it():
    """AC1: bounded text stays within the stated budget, whatever the field's real size is."""
    entries = _entries(50, 500)  # 50 * 500 + 49 = 25,049 chars, well over any sane budget
    text, kept, total = bound_learned_preferences('\n'.join(entries), 16000)

    assert total == 50
    assert kept < total  # some were dropped, or the budget would not be doing anything
    assert len(text) <= 16000


def test_newest_first_kept_in_original_order():
    """AC1: 'the last K by budget', not by count -- and the returned text reads oldest-to-newest,
    the same order the field itself is in, not newest-first."""
    entries = _entries(10, 500)
    text, kept, total = bound_learned_preferences('\n'.join(entries), 2000)

    # Traced by hand: entry 9 (newest) costs 500 unconditionally (the floor), then two more entries
    # fit at 501 chars each (500 + the joining newline) before the fourth would push past 2000.
    assert kept == 3 and total == 10
    assert text.split('\n') == entries[7:10]


def test_the_floor_a_single_huge_entry_is_still_returned():
    """AC3: the newest entry is never dropped for being large -- that would silently discard the
    owner's most recent instruction, which matters more than any older one."""
    huge = 'y' * 5000
    text, kept, total = bound_learned_preferences(huge, 100)

    assert text == huge
    assert kept == total == 1


def test_the_floor_survives_even_when_it_forces_older_entries_out():
    older = '- [CV] short older preference that would otherwise fit easily.'
    newest = 'z' * 5000
    text, kept, total = bound_learned_preferences(f'{older}\n{newest}', 100)

    assert text == newest  # the floor entry alone, over budget and still kept
    assert kept == 1 and total == 2


def test_budget_leq_0_is_unbounded_todays_behaviour_verbatim():
    """The escape hatch AC5's regression flips: budget<=0 must reproduce exactly what the field
    embedded before this task, blank lines and all -- not a reconstruction from parsed entries."""
    field = '  \n' + '\n'.join(_entries(5, 50)) + '\n  '

    zero = bound_learned_preferences(field, 0)
    negative = bound_learned_preferences(field, -5)

    assert zero == negative == (field.strip(), 5, 5)


def test_hand_edited_junk_does_not_raise_and_is_not_duplicated_or_lost():
    """AC3: the profile UI edits this field as free text. Blank lines, missing '- [scope]' prefixes,
    and stray whitespace are expected input, not error cases -- and truncation must still count and
    join them correctly rather than inventing or repeating a line."""
    junk = ['- [CV] A scoped line.', '', '   ', '-[Letter]No space after dash.',
            '[CV] No dash at all.', 'A line with [brackets] and no prefix.',
            '   trailing whitespace line   ']
    raw = '\n'.join(junk)

    unbounded_text, kept, total = bound_learned_preferences(raw, 0)
    assert kept == total == 5  # the blank and whitespace-only lines are not entries
    # unbounded is raw.strip() verbatim (the escape hatch), so only the whole string's own ends are
    # trimmed -- the last entry's own trailing spaces go with it. Every entry's core text still
    # appears exactly once; none is invented or repeated.
    for marker in ('A scoped line', 'No space after dash', 'No dash at all', 'brackets', 'trailing whitespace line'):
        assert unbounded_text.count(marker) == 1

    truncated_text, kept, total = bound_learned_preferences(raw, 100)
    assert kept == 3 and total == 5
    assert truncated_text.count('trailing whitespace line') == 1
    assert truncated_text.count('No dash at all') == 1
    assert truncated_text.count('brackets') == 1
    assert 'scoped line' not in truncated_text  # correctly dropped by the budget, not duplicated in
    assert 'No space after dash' not in truncated_text


def test_under_budget_load_candidate_evidence_matches_today_byte_for_byte():
    """AC3: an account whose field already fits the budget sees no change at all -- the header and
    the embedded text are byte-identical to what load_candidate_evidence returned before this task."""
    learned = '- [CV] Keep summary short.\n- [Letter] Mention German fluency.'

    context = cv_generator.load_candidate_evidence('Profile notes here.', learned, 'stored evidence text')

    assert f'\n\n{TODAY_HEADER}\n{learned}' in context


def test_over_budget_header_states_the_most_recent_n_of_m(settings):
    """AC1: a model told a list is complete when it is not reasons from a false premise, so the
    header must say how many of how many once entries are actually left out."""
    settings.CODEX_LEARNED_PREFERENCES_BUDGET = 50
    entries = _entries(5, 40)  # 5*40 + 4 = 204 chars, over the 50-char budget
    learned = '\n'.join(entries)

    context = cv_generator.load_candidate_evidence('Profile.', learned, 'stored evidence text')

    assert TODAY_HEADER not in context
    match = re.search(r'LEARNED ACCOUNT APPLICATION PREFERENCES -- most recent (\d+) of (\d+) entries', context)
    assert match and match.group(2) == '5'
    assert int(match.group(1)) < 5


def test_load_candidate_evidence_actually_bounds_the_prompt(settings):
    """AC5, the falsification test: RED if the bound is ever bypassed in the wiring, not just absent
    from the helper. Proved by neutralising the call in load_candidate_evidence and re-running this
    test -- see the code-implementer report for the failing output; the call was then restored."""
    entries = _entries(50, 5000)  # 250,049 chars, far past the 16,000-char default budget
    huge = '\n'.join(entries)

    context = cv_generator.load_candidate_evidence('Profile.', huge, 'stored evidence text')

    section = re.search(r'LEARNED ACCOUNT APPLICATION PREFERENCES[^\n]*:\n(.*?)\n\nDACHAPPLY PROFILE NOTES:',
                        context, re.S)
    assert section, 'learned-preferences section not found in the built prompt'
    assert len(section.group(1)) <= settings.CODEX_LEARNED_PREFERENCES_BUDGET
    assert entries[-1] in section.group(1)  # the newest entry always survives (the floor)
    assert entries[0] not in section.group(1)  # the oldest is what the budget actually drops
