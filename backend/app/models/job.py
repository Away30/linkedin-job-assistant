from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime
from app.db.session import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    linkedin_job_id = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    company = Column(String(300))
    location = Column(String(300))
    description = Column(Text)
    job_url = Column(String(1000))
    is_easy_apply = Column(Boolean, default=False)
    is_remote = Column(Boolean, default=False)
    salary_range = Column(String(200))
    experience_level = Column(String(100))
    job_type = Column(String(100))  # full-time, contract, etc.
    match_score = Column(Float, default=0.0)
    posted_date = Column(String(100))
    scraped_at = Column(DateTime, default=lambda: datetime.utcnow())
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
