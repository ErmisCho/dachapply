"""TASK-224: the request breakdown is a command that can be re-run, not a number recorded once.

Hermetic by construction: no provider is launched (the command never runs one), no real database is
touched, and every size below comes from fixture strings chosen so the parts stay distinguishable.
The owner's real evidence file is untracked personal data (CLAUDE.md) and no test may depend on it.
"""
import re
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command

from jobradar.management.commands.report_cv_prompt_size import (CODEX_OVERHEAD_TOKENS, GENERATION_ATTEMPTS,
                                                                REPAIR_BLOCK, REPAIR_DIAGNOSTICS_BUDGET,
                                                                _near_duplicate_pairs, _repair_chars)
from jobradar.models import JobLead, UserProfile
from jobradar.services import cv_generator

# Deliberately lopsided the way the real prompt is: the learned preferences dwarf everything else,
# and the job description -- the only part that differs between two generations -- is one line.
LEARNED = 'Always keep the professional summary to four lines. ' * 200
EVIDENCE = '# Candidate Evidence\n' + 'Shipped an ingestion pipeline end to end. ' * 60
PROFILE = 'Backend engineer working in Python and Django. ' * 20
CV_SOURCE = '\\documentclass{article}\\begin{document}' + 'SECRET-CV-BODY ' * 50 + '\\end{document}'
JOB_TEXT = 'We are looking for an engineer with Python experience.'

# '  {label:<44}{chars:>10,}{tokens:>10,}{share:>8}', read back without depending on the widths.
ROW = re.compile(r'^ {2}(?P<label>.+?)\s+(?P<chars>--|[\d,]+)\s+(?P<tokens>[\d,]+)(\s+(?P<share>[\d.]+)%)?\s*$')
# TASK-225's tables carry an entries column in front of the chars one; three numbers, not two.
COUNT_ROW = re.compile(r'^ {2}(?P<label>.+?)\s+(?P<entries>[\d,]+)\s+(?P<chars>[\d,]+)\s+(?P<tokens>[\d,]+)'
                       r'(\s+(?P<share>[\d.]+)%)?\s*$')

# TASK-225 fixture: what the real field is, in miniature. Written the way
# cv_tasks._learn_application_preference writes it, plus the two things that writer cannot produce
# and the field still holds -- a hand-edited line (the profile UI takes free text) and a repeat that
# the exact-casefold dedup let through because the case and the full stop differ.
LEARNED_MIX_ENTRIES = [
    '- [CV] Keep the professional summary to four lines.',
    '- [CV] keep the professional summary to four lines',
    '- [Letter] Address the hiring manager by name when it is known.',
    '- [CV + letter] Use metric units in every measurement.',
    '- [CV] Put the newest role first and never invent a metric.',
    'Remember: no photo on the CV.',
] + [f'- [CV] Mention project {n} only when the posting asks for it.' for n in range(24)]
LEARNED_MIX = '\n'.join(LEARNED_MIX_ENTRIES)  # 30 entries: 27 [CV], 1 [Letter], 1 [CV + letter], 1 hand-edited


@pytest.fixture
def account(db, cv_assets):
    user = User.objects.create_user('prompt-size@example.test', email='prompt-size@example.test')
    UserProfile.objects.create(user=user, candidate_profile=PROFILE, candidate_evidence=EVIDENCE,
                               learned_application_preferences=LEARNED)
    JobLead.objects.create(company='Firma', title='AI Engineer', raw_description=JOB_TEXT, created_by=user)
    cv_assets(user, cv_source=CV_SOURCE)
    return user


def report(user, *args):
    out = StringIO()
    call_command('report_cv_prompt_size', '--user', user.email, *args, stdout=out)
    return out.getvalue()


def chars(text):
    """{label: characters} for every table row the report printed."""
    rows = (ROW.match(line) for line in text.splitlines())
    return {row['label']: int(row['chars'].replace(',', '')) for row in rows if row and row['chars'] != '--'}


def tokens(text):
    rows = (ROW.match(line) for line in text.splitlines())
    return {row['label']: int(row['tokens'].replace(',', '')) for row in rows if row}


