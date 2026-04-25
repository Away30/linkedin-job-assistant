"""Fixtures for automation integration tests."""
import pytest

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.session import Base
except ModuleNotFoundError:  # pragma: no cover - optional test dependency
    create_engine = None
    sessionmaker = None
    Base = None


@pytest.fixture
def db_session():
    """Provide a transient SQLite session for rate-limiter tests."""
    if create_engine is None or sessionmaker is None or Base is None:
        pytest.skip("sqlalchemy is required for db_session fixture")

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
