"""TASK-225: bound the append-only learned-preferences field, without touching the stored field.

Hermetic by construction: no provider is launched, nothing reads or writes the real database or the
owner's real evidence/preferences (CLAUDE.md), and every field below is a fixture string built to
known, checkable lengths.
"""
import re

import pytest

from jobradar.services import cv_generator
from jobradar.services.cv_generator import bound_learned_preferences, preference_exclusion

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
    # TASK-236 filters briefs out of the read path before the budget is spent; these 5,000-char
    # fixtures are exactly what it drops, so the two rules are switched off here to keep this test
    # about the budget alone. Its own coverage lives in the TASK-236 block below.
    settings.CODEX_PREFERENCE_MAX_CHARS = 0
    settings.CODEX_PREFERENCE_SKIP_TRUNCATED = False
    entries = _entries(50, 5000)  # 250,049 chars, far past the 16,000-char default budget
    huge = '\n'.join(entries)

    context = cv_generator.load_candidate_evidence('Profile.', huge, 'stored evidence text')

    section = re.search(r'LEARNED ACCOUNT APPLICATION PREFERENCES[^\n]*:\n(.*?)\n\nDACHAPPLY PROFILE NOTES:',
                        context, re.S)
    assert section, 'learned-preferences section not found in the built prompt'
    assert len(section.group(1)) <= settings.CODEX_LEARNED_PREFERENCES_BUDGET
    assert entries[-1] in section.group(1)  # the newest entry always survives (the floor)
    assert entries[0] not in section.group(1)  # the oldest is what the budget actually drops


# --- TASK-236: which entries may reach the prompt as durable preferences at all ------------------
# Every fixture below is invented neutral text at a measured LENGTH. The real field is the owner's
# career record and this repository is public, so only lengths and counts cross into this file.

def _entry(length, tail='x'):
    """One fixture entry of exactly `length` chars, ending in `tail` (last char decides 'mid-cut')."""
    return ('- [CV] fixture entry ' + 'x' * length)[:length - len(tail)] + tail


def test_a_preference_shaped_entry_reaches_the_prompt():
    """AC1: the entries this task exists to rescue are not touched by either rule."""
    assert preference_exclusion('- [CV] Keep the profile summary to three lines.') == ''
    assert preference_exclusion(_entry(961)) == ''  # the top of the preference-shaped cluster


def test_a_pasted_brief_is_excluded_and_says_why():
    reason = preference_exclusion(_entry(2546))

    assert reason == '2,546 chars: a pasted brief, not a preference'


def test_a_wire_truncated_entry_is_excluded_with_the_length_limit_off(settings):
    """AC3: the truncation rule is not the length rule wearing a hat. With no length limit at all,
    entries that hit the 5,000-char wire cap are still excluded -- and entries merely long are not."""
    settings.CODEX_PREFERENCE_MAX_CHARS = 0

    # The real cluster's ends: 4,888 (lowest) and 4,979 (highest), cut mid-token by the wire cap.
    assert preference_exclusion(_entry(4888)) == 'cut off at the 5,000-char input cap'
    assert preference_exclusion(_entry(4979, tail='{')) == 'cut off at the 5,000-char input cap'
    # The two nearest real entries BELOW the cluster, 4,106 and 3,832. Both also end mid-word, and
    # neither was truncated -- proximity to the cap, not the ending, is what separates them.
    assert preference_exclusion(_entry(4106)) == ''
    assert preference_exclusion(_entry(3832)) == ''
    # A long entry that ends on a sentence boundary was written that way, not cut.
    assert preference_exclusion(_entry(4950, tail='.')) == ''


def test_the_truncation_rule_can_be_switched_off_on_its_own(settings):
    settings.CODEX_PREFERENCE_MAX_CHARS = 0
    settings.CODEX_PREFERENCE_SKIP_TRUNCATED = False

    assert preference_exclusion(_entry(4888)) == ''


def test_a_brief_with_no_whitespace_to_collapse_is_still_seen_as_truncated(settings):
    """AC3 regression. views.py:2043 caps the INSTRUCTION; cv_tasks adds the `- [scope] ` prefix
    AFTERWARDS. A brief pasted as one single-spaced paragraph gives `' '.join(x.split())` nothing to
    collapse, so it stores at 5,000 PLUS the prefix -- past the cap rather than under it.

    Measuring the stored line instead of the body made the slack negative (-7, -11, -16 for `CV`,
    `Letter` and `CV + letter`) and the `0 <=` test then stopped seeing exactly the entries this rule
    exists to catch. The default length limit hid it by excluding them for another reason, which is
    the threshold dependence AC3 forbids -- hence MAX_CHARS=0 here.
    """
    settings.CODEX_PREFERENCE_MAX_CHARS = 0

    for scope in ('CV', 'Letter', 'CV + letter'):
        stored = f'- [{scope}] ' + 'x' * 5000  # body exactly at the cap, nothing collapsed away
        assert preference_exclusion(stored) == 'cut off at the 5,000-char input cap', scope


