from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.session import Base

class Connection(Base):
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True, index=True)
    profile_url = Column(String(1000), nullable=False)
    person_name = Column(String(300))
    title = Column(String(500))
    company = Column(String(300))
    message = Column(Text)
    status = Column(String(50), default="pending")  # pending, sent, accepted, failed
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
