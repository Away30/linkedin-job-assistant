"""Connection management API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pathlib import Path
import yaml
from app.db.session import SessionLocal, get_db
from app.models import Connection, Job
from app.schemas.schemas import ConnectionRead, ConnectionUpdate
from app.config import settings

router = APIRouter(tags=["connections"])

MESSAGES_PATH = settings.DATA_DIR / "config" / "connection_messages.yaml"

# Default message templates
DEFAULT_MESSAGES = {
    "recruiter": "Hi {name}, I recently applied for the {role} role at {company}. I'd love to connect and learn more about the team!",
    "hiring_manager": "Hi {name}, I applied for the {role} position at {company}. I'm excited about the work your team is doing and would love to connect.",
    "engineer": "Hi {name}, I applied for the {role} role at {company}. I'd love to connect and hear about your experience on the team!",
    "default": "Hi {name}, I'm interested in opportunities at {company} and would love to connect.",
}


@router.get("/connections", response_model=list[ConnectionRead])
def list_connections(
    status: Optional[str] = None,
    company: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List connections with optional filtering."""
    query = db.query(Connection)
    if status:
        query = query.filter(Connection.status == status)
    if company:
        query = query.filter(Connection.company.ilike(f"%{company}%"))
    offset = (page - 1) * per_page
    return query.order_by(Connection.created_at.desc()).offset(offset).limit(per_page).all()


@router.get("/connections/stats")
def connection_stats(db: Session = Depends(get_db)):
    """Get connection statistics for the last 7 days."""
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    total = db.query(Connection).filter(
        Connection.created_at >= seven_days_ago
    ).count()
    sent = db.query(Connection).filter(
        Connection.created_at >= seven_days_ago,
        Connection.status == "sent",
    ).count()
    failed = db.query(Connection).filter(
        Connection.created_at >= seven_days_ago,
        Connection.status == "failed",
    ).count()
    accepted = db.query(Connection).filter(
        Connection.created_at >= seven_days_ago,
        Connection.status == "accepted",
    ).count()

    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "accepted": accepted,
        "success_rate": round(sent / total * 100, 1) if total > 0 else 0,
    }


@router.patch("/connections/{connection_id}", response_model=ConnectionRead)
def update_connection(
    connection_id: int,
    update: ConnectionUpdate,
    db: Session = Depends(get_db),
):
    """Update a connection's status (e.g., mark as accepted)."""
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(404, "Connection not found")
    if update.status:
        conn.status = update.status
        if update.status == "accepted":
            conn.accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/connections/messages")
def get_connection_messages():
    """Get custom connection message templates."""
    if MESSAGES_PATH.exists():
        with open(MESSAGES_PATH) as f:
            custom = yaml.safe_load(f) or {}
        return {**DEFAULT_MESSAGES, **{k: v for k, v in custom.items() if v}}
    return DEFAULT_MESSAGES


@router.post("/connections/messages")
def save_connection_messages(messages: dict):
    """Save custom connection message templates."""
    MESSAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MESSAGES_PATH, "w") as f:
        yaml.dump(messages, f, allow_unicode=True, default_flow_style=False)
    return {"success": True, "message": "消息模板已保存"}


@router.post("/connections/trigger")
async def trigger_networking(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Manually trigger networking for a specific job's company."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.company:
        raise HTTPException(400, "Job has no company info")

    job_company = job.company
    job_role = job.title or ""
    target_job_id = job.id

    from app.automation.browser_manager import browser_manager
    from app.automation.networking.networking_service import networking_service
    from app.config import settings as app_settings

    if not browser_manager.is_running:
        return {
            "message": "Browser not running. Start an automation session first.",
            "company": job_company,
            "role": job_role,
        }

    page = await browser_manager.get_page()
    # Use a dedicated session so the long-running networking flow doesn't keep
    # the request-scoped SQLite connection open while we wait on Playwright.
    networking_db = SessionLocal()
    try:
        results = await networking_service.network_after_apply(
            page=page,
            company=job_company,
            role_title=job_role,
            job_id=target_job_id,
            db=networking_db,
            max_connects=app_settings.NETWORKING_MAX_PER_SESSION,
            person_types=[t.strip() for t in app_settings.NETWORKING_PERSON_TYPES.split(",")],
        )
        sent = sum(1 for r in results if r.get("success"))
        failed = sum(1 for r in results if not r.get("success"))
        return {
            "message": f"Networking completed for {job_company}: {sent} sent, {failed} failed",
            "company": job_company,
            "role": job_role,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(500, f"Networking failed: {str(e)}")
    finally:
        networking_db.close()
