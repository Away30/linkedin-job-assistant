from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# `timeout` lets SQLite block briefly on a locked DB instead of raising
# OperationalError immediately. With long-running background sessions plus
# SSE polling, this is the difference between an occasional retry and a
# user-facing 500.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _):
    """Enable WAL + sane busy_timeout on every new SQLite connection.

    WAL allows concurrent readers while a writer is in flight, which matches
    our usage pattern (worker writing applications while SSE polls status).
    """
    if engine.url.get_backend_name() != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30s
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import app.models  # noqa: F401 - ensure models are imported
    Base.metadata.create_all(bind=engine)
