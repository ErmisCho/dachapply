import pytest

from jobradar.services import cv_generator


@pytest.fixture(autouse=True)
def _isolated_candidate_files(settings, tmp_path):
    """Point the candidate-evidence and rules files at fixtures for every test.

    CODEX_CANDIDATE_EVIDENCE_PATH defaults to Ermis-Chorinopoulos-Candidate-Evidence.md at the
    repo root, which is deliberately untracked -- it is personal career data. Tests that relied on
    that default therefore passed only on the author's machine and returned 503 anywhere else,
    which is exactly what CI caught the first time it ran the suite. Tests that care about the
    content set their own paths and override this.
    """
    evidence = tmp_path / 'fixture-candidate-evidence.md'
    evidence.write_text(
        '# Candidate Evidence\n## Professional Summary\nBackend engineer with Python and Django.\n'
        '## Needs Confirmation\nNothing outstanding.\n',
        encoding='utf-8',
    )
    rules = tmp_path / 'fixture-application-rules.md'
    rules.write_text('Never invent experience the candidate does not have.\n', encoding='utf-8')
    settings.CODEX_CANDIDATE_EVIDENCE_PATH = str(evidence)
    settings.CODEX_APPLICATION_RULES_PATH = str(rules)


@pytest.fixture(autouse=True)
def _never_send_real_email(settings):
    """Pin every test to the in-memory mail backend.

    Two reasons, the first of which is why this is autouse rather than per-test:

    1. Only locmem populates django.core.mail.outbox. Measured on a clean checkout,
       config.settings_test resolves to the *console* backend (no BREVO_*/LOCAL_* keys in
       either .env, so EMAIL_PROVIDER='auto' falls through to the DEBUG default), which
       prints the message and records nothing -- so any outbox assertion would silently
       pass on an empty list rather than proving a mail was sent.

    2. That resolution depends on the environment, not on the test settings. config.settings
       picks the backend from EMAIL_PROVIDER / BREVO_* / EMAIL_BACKEND, all of which are read
       from the two .env files. The moment someone configures real SMTP locally -- which the
       docs actively describe for testing password reset -- the suite would start sending real
       mail from a developer machine. It does not do that today; this fixture is what keeps it
       that way regardless of local configuration.

    Tests that want a specific backend still override it.
    """
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


@pytest.fixture(autouse=True)
def _reset_model_options_cache():
    """available_model_options() memoises for 60s at module level.

    Without this, whichever test runs first warms the cache and every later test
    that patches discovery silently asserts against the earlier test's result.
    """
    cv_generator._model_options_cache.update(at=0.0, options=None)
    yield
    cv_generator._model_options_cache.update(at=0.0, options=None)