def counted(text):
    """{label: (entries, chars)} for every TASK-225 table row the report printed."""
    rows = (COUNT_ROW.match(line) for line in text.splitlines())
    return {row['label']: (int(row['entries'].replace(',', '')), int(row['chars'].replace(',', '')))
            for row in rows if row}


def learned_report(user, *args):
    """The --learned section run against the TASK-225 fixture field rather than the one-line one."""
    UserProfile.objects.filter(user=user).update(learned_application_preferences=LEARNED_MIX)
    return report(user, '--learned', *args)


def test_the_parts_add_up_to_the_prompt_and_the_biggest_one_is_named(account):
    """AC1. The table is only worth reading if the components account for the whole prompt."""
    sizes = chars(report(account))
    parts = ['learned application preferences', 'candidate evidence (after compaction)',
             'DACHApply profile notes', 'mandatory application adaptation rules',
             'job description (the only per-job part)', 'prompt scaffolding, headers, evaluation JSON']

    assert sum(sizes[part] for part in parts) == sizes['TOTAL']
    assert max(parts, key=lambda part: sizes[part]) == 'learned application preferences'
    assert sizes['learned application preferences'] == len(LEARNED.strip())
    assert sizes['job description (the only per-job part)'] == len(JOB_TEXT)


def test_a_failed_generation_is_three_prompts_plus_two_repair_blocks(account):
    """AC4. One attempt is not what a failure costs: the prompt is re-sent whole, and grows."""
    text = report(account)
    sizes, counts = chars(text), tokens(text)
    prompt, repair = sizes['TOTAL'], _repair_chars(1)

    assert sizes['attempt 1: the prompt above'] == prompt
    assert sizes['attempt 2: the prompt + a repair block'] == prompt + repair
    assert sizes['attempt 3: the prompt + a repair block'] == prompt + repair
    assert sizes['prompt subtotal'] == GENERATION_ATTEMPTS * prompt + (GENERATION_ATTEMPTS - 1) * repair
    # The CLI's own system prompt is a token count, not characters, and is paid once per attempt
    # because every attempt is a separate run.
    assert counts[f'+ codex system prompt & tools, {GENERATION_ATTEMPTS} x {CODEX_OVERHEAD_TOKENS:,}'] == GENERATION_ATTEMPTS * CODEX_OVERHEAD_TOKENS
    assert sizes[f'+ template reads, {GENERATION_ATTEMPTS} x each file'] == GENERATION_ATTEMPTS * len(CV_SOURCE)


def test_the_retry_arithmetic_still_matches_cv_generator():
    """The command restates three things it cannot import, because they live inside a function body.

    If the retry loop, the diagnostics budget or the repair text is ever edited, the reported cost of
    a failed generation goes quietly wrong. This is the alarm.
    """
    source = Path(cv_generator.__file__).read_text(encoding='utf-8')
    assert f'for attempt in range({GENERATION_ATTEMPTS})' in source
    assert f'failure.diagnostics[-{REPAIR_DIAGNOSTICS_BUDGET}:]' in source

    literal = re.search(r"repair=f'''(.*?)''' if failure", source, re.S).group(1)
    assert (literal.replace('\\n', '\n')
                   .replace('{failure.summary}', '{summary}')
                   .replace(f'{{failure.diagnostics[-{REPAIR_DIAGNOSTICS_BUDGET}:]}}', '{diagnostics}')) == REPAIR_BLOCK


def test_no_evidence_cv_or_profile_text_reaches_the_report(account):
    """AC7 floor. This measures the owner's personal career data; sizes are the finding, text is not.

    Covers the TASK-225 section too: it reads every learned entry and must still print none of them,
    not truncated and not as a sample -- the duplicates it finds are reported by count, not quoted.
    """
    text = learned_report(account, '--letter')
    for secret in ('professional summary to four lines', 'ingestion pipeline', 'SECRET-CV-BODY',
                   'working in Python and Django', JOB_TEXT, 'hiring manager', 'metric units',
                   'no photo', 'Mention project', 'newest role first'):
        assert secret not in text
    assert 'Firma' in text and 'AI Engineer' in text  # the job it measured is still identifiable


def test_the_learned_breakdown_is_opt_in(account):
    """It is four tables answering a different question, so the default report stays one screen."""
    assert 'LEARNED APPLICATION PREFERENCES' not in report(account)
    assert 'LEARNED APPLICATION PREFERENCES' in learned_report(account)


