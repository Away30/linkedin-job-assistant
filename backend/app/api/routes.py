from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from pathlib import Path as PathLib
from datetime import datetime, timedelta
import asyncio
import json
import logging
import uuid
import yaml

from app.db.session import get_db
from app.models import Job, Application, Resume, SearchFilter, OperationLog, Blacklist
from app.schemas.schemas import (
    JobCreate, JobRead, JobListParams,
    ApplicationRead, ApplicationUpdate,
    ResumeRead,
    SearchFilterCreate, SearchFilterRead, SearchFilterUpdate,
    AutomationStartRequest, AutomationStatus,
    OperationLogRead,
    SettingsUpdate, SettingsRead,
    BlacklistCreate, BlacklistRead,
)
from app.services.automation_service import automation_service
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ---- Health ----
@router.get("/ping")
async def ping():
    return {"message": "pong"}

@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}

# ---- Automation ----
@router.post("/automation/start")
async def start_automation(request: AutomationStartRequest):
    if automation_service.is_running:
        raise HTTPException(400, "Automation session already running")
    await automation_service.start(request)
    return {"message": "Automation started", "session_id": automation_service.session_id}

@router.post("/automation/stop")
async def stop_automation():
    await automation_service.stop()
    return {"message": "Automation stopped"}

@router.get("/automation/status")
async def get_automation_status():
    return automation_service.get_status()

@router.get("/automation/status/stream")
async def stream_automation_status(request: Request):
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    return
                status = automation_service.get_status()
                yield f"data: {json.dumps(status.model_dump(), default=str)}\n\n"
                if not status.is_running:
                    return
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            # Client closed the stream — exit cleanly so the worker doesn't leak.
            raise
        except Exception:  # pragma: no cover - defensive
            logger.exception("status SSE generator failed")
            return
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ---- Jobs ----
@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    company: Optional[str] = None,
    easy_apply_only: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if keyword:
        query = query.filter(Job.title.ilike(f"%{keyword}%"))
    if company:
        query = query.filter(Job.company.ilike(f"%{company}%"))
    if easy_apply_only:
        query = query.filter(Job.is_easy_apply == True)
    offset = (page - 1) * per_page
    return query.order_by(Job.created_at.desc()).offset(offset).limit(per_page).all()

@router.post("/jobs", response_model=JobRead)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    existing = db.query(Job).filter(Job.linkedin_job_id == job.linkedin_job_id).first()
    if existing:
        return existing
    db_job = Job(**job.model_dump())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return job

# ---- Applications ----
@router.get("/applications", response_model=list[ApplicationRead])
def list_applications(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Application).options(joinedload(Application.job))
    if status:
        query = query.filter(Application.status == status)
    offset = (page - 1) * per_page
    return query.order_by(Application.created_at.desc()).offset(offset).limit(per_page).all()

@router.patch("/applications/{app_id}", response_model=ApplicationRead)
def update_application(app_id: int, update: ApplicationUpdate, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(app, key, value)
    db.commit()
    db.refresh(app)
    return app

# ---- Resumes ----
@router.get("/resumes", response_model=list[ResumeRead])
def list_resumes(db: Session = Depends(get_db)):
    return db.query(Resume).order_by(Resume.created_at.desc()).all()

@router.post("/resumes", response_model=ResumeRead)
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form(...),
    target_roles: str = Form(""),
    is_default: bool = Form(False),
    db: Session = Depends(get_db),
):
    ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
    ext = PathLib(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type {ext} not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}")

    settings.RESUME_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    file_path = settings.RESUME_DIR / safe_name
    content = await file.read()
    file_path.write_bytes(content)

    if is_default:
        db.query(Resume).filter(Resume.is_default == True).update({"is_default": False})

    resume = Resume(
        name=name,
        file_path=str(file_path),
        file_size=len(content),
        target_roles=target_roles,
        is_default=is_default,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume

@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "Resume not found")
    from pathlib import Path
    path = Path(resume.file_path)
    if path.exists():
        path.unlink()
    db.delete(resume)
    db.commit()
    return {"message": "Resume deleted"}

# ---- Search Filters ----
@router.get("/filters", response_model=list[SearchFilterRead])
def list_filters(db: Session = Depends(get_db)):
    return db.query(SearchFilter).order_by(SearchFilter.created_at.desc()).all()

@router.post("/filters", response_model=SearchFilterRead)
def create_filter(f: SearchFilterCreate, db: Session = Depends(get_db)):
    db_filter = SearchFilter(**f.model_dump())
    db.add(db_filter)
    db.commit()
    db.refresh(db_filter)
    return db_filter

@router.get("/filters/{filter_id}", response_model=SearchFilterRead)
def get_filter(filter_id: int, db: Session = Depends(get_db)):
    f = db.query(SearchFilter).filter(SearchFilter.id == filter_id).first()
    if not f:
        raise HTTPException(404, "Filter not found")
    return f