def test_a_sentence_ending_inside_a_quote_or_bracket_still_ended(settings):
    """A genuine entry near the cap that closes `... three lines."` or `...(see above).` ended on a
    sentence boundary; the closing mark is not a mid-cut ending. Only reachable within
    TRUNCATION_ALLOWANCE of the cap, so it shows on the AC3 path and nowhere else."""
    settings.CODEX_PREFERENCE_MAX_CHARS = 0

    for closing in ('."', ".'", '.)', '.]', '\u2026'):
        stored = '- [CV] ' + 'x' * (4900 - len(closing)) + closing
        assert preference_exclusion(stored) == '', closing

    # Same length, same window -- only the ending differs, so the ending is what is under test.
    assert preference_exclusion('- [CV] ' + 'x' * 4900) == 'cut off at the 5,000-char input cap'


def test_a_blank_or_odd_shaped_field_is_not_an_error():
    """The profile UI edits this field as free text, so blanks and unparseable shapes are input."""
    for odd in ('', '   ', None, '-[Letter]No space after dash.', 'no prefix at all'):
        assert preference_exclusion(odd) == ''

    junk = '  \n- [CV] A scoped line.\n\n   \nno prefix at all\n  '
    context = cv_generator.load_candidate_evidence('Profile.', junk, 'stored evidence text')
    assert 'A scoped line' in context and 'no prefix at all' in context


def test_excluded_entries_release_budget_instead_of_consuming_it(settings):
    """The filter runs BEFORE the budget, so a dropped brief buys room for the preferences behind
    it. RED if the two ever swap order -- which is how this test was falsified."""
    settings.CODEX_LEARNED_PREFERENCES_BUDGET = 700
    preferences = [f'- [CV] Fixture preference {i}.'.ljust(100, 'x')[:99] + '.' for i in range(5)]
    briefs = [_entry(1500 + i) for i in range(3)]
    field = '\n'.join(preferences + briefs)  # oldest first: the briefs are the newest entries

    with_filter = cv_generator.load_candidate_evidence('Profile.', field, 'stored evidence text')
    settings.CODEX_PREFERENCE_MAX_CHARS = 0
    settings.CODEX_PREFERENCE_SKIP_TRUNCATED = False
    without_filter = cv_generator.load_candidate_evidence('Profile.', field, 'stored evidence text')

    assert all(preference in with_filter for preference in preferences)  # all 5 fit once briefs go
    assert not any(brief in with_filter for brief in briefs)
    # Before: the newest brief alone eats the budget (the floor keeps it), and every preference is
    # starved out -- the measured 86.7%-brief prompt in miniature.
    assert briefs[-1] in without_filter
    assert not any(preference in without_filter for preference in preferences)


def test_both_settings_off_reproduce_the_prompt_byte_for_byte(settings):
    """AC6, exactly: not 'equivalently', identically. The pre-TASK-236 prompt is rebuilt from parts
    that never pass through the filter -- the same call and the same header the old code used --
    and compared as whole strings."""
    settings.CODEX_PREFERENCE_MAX_CHARS = 0
    settings.CODEX_PREFERENCE_SKIP_TRUNCATED = False
    settings.CODEX_LEARNED_PREFERENCES_BUDGET = 3000
    field = '  \n' + '\n'.join([_entry(4979), '', _entry(2546), '- [CV] Keep it short.']) + '\n  '

    escape_hatch = cv_generator.load_candidate_evidence('Profile.', field, 'stored evidence text')

    # Everything except the learned block is pinned by building the same prompt with an empty field.
    skeleton = cv_generator.load_candidate_evidence('Profile.', '', 'stored evidence text')
    marker = '\n\nDACHAPPLY PROFILE NOTES:'
    assert skeleton.count(marker) == 1
    bounded, kept, total = bound_learned_preferences(field, settings.CODEX_LEARNED_PREFERENCES_BUDGET)
    header = (TODAY_HEADER if kept >= total else
              f'LEARNED ACCOUNT APPLICATION PREFERENCES -- most recent {kept} of {total} entries (newer entries override older ones):')
    assert escape_hatch == skeleton.replace(marker, f'\n\n{header}\n{bounded}{marker}')

    # ...and the test is not vacuous: with the rules on, the same field builds a different prompt.
    settings.CODEX_PREFERENCE_MAX_CHARS = 1000
    settings.CODEX_PREFERENCE_SKIP_TRUNCATED = True
    assert cv_generator.load_candidate_evidence('Profile.', field, 'stored evidence text') != escape_hatch


def test_the_stored_field_is_never_touched_by_reading_it(settings):
    """AC2: no write path exists here. The string handed in is the string still held afterwards."""
    field = '\n'.join([_entry(4979), _entry(2546), '- [CV] Keep it short.'])
    before = field

    cv_generator.load_candidate_evidence('Profile.', field, 'stored evidence text')

    assert field == before
