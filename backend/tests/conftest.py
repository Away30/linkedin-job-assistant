import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base, engine
from app.middleware.auth import get_or_create_api_key
from app.config import settings


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def api_key():
    """Get the current API key for authenticated requests."""
    return get_or_create_api_key(settings.DATA_DIR / "config")


@pytest.fixture
def client(api_key):
    return TestClient(app, headers={"X-API-Key": api_key})