@router.put("/filters/{filter_id}", response_model=SearchFilterRead)
def update_filter(filter_id: int, update: SearchFilterUpdate, db: Session = Depends(get_db)):
    f = db.query(SearchFilter).filter(SearchFilter.id == filter_id).first()
    if not f:
        raise HTTPException(404, "Filter not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(f, key, value)
    db.commit()
    db.refresh(f)
    return f

@router.delete("/filters/{filter_id}")
def delete_filter(filter_id: int, db: Session = Depends(get_db)):
    f = db.query(SearchFilter).filter(SearchFilter.id == filter_id).first()
    if not f:
        raise HTTPException(404, "Filter not found")
    db.delete(f)
    db.commit()
    return {"message": "Filter deleted"}

# ---- Operation Logs ----
@router.get("/logs", response_model=list[OperationLogRead])
def list_logs(
    operation_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(OperationLog)
    if operation_type:
        query = query.filter(OperationLog.operation_type == operation_type)
    offset = (page - 1) * per_page
    return query.order_by(OperationLog.created_at.desc()).offset(offset).limit(per_page).all()


# ---- Settings ----
@router.get("/settings", response_model=SettingsRead)
def get_settings():
    return SettingsRead(
        max_applies_per_day=settings.MAX_APPLIES_PER_DAY,
        max_connects_per_day=settings.MAX_CONNECTS_PER_DAY,
        warmup_days=settings.WARMUP_DAYS,
        action_delay_min=settings.ACTION_DELAY_MIN,
        action_delay_max=settings.ACTION_DELAY_MAX,
        max_session_minutes=settings.MAX_SESSION_MINUTES,
        networking_enabled=settings.NETWORKING_ENABLED,
        networking_max_per_session=settings.NETWORKING_MAX_PER_SESSION,
        networking_person_types=settings.NETWORKING_PERSON_TYPES,
    )


@router.post("/settings")
def update_settings(update: SettingsUpdate):
    payload = update.model_dump(exclude_unset=True)
    if not payload:
        return {"message": "No changes", "updated": {}}
    try:
        applied = settings.persist_runtime_overrides(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"message": "Settings updated", "updated": applied}


# ---- Blacklist ----
@router.get("/blacklist", response_model=list[BlacklistRead])
def list_blacklist(db: Session = Depends(get_db)):
    return db.query(Blacklist).order_by(Blacklist.created_at.desc()).all()


@router.post("/blacklist", response_model=BlacklistRead)
def add_blacklist_entry(entry: BlacklistCreate, db: Session = Depends(get_db)):
    db_entry = Blacklist(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.delete("/blacklist/{entry_id}")
def delete_blacklist_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(Blacklist).filter(Blacklist.id == entry_id).first()
    if not entry:
        raise HTTPException(404, "Blacklist entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Blacklist entry deleted"}


# ---- Application Retry ----
@router.post("/applications/{app_id}/retry")
async def retry_application(app_id: int, db: Session = Depends(get_db)):
    """Re-attempt a failed application."""
    application = db.query(Application).filter(Application.id == app_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.status == "applied":
        raise HTTPException(status_code=400, detail="Application already succeeded")

    # Mark for retry - the actual retry happens on next automation run
    application.status = "pending_retry"
    application.error_message = None
    db.commit()
    db.refresh(application)
    return application


# ---- Stats Summary ----
@router.get("/stats/summary")
async def stats_summary(db: Session = Depends(get_db)):
    """Get application statistics for the last 7 days."""
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    total = db.query(Application).filter(Application.applied_at >= seven_days_ago).count()
    successful = db.query(Application).filter(
        Application.applied_at >= seven_days_ago,
        Application.status == "applied",
    ).count()
    failed = db.query(Application).filter(
        Application.applied_at >= seven_days_ago,
        Application.status == "failed",
    ).count()

    # Top companies
    from sqlalchemy import func as sqlfunc
    top_companies = db.query(
        Job.company, sqlfunc.count(Application.id).label("count"),
    ).join(Application).filter(
        Application.applied_at >= seven_days_ago,
    ).group_by(Job.company).order_by(sqlfunc.count(Application.id).desc()).limit(5).all()

    return {
        "total_applications": total,
        "successful": successful,
        "failed": failed,
        "success_rate": round(successful / total * 100, 1) if total > 0 else 0,
        "top_companies": [{"company": c, "count": n} for c, n in top_companies if c],
    }


# --- Form Answers ---

@router.get("/form-answers")
def get_form_answers():
    """Read form_answers.yaml and return as JSON."""
    yaml_path = settings.FORM_ANSWERS_PATH
    if not yaml_path.exists():
        return {}
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


@router.post("/form-answers")
def update_form_answers(answers: dict):
    """Write form answers dict to form_answers.yaml."""
    yaml_path = settings.FORM_ANSWERS_PATH
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    # Strip None values and ensure all values are strings
    cleaned = {k: str(v) if v is not None else "" for k, v in answers.items()}
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(cleaned, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return {"message": "表单答案已保存", "count": len(cleaned)}
