from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.session import Base

class SearchFilter(Base):
    __tablename__ = "search_filters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    keywords = Column(String(500))
    location = Column(String(300))
    job_type = Column(String(100))  # full-time, part-time, contract, internship
    experience_level = Column(String(100))  # entry, associate, mid-senior, director, executive
    remote_filter = Column(String(50))  # on-site, remote, hybrid
    salary_min = Column(Integer, nullable=True)
    easy_apply_only = Column(Boolean, default=True)
    date_posted = Column(String(50))  # any, past-24h, past-week, past-month
    required_skills = Column(String(2000))  # comma-separated: Python, FastAPI, AWS
    preferred_skills = Column(String(2000))  # comma-separated: Docker, K8s
    min_match_score = Column(Integer, default=40)  # 0-100, skip jobs below this
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
