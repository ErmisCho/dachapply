from types import SimpleNamespace

import pytest

from jobradar.services import cv_generator as cg

BASE_LETTER = r'''\documentclass{letter}
\begin{document}
% OLD: this comment mentions old text and must be ignored
\hfill Wien, \today \\
Sehr geehrte Damen und Herren,
Body.
\end{document}
'''
BASE_CV = '\\documentclass{article}\n\\begin{document}\n%  OLD: a comment\n%  NEW: another\n\\section{Profile} Engineer\n\\end{document}\n'


def _prompt():
    job = SimpleNamespace(evaluations=SimpleNamespace(first=lambda: None), company='C', title='T', location='L', language_requirements='', source_text='x')
    return cg._prompt(job, 'profile', 'cv.tex', 'letter.tex', 'en', 'en')


def test_prompt_carries_new_rules():
    prompt = _prompt()
    assert '"Senior"' in prompt
    assert 'at least two of the posting' in prompt
    assert 'own terms' in prompt
    assert 'never write a literal date' in prompt
    assert 'contact person' in prompt
    assert 'OLD:, NEW:' in prompt


@pytest.mark.parametrize('literal', ['Wien, 16. Oktober 2026', 'Vienna, 16 November 2026', 'Vienna, November 16, 2026'])
def test_literal_date_restored_to_today(literal):
    generated = BASE_LETTER.replace('Wien, \\today', literal)
    restored = cg._restore_today(BASE_LETTER, generated)
    assert restored.splitlines()[3] == f'\\hfill {literal.split(",")[0]}, \\today \\\\'


def test_template_date_line_untouched_and_body_dates_kept():
    assert cg._restore_today(BASE_LETTER, BASE_LETTER) == BASE_LETTER
    body = BASE_LETTER.replace('Body.', 'Seit dem Treffen am 16. Oktober 2026, danke.')
    assert cg._restore_today(BASE_LETTER, body) == body


def test_no_restore_when_template_has_no_today():
    plain = BASE_LETTER.replace('\\today', 'Wien, 1. Mai 2026')
    assert cg._restore_today(plain, plain) == plain


@pytest.mark.parametrize('leak', ['OLD: x', 'NEW: y', 'FINAL VALIDATION', 'CHANGE 2 \u2014 skills', 'FILE 1: cv.tex'])
def test_leaked_instruction_raises_recoverable(leak):
    tex = BASE_CV.replace('\\section', leak + '\n\\section')
    with pytest.raises(cg.RecoverableGenerationError):
        cg._reject_leaked_instructions('cv_tex', tex)


def test_commented_markers_and_real_templates_pass():
    cg._reject_leaked_instructions('cv_tex', BASE_CV)
    cg._reject_leaked_instructions('letter_tex', BASE_LETTER)
