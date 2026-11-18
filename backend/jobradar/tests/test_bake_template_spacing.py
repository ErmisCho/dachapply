"""TASK-393: bake_template_spacing is dry-run by default, all-or-nothing per template, idempotent."""
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from jobradar.models import CvAsset

OLD1 = r'\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}'
NEW1 = r'\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-2pt}}'
OLD2 = r'\end{tabular*}\vspace{-7pt}'
NEW2 = r'\end{tabular*}\vspace{0pt}'
# Two copies of OLD2 (the "every copy" rule) and unrelated bytes around them.
SOURCE = f'head\r\n{OLD1}\r\nA{OLD2}\r\nB{OLD2}\r\n\\vspace{{-7pt}} tail\r\n'
EXPECTED = f'head\r\n{NEW1}\r\nA{NEW2}\r\nB{NEW2}\r\n\\vspace{{-7pt}} tail\r\n'

pytestmark = pytest.mark.django_db


def _run(*args):
    out = StringIO()
    call_command('bake_template_spacing', *args, stdout=out)
    return out.getvalue()


def _cv(source, key='en'):
    user = get_user_model().objects.create_user(f'u-{key}', password='pw')
    return CvAsset.objects.create(user=user, kind='cv', key=key, source=source)


def test_dry_run_prints_diff_and_writes_nothing():
    asset = _cv(SOURCE)
    out = _run()
    asset.refresh_from_db()
    assert asset.source == SOURCE
    assert 'pair 2: 2 match(es)' in out and f'+A{NEW2}' in out


def test_apply_writes_exact_bytes_then_is_idempotent():
    asset = _cv(SOURCE)
    _run('--apply')
    asset.refresh_from_db()
    assert asset.source == EXPECTED
    assert 'nothing to change' in _run('--apply')
    asset.refresh_from_db()
    assert asset.source == EXPECTED


def test_template_missing_one_old_is_skipped_with_reason():
    partial = f'x\n{OLD1}\n'
    asset = _cv(partial)
    out = _run('--apply')
    asset.refresh_from_db()
    assert asset.source == partial
    assert 'skipped: OLD of pair 2 not found' in out
