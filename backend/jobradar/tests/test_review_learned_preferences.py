"""TASK-229 AC3/AC5: a review list is only worth reading if its signals mean what they say.

Hermetic and invented by construction. Every entry below was written for this file: the real field is
the owner's career record and this repository is public (CLAUDE.md), so no real entry, term, employer
or number appears here. That rule bites harder in this test than in test_prompt_size.py, because the
command under test PRINTS entry text -- fixture text is the only text it may ever be handed in CI.

What each test defends is named in its docstring. The load-bearing ones are the two the brief calls
out: a label is never printed without the signal that produced it (AC3), and two entries that agree
are never reported as contradicting each other (AC5) -- a report that flagged every near-duplicate
would be worthless.
"""
import re
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from jobradar.models import UserProfile

# Deliberately thin: it has to corroborate a couple of fixture terms and nothing else, so that a term
# reported as absent is absent because the entry invented it, not because the evidence is short.
EVIDENCE = ('# Candidate Evidence\n## Professional Summary\n'
            'Backend engineer working in Python and Django on ingestion pipelines.\n'
            '## Needs Confirmation\nNothing outstanding.\n')

# One entry per shape the report has to tell apart. Invented names, invented numbers.
STYLE_ENTRY = '- [CV] Keep the professional summary to four lines and avoid adjectives in it.'
FACT_ENTRY = '- [CV] I led the Zephyr migration at Northwind Logistics from 2019, moving 12 TB of records.'
CORROBORATED_ENTRY = '- [CV] The Django work at the previous employer belongs in the skills block.'

# AC5. Two ways of agreeing that a naive rule would call a contradiction: the first pair opposes on
# verbs (keep / never) while naming the same size, the second asks for the same thing twice.
AGREE_ON_SIZE = ['- [CV] Keep the professional summary to four lines.',
                 '- [CV] The professional summary must stay at four lines, never longer.']
AGREE_ON_DIRECTION = ['- [CV] Always mention the deployment tooling in the skills block.',
                      '- [CV] The deployment tooling belongs in the skills block, include it.']
# And two ways of disagreeing: the same subject given two different sizes, and opposed verbs about it.
CONFLICT_ON_SIZE = ['- [CV] Keep the professional summary to four lines.',
                    '- [CV] Expand the professional summary to eight lines so it covers the tooling.']
CONFLICT_ON_DIRECTION = ['- [Letter] Shorten the closing paragraph as much as possible.',
                         '- [Letter] The closing paragraph should be expanded with a sentence about relocation.']

ENTRY = re.compile(r'^#(?P<index>\d+)\s+(?P<label>likely-FACT|likely-STYLE|unclear)\s')
PAIR = re.compile(r'^\s+#(?P<first>\d+) vs #(?P<second>\d+)\b')


@pytest.fixture
def account(db):
    user = User.objects.create_user('review@example.test', email='review@example.test')
    UserProfile.objects.create(user=user, candidate_evidence=EVIDENCE, learned_application_preferences='')
    return user


def review(user, entries, *args):
    """Run the command over exactly these entries, printing all of them unless a test says otherwise.

    update(), not save(): the field is planted without the profile's own save path running, so the
    byte-for-byte assertion below is about the COMMAND and nothing else.
    """
    if entries is not None:
        field = entries if isinstance(entries, str) else '\n'.join(entries)
        UserProfile.objects.filter(user=user).update(learned_application_preferences=field)
    out = StringIO()
    call_command('review_learned_preferences', '--user', user.email, '--limit', '0', *args, stdout=out)
    return out.getvalue()


def blocks(text):
    """{entry number: {'label': ..., 'style signal': ..., 'fact signal': ..., 'text': ...}}."""
    found, current = {}, None
    for line in text.splitlines():
        match = ENTRY.match(line)
        if match:
            current = found.setdefault(int(match['index']), {'label': match['label']})
        elif not line.startswith('    '):
            current = None  # the summary and contradiction sections are not part of an entry block
        elif current is not None and ':' in line:
            key, _, value = line.strip().partition(':')
            current[key.strip()] = value.strip()
    return found


