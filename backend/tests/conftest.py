import pytest
from fastapi.testclient import TestClient

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
