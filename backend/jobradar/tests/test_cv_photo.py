from jobradar.services.cv_generator import _drop_forced_breaks, _dropped_photo

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
