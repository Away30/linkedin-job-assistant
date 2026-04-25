import pytest

pytest.importorskip("sqlalchemy")

from app.models import Job, OperationLog
from app.services.automation_service import AutomationService


def test_build_application_record_persists_structured_form_answers(db_session):
    job = Job(linkedin_job_id="job-1", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    service = AutomationService()
    apply_result = {
        "success": False,
        "failure_type": "field_unresolved",
        "final_action": "blocked",
        "cleanup_success": False,
        "resolved_fields": ["Email"],
        "unresolved_fields": ["Work authorization"],
        "validation_errors": ["Select an option"],
        "errors": ["Unresolved required fields: Work authorization"],
    }

    record = service._build_application_record(
        job_id=job.id,
        resume_id=None,
        result=apply_result,
    )
    db_session.add(record)
    db_session.commit()

    stored = db_session.get(type(record), record.id)

    assert stored.form_answers["final_action"] == "blocked"
    assert stored.form_answers["failure_type"] == "field_unresolved"
    assert stored.form_answers["cleanup_success"] is False
    assert stored.form_answers["resolved_fields"] == ["Email"]
    assert stored.form_answers["unresolved_fields"] == ["Work authorization"]
    assert stored.form_answers["validation_errors"] == ["Select an option"]


def test_build_application_record_uses_structured_failure_as_error_message(db_session):
    job = Job(linkedin_job_id="job-2", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    service = AutomationService()
    apply_result = {
        "success": False,
        "failure_type": "cleanup_not_confirmed",
        "final_action": "submit",
        "cleanup_success": False,
        "resolved_fields": [],
        "unresolved_fields": [],
        "validation_errors": [],
        "errors": ["Submit click did not confirm completion or modal close"],
    }

    record = service._build_application_record(
        job_id=job.id,
        resume_id=None,
        result=apply_result,
    )

    assert record.error_message == "cleanup_not_confirmed: Submit click did not confirm completion or modal close"


def test_apply_outcome_persists_structured_record_and_operation_log(db_session):
    job = Job(linkedin_job_id="job-3", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    service = AutomationService()
    apply_result = {
        "success": True,
        "failure_type": None,
        "final_action": "submit",
        "cleanup_success": True,
        "resolved_fields": ["Email", "Phone"],
        "unresolved_fields": [],
        "validation_errors": [],
        "errors": [],
    }

    record = service._build_application_record(
        job_id=job.id,
        resume_id=None,
        result=apply_result,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)

    details = service._build_apply_operation_details(
        job_title=job.title,
        company=job.company,
        result=apply_result,
    )
    service._log_operation(db_session, "apply", details, "success")

    stored_app = db_session.get(type(record), record.id)
    op_log = db_session.query(OperationLog).filter(OperationLog.operation_type == "apply").first()

    assert stored_app.form_answers["final_action"] == "submit"
    assert stored_app.form_answers["cleanup_success"] is True
    assert stored_app.form_answers["resolved_fields"] == ["Email", "Phone"]
    assert "success=True" in op_log.details
    assert "final_action=submit" in op_log.details
    assert "resolved_fields=['Email', 'Phone']" in op_log.details
