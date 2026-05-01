import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="lja-pytest-"))
_TEST_DB_PATH = _TEST_DATA_DIR / "db" / "linkedin_assistant_test.db"
_TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# App modules create their engine and config at import time, so tests must
# redirect all persistent paths before importing app.main or app.db.session.
os.environ["LJA_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["LJA_DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["LJA_RESUME_DIR"] = str(_TEST_DATA_DIR / "resumes")
os.environ["LJA_FORM_ANSWERS_PATH"] = str(_TEST_DATA_DIR / "config" / "form_answers.yaml")
os.environ["LJA_BROWSER_PROFILE_DIR"] = str(_TEST_DATA_DIR / "browser_profile")

app = None
Base = None
engine = None
get_or_create_api_key = None
settings = None


def _load_app_test_dependencies() -> bool:
    """Load app fixtures lazily; only degrade when sqlalchemy is missing."""
    global app, Base, engine, get_or_create_api_key, settings
    if app is not None and Base is not None and engine is not None:
        return True

    try:
        from app.main import app as loaded_app
        from app.db.session import Base as loaded_base, engine as loaded_engine
        from app.middleware.auth import get_or_create_api_key as loaded_get_key
        from app.config import settings as loaded_settings
    except ModuleNotFoundError as exc:
        if exc.name == "sqlalchemy":
            return False
        raise

    app = loaded_app
    Base = loaded_base
    engine = loaded_engine
    get_or_create_api_key = loaded_get_key
    settings = loaded_settings
    return True


@pytest.fixture(autouse=True)
def setup_db():
    if not _load_app_test_dependencies():
        yield
        return
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def api_key():
    """Get the current API key for authenticated requests."""
    if not _load_app_test_dependencies():
        pytest.skip("sqlalchemy is required for app fixtures")
    return get_or_create_api_key(settings.DATA_DIR / "config")


@pytest.fixture
def client(api_key):
    return TestClient(app, headers={"X-API-Key": api_key})


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
