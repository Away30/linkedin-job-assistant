from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal, Optional


# Allowed status values shared between Application records and the API surface.
ApplicationStatus = Literal[
    "pending", "applied", "failed", "skipped", "pending_retry", "dry_run"
]
ConnectionStatus = Literal[
    "pending", "sent", "failed", "accepted",
]

# --- Job ---
class JobBase(BaseModel):
    linkedin_job_id: str
    title: str
    company: str | None = None
    location: str | None = None
    description: str | None = None
    job_url: str | None = None
    is_easy_apply: bool = False
    is_remote: bool = False
    salary_range: str | None = None
    experience_level: str | None = None
    job_type: str | None = None
    match_score: float = 0.0
    posted_date: str | None = None

class JobCreate(JobBase):
    pass

class JobRead(JobBase):
    id: int
    scraped_at: datetime | None = None
    created_at: datetime | None = None
    class Config:
        from_attributes = True

class JobListParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    keyword: str | None = None
    company: str | None = None
    easy_apply_only: bool | None = None
    sort_by: str = "created_at"

# --- Application ---
class ApplicationBase(BaseModel):
    job_id: int
    resume_id: int | None = None
    status: str = "pending"
    apply_method: str = "easy_apply"

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationRead(ApplicationBase):
    id: int
    job: JobRead | None = None
    form_answers: dict | None = None
    error_message: str | None = None
    applied_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    class Config:
        from_attributes = True

class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    error_message: str | None = None

# --- Resume ---
class ResumeRead(BaseModel):
    id: int
    name: str
    file_path: str
    file_size: int | None = None
    target_roles: str | None = None
    is_default: bool = False
    created_at: datetime | None = None
    class Config:
        from_attributes = True

# --- SearchFilter ---
class SearchFilterBase(BaseModel):
    name: str
    keywords: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    remote_filter: str | None = None
    salary_min: int | None = None
    easy_apply_only: bool = True
    date_posted: str | None = None
    required_skills: str | None = None
    preferred_skills: str | None = None
    min_match_score: int = 40
    is_active: bool = True

class SearchFilterCreate(SearchFilterBase):
    pass

class SearchFilterRead(SearchFilterBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    class Config:
        from_attributes = True

class SearchFilterUpdate(BaseModel):
    name: str | None = None
    keywords: str | None = None
    location: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    remote_filter: str | None = None
    salary_min: int | None = None
    easy_apply_only: bool | None = None
    date_posted: str | None = None
    required_skills: str | None = None
    preferred_skills: str | None = None
    min_match_score: int | None = None
    is_active: bool | None = None

# --- Automation ---
class AutomationStartRequest(BaseModel):
    filter_id: int | None = None
    keywords: str | None = None
    location: str | None = None
    max_applies: int = Field(default=10, ge=1, le=50)
    resume_id: int | None = None
    dry_run: bool = False
    enable_networking: bool = False  # Post-apply recruiter connection

class AutomationStatus(BaseModel):
    is_running: bool = False
    session_id: str | None = None
    jobs_found: int = 0
    jobs_applied: int = 0
    jobs_skipped: int = 0
    jobs_failed: int = 0
    jobs_dry_run: int = 0
    connections_sent: int = 0
    current_job: str | None = None
    elapsed_seconds: int = 0
    daily_applies_remaining: int = 25
    status_message: str = "idle"

class OperationLogRead(BaseModel):
    id: int
    operation_type: str
    details: str | None = None
    status: str
    error_message: str | None = None
    duration_ms: int | None = None
    created_at: datetime | None = None
    class Config:
        from_attributes = True

# --- Settings ---
class SettingsUpdate(BaseModel):
    max_applies_per_day: int | None = Field(default=None, ge=1, le=100)
    max_connects_per_day: int | None = Field(default=None, ge=1, le=50)
    action_delay_min: float | None = Field(default=None, ge=1.0, le=60.0)
    action_delay_max: float | None = Field(default=None, ge=1.0, le=120.0)
    networking_enabled: bool | None = None
    networking_max_per_session: int | None = Field(default=None, ge=1, le=10)
    networking_person_types: str | None = None

class SettingsRead(BaseModel):
    max_applies_per_day: int
    max_connects_per_day: int
    warmup_days: int
    action_delay_min: float
    action_delay_max: float
    max_session_minutes: int
    networking_enabled: bool = False
    networking_max_per_session: int = 3
    networking_person_types: str = "recruiter"

# --- Blacklist ---
class BlacklistCreate(BaseModel):
    company_name: str
    reason: Optional[str] = None

class BlacklistRead(BaseModel):
    id: int
    company_name: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

# --- Connection ---
class ConnectionUpdate(BaseModel):
    status: ConnectionStatus | None = None


class ConnectionRead(BaseModel):
    id: int
    job_id: int | None = None
    profile_url: str
    person_name: str | None = None
    title: str | None = None
    company: str | None = None
    person_type: str | None = None
    message: str | None = None
    status: ConnectionStatus = "pending"
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None
    class Config:
        from_attributes = True
