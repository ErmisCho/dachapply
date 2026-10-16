from jobradar.services.cv_generator import _dropped_photo

BASE = '\documentclass{article}\begin{document}\includegraphics{./Picture.jpg} CV\end{document}'


def test_a_cv_that_lost_the_base_photo_is_flagged_and_others_are_not():
    """TASK-304: only a non-empty CV missing the base CV's photo fails validation."""
    assert _dropped_photo(BASE, BASE.replace('\includegraphics{./Picture.jpg} ', ''))
    assert not _dropped_photo(BASE, BASE)
    assert not _dropped_photo(BASE.replace('\includegraphics{./Picture.jpg} ', ''), 'no photo anywhere')
    assert not _dropped_photo(BASE, '   ')  # an empty CV is reported as empty, not as a lost photo
