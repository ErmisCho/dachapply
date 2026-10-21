"""TASK-332: a LaTeX compile failure names the actual error instead of opening on package noise."""
import shutil

import pytest

from jobradar.services.cv_generator import RecoverableGenerationError, _compile_pdf, latex_error

LOG = 'Package hyperref Info: Driver (autodetected): hpdftex.\n' * 40 + (
    '! Undefined control sequence.\n'
    'l.123 \\resumeItm\n'
    '                {Built things}\n'
    'Here is how much of TeX\'s memory you used:\n')


def test_the_error_and_its_line_come_first():
    reason, block = latex_error(LOG, 1)
    assert reason == 'Undefined control sequence (line 123)'
    assert block.splitlines() == ['! Undefined control sequence.', 'l.123 \\resumeItm']


def test_a_log_without_an_error_line_says_so():
    reason, block = latex_error('Package hyperref Info: Driver (autodetected): hpdftex.\n', 3)
    assert reason == 'pdflatex stopped without an error message (exit code 3)' and 'exit code 3' in block


@pytest.mark.skipif(not shutil.which('pdflatex'), reason='needs pdflatex')
def test_a_real_failing_document_reports_its_error(tmp_path):
    (tmp_path / 'cv.tex').write_text('\\documentclass{article}\n\\begin{document}\n\\resumeItm{x}\n\\end{document}\n', encoding='utf-8')
    with pytest.raises(RecoverableGenerationError) as failure:
        _compile_pdf(tmp_path, 'cv.tex', True)
    assert failure.value.summary == 'LaTeX could not compile the CV: Undefined control sequence (line 3).'
    assert failure.value.diagnostics.startswith('! Undefined control sequence.')
