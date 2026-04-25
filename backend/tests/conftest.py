import pytest
from fastapi.testclient import TestClient

try:
    from app.main import app
    from app.db.session import Base, engine
    from app.middleware.auth import get_or_create_api_key
    from app.config import settings
except ModuleNotFoundError:
    app = None
    Base = None
    engine = None
    get_or_create_api_key = None
    settings = None


@pytest.fixture(autouse=True)
def setup_db():
    if Base is None or engine is None:
        yield
        return
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def api_key():
    """Get the current API key for authenticated requests."""
    if get_or_create_api_key is None or settings is None:
        pytest.skip("app test dependencies are not installed")
    return get_or_create_api_key(settings.DATA_DIR / "config")


@pytest.fixture
def client(api_key):
    if app is None:
        pytest.skip("app test dependencies are not installed")
    return TestClient(app, headers={"X-API-Key": api_key})
