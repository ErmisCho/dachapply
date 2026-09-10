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
                                                                _repair_chars)
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
    """AC7 floor. This measures the owner's personal career data; sizes are the finding, text is not."""
    text = report(account, '--letter')
    for secret in ('professional summary to four lines', 'ingestion pipeline', 'SECRET-CV-BODY',
                   'working in Python and Django', JOB_TEXT):
        assert secret not in text
    assert 'Firma' in text and 'AI Engineer' in text  # the job it measured is still identifiable


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
