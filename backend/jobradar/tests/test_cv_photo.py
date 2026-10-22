from jobradar.services.cv_generator import _drop_forced_breaks, _dropped_photo, _restore_base_macros

BASE = '\documentclass{article}\begin{document}\includegraphics{./Picture.jpg} CV\end{document}'


def test_a_cv_that_lost_the_base_photo_is_flagged_and_others_are_not():
    """TASK-304: only a non-empty CV missing the base CV's photo fails validation."""
    assert _dropped_photo(BASE, BASE.replace('\includegraphics{./Picture.jpg} ', ''))
    assert not _dropped_photo(BASE, BASE)
    assert not _dropped_photo(BASE.replace('\includegraphics{./Picture.jpg} ', ''), 'no photo anywhere')
    assert not _dropped_photo(BASE, '   ')  # an empty CV is reported as empty, not as a lost photo


def test_forced_page_breaks_the_base_does_not_have_are_dropped():
    """TASK-327: the generated CVs' \\newpage before Huawei left page 1 a quarter empty."""
    generated = '\\resumeSubHeadingListEnd\n\n\\newpage\n\n\\resumeSubHeadingListStart\n\\clearpage\\section{Skills}\\pagebreak[4] \\newpagestyle'
    assert _drop_forced_breaks(BASE, generated) == '\\resumeSubHeadingListEnd\n\n\n\n\\resumeSubHeadingListStart\n\\section{Skills} \\newpagestyle'
    with_break = BASE.replace(' CV', ' CV\\newpage')
    assert _drop_forced_breaks(with_break, generated) == generated  # the base forces breaks itself: kept


def test_a_generation_gets_the_base_layout_macros_back():
    """TASK-342: a tightened \\resumeItemListStart under v1.5's \\vspace{-7pt} project heading made headings
    overlap their first bullet. Base-defined \\resume* macros come back verbatim; others stay."""
    base = ('\\newcommand{\\resumeProjectHeading}[2]{\n  \\item\n  \\begin{tabular*}{0.97\\textwidth}{l@{\\extracolsep{\\fill}}r}\n'
            '    \\small#1 & #2 \\\\\n  \\end{tabular*}\\vspace{-7pt}\n}\n\\newcommand{\\resumeItemListStart}{\\begin{itemize}}\n\\begin{document}x\\end{document}')
    generated = base.replace('\\begin{itemize}}', '\\begin{itemize}[topsep=4pt, itemsep=2pt]}').replace('\\vspace{-7pt}', '\\vspace{-9pt}')
    generated = generated.replace('\\begin{document}', '\\newcommand{\\resumeExtra}{\\textbf{x}}\n\\begin{document}')
    restored = _restore_base_macros(base, generated)
    assert '\\newcommand{\\resumeItemListStart}{\\begin{itemize}}' in restored and '\\vspace{-7pt}' in restored
    assert '\\newcommand{\\resumeExtra}{\\textbf{x}}' in restored  # not in the base: the model's own macro stays
    assert _restore_base_macros(base, base) == base
