"""TASK-333: an instruction heading after a NEW block ('CHANGE 2 — ...', 'FILE 2: ...', 'FINAL
VALIDATION:') ends the block instead of being spliced into the document (2026-10-21: 'Missing
\\begin{document}' at the CV preamble line holding 'CHANGE 2 ...')."""
from jobradar.services.cv_generator import exact_revision_plan

CV = '\\documentclass{article}\n\\newcommand{\\item}[1]{\\small{#1}}\n\\begin{document}\n\\item{Alpha}\n\\item{Beta}\n\\end{document}\n'
LETTER = 'Vienna, 1 May\n\nFirst paragraph.\n\nClosing paragraph.\n'

INSTRUCTIONS = '''Apply these exact OLD/NEW replacements.

FILE 1: cv.tex

CHANGE 1 — Normal size

OLD:
\\newcommand{\\item}[1]{\\small{#1}}

NEW:
\\newcommand{\\item}[1]{\\normalsize{#1}}


CHANGE 2 — Two items, a blank line between them

OLD:
\\item{Alpha}

NEW:
\\item{Alpha one}

\\item{Alpha two}


FILE 2: letter.tex

CHANGE 3 — Date

OLD:
Vienna, 1 May

NEW:
Vienna, 2 May

CHANGE 4 — Two letter paragraphs
OLD:
Closing paragraph.

NEW:
Closing paragraph, new.

Change of plans is welcome too.


FINAL VALIDATION:
1. Compile both files.
'''


def test_headings_end_new_blocks_and_block_content_is_kept(tmp_path):
    cv, letter = tmp_path / 'cv.tex', tmp_path / 'letter.tex'
    cv.write_text(CV, encoding='utf-8', newline='')
    letter.write_text(LETTER, encoding='utf-8', newline='')
    plan = exact_revision_plan([str(cv), str(letter)], INSTRUCTIONS)
    new_cv, new_letter = plan[str(cv)], plan[str(letter)]
    assert 'CHANGE' not in new_cv and 'FILE' not in new_cv and 'FINAL' not in new_letter and 'CHANGE' not in new_letter
    assert '\\newcommand{\\item}[1]{\\normalsize{#1}}\n\\begin{document}' in new_cv
    assert '\\item{Alpha one}\n\n\\item{Alpha two}\n\\item{Beta}' in new_cv  # a blank line inside a NEW block stays
    assert new_letter.startswith('Vienna, 2 May\n')
    # A paragraph starting 'Change of plans' after a blank line is block text: a heading word counts only
    # when a number, colon or dash follows it ('CHANGE 2 —', 'FILE 2:', 'NOTE:').
    assert new_letter.endswith('Closing paragraph, new.\n\nChange of plans is welcome too.\n')
