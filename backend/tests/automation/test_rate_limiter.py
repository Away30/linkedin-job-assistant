"""Test rate limiter with timezone-aware datetimes."""
import pytest
from datetime import datetime, timezone

def test_timezone_aware_comparison(db_session):
    """Verify rate limiter works with UTC-stored applied_at."""
    pytest.importorskip("sqlalchemy", reason="sqlalchemy is required for rate limiter DB tests")
    from app.safety.rate_limiter import RateLimiter
    from app.models import Application

    # Create an application with UTC timestamp
    app = Application(
        job_id=1,
        status="applied",
        applied_at=datetime.now(timezone.utc),
    )
    db_session.add(app)
    db_session.commit()

    limiter = RateLimiter()
    count = limiter.get_today_count(db_session)
    assert count == 1


def test_daily_remaining_respects_limit(db_session):
    """Remaining count should decrease with each application."""
    pytest.importorskip("sqlalchemy", reason="sqlalchemy is required for rate limiter DB tests")
    from app.safety.rate_limiter import RateLimiter
    from app.models import Application

    limiter = RateLimiter()
    remaining = limiter.get_daily_remaining(db_session)
    assert remaining > 0

    # Add an application
    app = Application(
        job_id=1,
        status="applied",
        applied_at=datetime.now(timezone.utc),
    )
    db_session.add(app)
    db_session.commit()

    new_remaining = limiter.get_daily_remaining(db_session)
    assert new_remaining == remaining - 1