def pairs(text):
    """{(earlier entry, later entry)} for every contradiction candidate the report printed."""
    matches = (PAIR.match(line) for line in text.splitlines())
    return {(int(match['first']), int(match['second'])) for match in matches if match}


def test_a_style_entry_and_a_fact_entry_get_different_labels(account):
    """AC3. The two shapes the field mixes have to come out the other side distinguishable at all."""
    entries = blocks(review(account, [STYLE_ENTRY, FACT_ENTRY]))

    assert entries[1]['label'] == 'likely-STYLE'
    assert entries[2]['label'] == 'likely-FACT'


def test_every_label_is_printed_with_the_signal_that_produced_it(account):
    """AC3, and the reason the command exists in this shape: a bare verdict is useless, because the
    owner cannot tell a good label from a bad one without seeing what the rule actually saw."""
    entries = blocks(review(account, [STYLE_ENTRY, FACT_ENTRY, CORROBORATED_ENTRY]))

    assert set(entries) == {1, 2, 3}
    for entry in entries.values():
        assert 'style signal' in entry and 'fact signal' in entry and 'text' in entry

    style, fact = entries[1], entries[2]
    assert 'keep' in style['style signal'] and 'avoid' in style['style signal']
    assert style['fact signal'] == 'none'          # 'four lines' is a size of document, not a claim
    assert fact['style signal'] == 'none'
    for signal in ('Zephyr', 'Northwind', 'Logistics', '2019', '12 tb'):
        assert signal in fact['fact signal']


def test_a_term_the_evidence_corroborates_is_not_a_fact_signal(account):
    """AC3. The whole point of the fact signal is 'this is asserted nowhere in the evidence', so a
    term that IS in the evidence must not be listed -- otherwise the signal is just a capital letter."""
    entry = blocks(review(account, [CORROBORATED_ENTRY]))[1]

    assert entry['fact signal'] == 'none'
    assert entry['label'] == 'unclear'  # neither signal fired; the report says so rather than guessing


def test_the_report_states_that_its_own_label_has_no_measured_accuracy(account):
    """AC3's second branch. The heuristic was never validated against a labelled sample -- there is
    none -- so the output has to say that where the owner reads it, not only in a commit message."""
    text = review(account, [STYLE_ENTRY, FACT_ENTRY])

    assert 'NO measured accuracy' in text
    assert 'NOT drawn automatically' in text


def test_entries_that_agree_are_not_reported_as_a_contradiction(account):
    """AC5, the distinction that makes the section worth printing. Both pairs below would trip a naive
    opposed-verbs rule: the first says 'keep' against 'never', the second is simply the same request
    twice. Neither is a contradiction, and a report that flagged them would be noise."""
    assert pairs(review(account, AGREE_ON_SIZE)) == set()
    assert pairs(review(account, AGREE_ON_DIRECTION)) == set()


def test_a_near_duplicate_is_counted_as_a_repeat_not_as_a_conflict(account):
    """AC5. cv_tasks dedups on an exact casefold match, so re-pasted instructions survive with a
    changed full stop. Those are duplicates -- report_cv_prompt_size --learned already counts them."""
    repeat = ['- [CV] Keep the professional summary to four lines.',
              'keep the professional summary to four lines']

    text = review(account, repeat)

    assert pairs(text) == set()
    assert '1 pair(s) were at least 90%' in text


def test_two_entries_that_conflict_about_a_size_are_reported_with_both_sizes(account):
    """AC5. Same subject, two different answers: the owner has to be shown which numbers disagree,
    because 'these two conflict' without the numbers is a claim they would have to re-derive."""
    text = review(account, CONFLICT_ON_SIZE)

    assert pairs(text) == {(1, 2)}
    assert '4 line vs 8 line' in text
    assert 'summari' in text or 'summary' in text  # the shared subject is named, not just the verdict


def test_two_entries_that_ask_for_opposite_things_are_reported_with_the_words(account):
    """AC5, the other axis: no numbers at all, one entry asks for less and the other for more of the
    same thing. The words that fired the rule are printed so a bad axis is visible immediately."""
    text = review(account, CONFLICT_ON_DIRECTION)

    assert pairs(text) == {(1, 2)}
    assert 'opposed on length' in text
    assert 'shorten' in text and 'expanded' in text


