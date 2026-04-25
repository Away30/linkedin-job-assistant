"""Fixtures for automation integration tests."""
import asyncio
import importlib.util
import inspect

import pytest

create_engine = None
sessionmaker = None
Base = None
SQLALCHEMY_AVAILABLE = importlib.util.find_spec("sqlalchemy") is not None
SQLALCHEMY_TEST_MODULES = {"test_rate_limiter.py"}


def _load_db_dependencies() -> bool:
    """Load DB fixtures lazily; only degrade when sqlalchemy is missing."""
    global create_engine, sessionmaker, Base
    if create_engine is not None and sessionmaker is not None and Base is not None:
        return True

    try:
        from sqlalchemy import create_engine as loaded_create_engine
        from sqlalchemy.orm import sessionmaker as loaded_sessionmaker
        from app.db.session import Base as loaded_base
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        if exc.name == "sqlalchemy":
            return False
        raise

    create_engine = loaded_create_engine
    sessionmaker = loaded_sessionmaker
    Base = loaded_base
    return True


def pytest_configure(config):
    # Keep async marker consistent even when pytest-asyncio is unavailable.
    config.addinivalue_line("markers", "asyncio: mark async test to run in asyncio loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if pyfuncitem.config.pluginmanager.hasplugin("asyncio"):
        return None

    if pyfuncitem.get_closest_marker("asyncio") is None:
        return None

    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    test_kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(test_func(**test_kwargs))
    return True


def pytest_collection_modifyitems(config, items):
    """Skip only known SQLAlchemy-dependent automation modules when unavailable."""
    if SQLALCHEMY_AVAILABLE:
        return

    skip_sqlalchemy = pytest.mark.skip(reason="sqlalchemy is required for DB-backed automation tests")
    for item in items:
        module_name = item.nodeid.split("::", 1)[0].rsplit("/", 1)[-1]
        if module_name in SQLALCHEMY_TEST_MODULES:
            item.add_marker(skip_sqlalchemy)


@pytest.fixture
def db_session():
    """Provide a transient SQLite session for rate-limiter tests."""
    if not _load_db_dependencies():
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
