"""Rate limiting and warmup logic for anti-detection."""
from datetime import datetime, date, timezone
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Application, OperationLog


class RateLimiter:
    """Enforces daily application limits with warmup period."""

    def can_apply(self, db: Session) -> tuple[bool, str]:
        """Check if we can apply right now."""
        remaining = self.get_daily_remaining(db)
        if remaining <= 0:
            return False, "Daily application limit reached"
        return True, f"{remaining} applications remaining today"

    def get_daily_remaining(self, db: Session) -> int:
        """Get remaining applications for today."""
        today = date.today()
        today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        today_count = db.query(Application).filter(
            Application.status == "applied",
            Application.applied_at >= today_start,
        ).count()

        daily_limit = self._get_current_limit(db)
        return max(0, daily_limit - today_count)

    def get_today_count(self, db: Session) -> int:
        """Get number of applications made today."""
        today = date.today()
        today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        return db.query(Application).filter(
            Application.status == "applied",
            Application.applied_at >= today_start,
        ).count()

    def _get_current_limit(self, db: Session) -> int:
        """Calculate current daily limit based on warmup period."""
        first_log = db.query(OperationLog).order_by(OperationLog.created_at.asc()).first()
        if not first_log:
            return settings.WARMUP_START_APPLIES

        days_active = (datetime.now(timezone.utc) - first_log.created_at).days

        if days_active < settings.WARMUP_DAYS:
            return settings.WARMUP_START_APPLIES + int(
                (settings.MAX_APPLIES_PER_DAY - settings.WARMUP_START_APPLIES)
                * (days_active / settings.WARMUP_DAYS)
            )
        return settings.MAX_APPLIES_PER_DAY


rate_limiter = RateLimiter()