def test_every_entry_is_counted_and_the_scope_split_is_right(account):
    """TASK-225 AC1/AC2. A bound cannot be chosen without knowing how many entries there are and how
    they are scoped -- and the totals have to be the field's real chars, joining newlines included."""
    rows = counted(learned_report(account))
    by_scope = {'- [CV]': LEARNED_MIX_ENTRIES[:2] + LEARNED_MIX_ENTRIES[4:5] + LEARNED_MIX_ENTRIES[6:],
                '- [Letter]': LEARNED_MIX_ENTRIES[2:3],
                '- [CV + letter]': LEARNED_MIX_ENTRIES[3:4],
                'unscoped (hand-edited)': LEARNED_MIX_ENTRIES[5:6]}

    assert rows['all (no cap at all)'] == (30, len(LEARNED_MIX))
    for label, entries in by_scope.items():
        assert rows[label] == (len(entries), len('\n'.join(entries)))
    assert sum(count for count, _ in (rows[label] for label in by_scope)) == 30


def test_hand_edited_lines_are_counted_rather_than_crashed_on(account):
    """The profile UI edits this field as free text, so lines the writer could not have produced are
    expected. Every one of these is a shape the parser must survive and report as unscoped."""
    hand_edited = ['- [CV] A scoped line, for contrast.', '', '   ', '- [] Empty scope.',
                   '-[Letter]No space after the dash.', '[CV] No dash at all.',
                   '- [CV + Letter] Wrong casing on the scope.', 'A line with [brackets] and no prefix.',
                   '- [CV] ']
    UserProfile.objects.filter(user=account).update(learned_application_preferences='\n'.join(hand_edited))

    rows = counted(report(account, '--learned'))

    assert rows['all (no cap at all)'][0] == 7  # the blank and the whitespace-only line are not entries
    assert rows['- [CV]'][0] == 2                 # the scoped one and the empty-bodied one
    assert rows['- [Letter]'][0] == 1             # no space after the dash is still the writer's shape
    assert rows['- [CV + letter]'][0] == 0        # wrong casing is a hand edit, not the writer
    assert rows['unscoped (hand-edited)'][0] == 4


def test_the_forgiving_dedup_finds_what_exact_casefold_matching_missed(account):
    """TASK-225 AC3. cv_tasks dedups on an exact casefold match of the whole line, so one changed
    full stop keeps a repeat. The survivor is the LAST copy: the prompt says newer entries win."""
    rows = counted(learned_report(account))
    repeat = LEARNED_MIX_ENTRIES[0]  # entry 1 says the same thing with different case and no full stop

    assert rows['after casefold+punctuation+space'] == (29, len(LEARNED_MIX) - len(repeat) - 1)
    assert rows['removed by that alone'] == (1, len(repeat) + 1)  # + the newline that joined it


def test_near_duplicates_are_found_past_exact_normalisation():
    """Unit, because the fixture above cannot produce a spelled-out number against a digit. difflib
    catches what normalisation alone cannot; the count is of entries, not of pairs."""
    assert _near_duplicate_pairs(['keep the summary to four lines', 'keep the summary to 4 lines',
                                  'always use metric units']) == (1, 3)
    # The ceiling is the O(n^2) guard, and it must be visible in the compared count rather than
    # silently shrinking the answer.
    assert _near_duplicate_pairs(['a', 'b', 'c', 'd'], ceiling=2)[1] == 2


def test_a_recency_cap_keeps_exactly_the_last_k_entries(account):
    """TASK-225 AC4. This is the table the bound gets chosen from, so its arithmetic is the finding:
    'last K' must be the last K entries' own chars, not an average or a share of the total."""
    rows = counted(learned_report(account))

    for cap in (10, 25):
        assert rows[f'last {cap}'] == (cap, len('\n'.join(LEARNED_MIX_ENTRIES[-cap:])))
    assert 'last 50' not in rows  # a cap that keeps all 30 is the "all" row, printed once
    assert rows['all (no cap at all)'] == (30, len(LEARNED_MIX))


