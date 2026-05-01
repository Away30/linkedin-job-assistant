from pathlib import Path


def test_pytest_database_url_does_not_point_to_runtime_database():
    from app.config import settings

    runtime_db = Path(__file__).resolve().parents[1] / "data" / "db" / "linkedin_assistant.db"

    assert str(runtime_db) not in str(settings.DATABASE_URL)
    assert settings.DATA_DIR != runtime_db.parent.parent

