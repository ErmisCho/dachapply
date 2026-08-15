import pytest

from jobradar.services import cv_generator


@pytest.fixture(autouse=True)
def _reset_model_options_cache():
    """available_model_options() memoises for 60s at module level.

    Without this, whichever test runs first warms the cache and every later test
    that patches discovery silently asserts against the earlier test's result.
    """
    cv_generator._model_options_cache.update(at=0.0, options=None)
    yield
    cv_generator._model_options_cache.update(at=0.0, options=None)