def test_measuring_writes_nothing_to_the_workspace(account, settings, tmp_path):
    """AC6 floor. load_candidate_evidence refreshes a compaction snapshot on the workspace when the
    evidence comes from the file rather than the account; a report must not write it."""
    settings.CODEX_CV_WORKSPACE = str(tmp_path)
    UserProfile.objects.filter(user=account).update(candidate_evidence='')  # forces the file fallback

    report(account)

    assert not (tmp_path / '.dachapply-cache').exists()
    assert settings.CODEX_CV_WORKSPACE == str(tmp_path)  # blanked only for the load, then restored


def test_an_account_without_a_profile_is_refused_rather_than_given_one(db):
    """user_profile_settings() is a get_or_create; reporting must not create a row to report on."""
    user = User.objects.create_user('no-profile@example.test', email='no-profile@example.test')

    with pytest.raises(CommandError):
        call_command('report_cv_prompt_size', '--user', user.email, stdout=StringIO())

    assert not UserProfile.objects.filter(user=user).exists()


def test_the_report_measures_what_the_prompt_carries_not_what_the_field_stores(account, settings):
    """TASK-225 AC2. The bound lives in cv_generator; if the report kept measuring the raw field the
    two would disagree silently and the whole difference would vanish into the residual row."""
    entries = [f'- [CV] Preference number {index} ' + 'padding ' * 40 for index in range(60)]
    stored = '\n'.join(entries)
    UserProfile.objects.filter(user=account).update(learned_application_preferences=stored)
    settings.CODEX_LEARNED_PREFERENCES_BUDGET = 4000

    text = report(account)
    sizes = chars(text)
    parts = ['learned application preferences', 'candidate evidence (after compaction)',
             'DACHApply profile notes', 'mandatory application adaptation rules',
             'job description (the only per-job part)', 'prompt scaffolding, headers, evaluation JSON']

    assert sizes['learned application preferences'] <= 4000 < len(stored)
    assert sum(sizes[part] for part in parts) == sizes['TOTAL']  # still adds up, nothing hidden
    assert 'bounded at 4,000 chars' in text
    assert f'field still stores all {len(stored.strip()):,} chars' in text  # AC3: nothing was deleted


def test_an_unbounded_budget_is_reported_as_unbounded(account, settings):
    """The escape hatch has to be visible: a report that looked identical either way would let the
    bound be switched off without anyone noticing it had been."""
    settings.CODEX_LEARNED_PREFERENCES_BUDGET = 0

    text = report(account)

    assert 'UNBOUNDED' in text
    assert chars(text)['learned application preferences'] == len(LEARNED.strip())


def test_the_cap_table_names_the_rule_that_is_actually_in_force(account, settings):
    """AC1/AC2. The last-K table is the evidence a bound was chosen FROM; it is not the bound. A
    reader who took last-K for the live rule would predict the wrong prompt size."""
    entries = [f'- [CV] Preference number {index} ' + 'padding ' * 40 for index in range(60)]
    UserProfile.objects.filter(user=account).update(learned_application_preferences='\n'.join(entries))
    settings.CODEX_LEARNED_PREFERENCES_BUDGET = 4000

    rows = counted(report(account, '--learned'))

    assert 'IN FORCE: the character budget' in rows
    kept, size = rows['IN FORCE: the character budget']
    assert size <= 4000 and 0 < kept < 60


def test_no_share_column_can_read_negative_or_over_a_hundred(account, settings):
    """The bound made `prompt_chars` the BOUNDED prompt, so every share denominator that assumed the
    whole field was in there inverted. It printed -375.6% before this was caught, and a percentage
    that has gone negative is a table nobody can read -- so pin the invariant, not the arithmetic."""
    entries = [f'- [CV] Preference number {index} ' + 'padding ' * 40 for index in range(60)]
    UserProfile.objects.filter(user=account).update(learned_application_preferences='\n'.join(entries))
    settings.CODEX_LEARNED_PREFERENCES_BUDGET = 4000

    shares = [float(match['share']) for match in
              (re.compile(r'(?P<share>-?[\d.]+)%').search(line) for line in report(account, '--learned').splitlines())
              if match]

    assert shares, 'no share column was printed at all, so this test proved nothing'
    assert all(0 <= share <= 100 for share in shares), [share for share in shares if not 0 <= share <= 100]
