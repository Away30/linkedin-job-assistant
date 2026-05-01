"""Rate limiting and warmup logic for anti-detection."""
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Application, Connection, OperationLog


class RateLimiter:
    """Enforces daily application limits with warmup period."""

    def can_apply(self, db: Session) -> tuple[bool, str]:
        """Check if we can apply right now."""
        remaining = self.get_daily_remaining(db)
        if remaining <= 0:
            return False, "已达到每日投递上限"
        return True, f"今日还可投递 {remaining} 次"

    def get_daily_remaining(self, db: Session) -> int:
        """Get remaining applications for today."""
        today = date.today()
        today_start = datetime(today.year, today.month, today.day)
        today_count = db.query(Application).filter(
            Application.status == "applied",
            Application.applied_at >= today_start,
        ).count()

        daily_limit = self._get_current_limit(db)
        return max(0, daily_limit - today_count)

    def get_today_count(self, db: Session) -> int:
        """Get number of applications made today."""
        today = date.today()
        today_start = datetime(today.year, today.month, today.day)
        return db.query(Application).filter(
            Application.status == "applied",
            Application.applied_at >= today_start,
        ).count()

    # --- Connection rate limiting (independent from applications) ---

    def can_connect(self, db: Session) -> tuple[bool, str]:
        """Check if we can send a connection request right now."""
        remaining = self.get_daily_connect_remaining(db)
        if remaining <= 0:
            return False, "已达到每日连接请求上限"
        return True, f"今日还可发送 {remaining} 个连接请求"

    def get_daily_connect_remaining(self, db: Session) -> int:
        """Get remaining connection requests for today."""
        today = date.today()
        today_start = datetime(today.year, today.month, today.day)
        today_count = db.query(Connection).filter(
            Connection.status == "sent",
            Connection.sent_at >= today_start,
        ).count()
        return max(0, settings.MAX_CONNECTS_PER_DAY - today_count)

    def _get_current_limit(self, db: Session) -> int:
        """Calculate current daily limit based on warmup period."""
        first_log = db.query(OperationLog).order_by(OperationLog.created_at.asc()).first()
        if not first_log:
            return settings.WARMUP_START_APPLIES

        days_active = (datetime.utcnow() - first_log.created_at).days

        if days_active < settings.WARMUP_DAYS:
            return settings.WARMUP_START_APPLIES + int(
                (settings.MAX_APPLIES_PER_DAY - settings.WARMUP_START_APPLIES)
                * (days_active / settings.WARMUP_DAYS)
            )
        return settings.MAX_APPLIES_PER_DAY


rate_limiter = RateLimiter()
