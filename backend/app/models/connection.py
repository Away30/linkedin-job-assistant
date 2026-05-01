from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class Connection(Base):
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True, index=True)
    profile_url = Column(String(1000), nullable=False, index=True)
    person_name = Column(String(300))
    title = Column(String(500))
    company = Column(String(300), index=True)
    person_type = Column(String(50), nullable=True)  # recruiter, hiring_manager, engineer
    message = Column(Text)
    status = Column(String(50), default="pending", index=True)  # pending, sent, accepted, failed
    error_message = Column(Text, nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    sent_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), index=True)

    job = relationship("Job")
