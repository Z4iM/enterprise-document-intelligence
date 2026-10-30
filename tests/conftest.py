"""Keep import-time SQLite initialization and dotenv away from user data."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def pytest_configure(config):
    sandbox = TemporaryDirectory(prefix="edi-pytest-")
    patch = pytest.MonkeyPatch()
    patch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    patch.chdir(sandbox.name)
    patch.setenv("PYTHON_DOTENV_DISABLED", "1")
    patch.setenv("EDI_ENV", "development")
    patch.setenv("EDI_PROCESSING_MODE", "inline")
    patch.setenv("EDI_DATA_ROOT", "data")
    patch.setenv("EDI_DATABASE_URL", "sqlite:///data/database.db")
    patch.setenv("EDI_ALLOWED_ORIGINS", "http://127.0.0.1:3000,http://127.0.0.1:8000")
    config.addinivalue_line("markers", "security: exercises real authentication without trusted unit-test identity overrides")
    patch.setenv("LLM_PROVIDER", "http")
    patch.setenv("LLM_API_URL", "http://127.0.0.1:9999")
    patch.setenv("LLM_API_KEY", "ci-test-placeholder")
    patch.delenv("GEMINI_API_KEY", raising=False)
    config._edi_sandbox = sandbox
    config._edi_patch = patch


def pytest_unconfigure(config):
    if hasattr(config, "_edi_patch"):
        from app.database import database

        database.engine.dispose()
        config._edi_patch.undo()
        config._edi_sandbox.cleanup()


@pytest.fixture(autouse=True)
def trusted_identity_for_existing_component_tests(request):
    """Legacy component tests assume identity; security tests exercise real sessions."""
    if request.node.get_closest_marker("security"):
        yield
        return
    from app.auth.security import require_actor
    from app.main import app
    from tests.auth_helpers import TEST_ACTOR
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[require_actor] = lambda: TEST_ACTOR
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