def test_the_stored_field_is_byte_identical_after_a_run(account):
    """The hard constraint. TASK-225 deliberately never writes this field -- it is the owner's only
    copy of their own instructions -- and a review tool that tidied it would undo that silently."""
    field = ('- [CV] Keep the professional summary to four lines.\n\n   \n'
             '- [Letter] Schreibe die Zusammenfassung kürzer, ohne Füllwörter.  \n'
             'Remember: no photo.\n')

    review(account, field)

    assert UserProfile.objects.get(user=account).learned_application_preferences == field


def test_hand_edited_and_malformed_lines_do_not_crash_it(account):
    """The profile UI edits this field as free text, so lines cv_tasks could not have written are
    expected rather than exceptional. Every one of these is a shape the report must survive."""
    hand_edited = ['- [CV] A scoped line, for contrast.', '', '   ', '- [] Empty scope.',
                   '-[Letter]No space after the dash.', '[CV] No dash at all.',
                   '- [CV + Letter] Wrong casing on the scope.', 'A line with [brackets] and no prefix.',
                   '- [CV] ', '!!!', '2019', '---', '- [CV] 100% and 12,500 EUR.']

    entries = blocks(review(account, hand_edited))

    assert set(entries) == set(range(1, 12))  # the blank and the whitespace-only line are not entries
    assert all('style signal' in entry and 'fact signal' in entry for entry in entries.values())


def test_it_pages_and_filters_so_a_long_field_can_be_reviewed_in_sittings(account):
    """43 entries in one wall of text is not a review list. --start/--limit page it, --label narrows
    it, and the counts underneath still describe the whole field rather than the page."""
    entries = [STYLE_ENTRY, FACT_ENTRY, CORROBORATED_ENTRY]

    assert set(blocks(review(account, entries, '--limit', '1'))) == {1}
    assert set(blocks(review(account, entries, '--limit', '1', '--start', '2'))) == {2}
    assert set(blocks(review(account, entries, '--label', 'fact'))) == {2}
    assert 'LABELS OVER ALL 3 ENTRIES' in review(account, entries, '--limit', '1')


def test_the_evidence_comes_from_the_file_when_the_profile_field_is_empty(account, settings, tmp_path):
    """The trap TASK-229 AC1 fell into first. UserProfile.candidate_evidence is EMPTY on the account
    this tool exists for, so load_candidate_evidence reads the configured FILE; comparing against the
    empty profile field reports everything uncorroborated, which is an artifact, not a finding."""
    evidence = tmp_path / 'evidence.md'
    evidence.write_text('# Candidate Evidence\nLed the Zephyr migration at Northwind Logistics.\n', encoding='utf-8')
    settings.CODEX_CANDIDATE_EVIDENCE_PATH = str(evidence)
    UserProfile.objects.filter(user=account).update(candidate_evidence='')

    text = review(account, [FACT_ENTRY])

    assert 'CODEX_CANDIDATE_EVIDENCE_PATH' in text
    assert 'Zephyr' not in blocks(text)[1]['fact signal']   # now corroborated by the file
    assert '12 tb' in blocks(text)[1]['fact signal']        # and the rest of the signal still fires


def test_it_refuses_rather_than_comparing_against_nothing(account, settings):
    """With no evidence at all, every term looks absent and every entry looks factual. That report
    would be worse than no report, so the command raises instead of printing it."""
    settings.CODEX_CANDIDATE_EVIDENCE_PATH = ''
    UserProfile.objects.filter(user=account).update(candidate_evidence='')

    with pytest.raises(CommandError, match='No candidate evidence'):
        review(account, [FACT_ENTRY])


def test_an_empty_field_and_an_unknown_account_are_handled_without_a_traceback(account):
    """CommandError rather than a traceback, and an empty field is a sentence rather than a crash."""
    assert 'nothing to review' in review(account, '')

    with pytest.raises(CommandError, match='No such account'):
        call_command('review_learned_preferences', '--user', 'nobody@example.test', stdout=StringIO())

