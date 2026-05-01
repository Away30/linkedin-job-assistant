import pytest

pytest.importorskip("sqlalchemy")

from app.models import Application, Job, OperationLog
from app.schemas.schemas import AutomationStartRequest
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


def test_dry_run_submit_intercept_is_not_persisted_as_applied(db_session):
    job = Job(linkedin_job_id="job-4", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    service = AutomationService()
    apply_result = {
        "success": True,
        "failure_type": "submit_intercepted_dry_run",
        "final_action": "submit",
        "cleanup_success": True,
        "resolved_fields": [],
        "unresolved_fields": [],
        "validation_errors": [],
        "errors": ["dry_run: submit skipped"],
    }

    record = service._build_application_record(
        job_id=job.id,
        resume_id=None,
        result=apply_result,
    )

    assert record.status == "dry_run"
    assert record.applied_at is None


def test_dry_run_submit_intercept_log_uses_dry_run_label():
    service = AutomationService()
    apply_result = {
        "success": True,
        "failure_type": "submit_intercepted_dry_run",
        "final_action": "submit",
        "cleanup_success": True,
        "resolved_fields": [],
        "unresolved_fields": [],
        "validation_errors": [],
        "errors": ["dry_run: submit skipped"],
    }

    details = service._build_apply_operation_details(
        job_title="Backend Engineer",
        company="Sample Co",
        result=apply_result,
    )
    success_message = service._build_apply_success_log_message(
        job_title="Backend Engineer",
        result=apply_result,
    )

    assert details.startswith("Dry-run reached submit:")
    assert success_message == "Dry-run reached submit for Backend Engineer"
    assert "Successfully applied" not in details
    assert "Successfully applied" not in success_message


def test_session_summary_uses_dry_run_label_while_preserving_count():
    service = AutomationService()

    summary = service._build_session_summary(
        completed_count=1,
        total_jobs=35,
        dry_run=True,
    )

    assert summary == "Completed. Dry-run reached submit for 1 of 35 jobs."
    assert "Applied to" not in summary


def test_dry_run_never_triggers_post_apply_networking_even_if_enabled():
    service = AutomationService()
    request = AutomationStartRequest(
        dry_run=True,
        enable_networking=True,
    )
    apply_result = {
        "success": True,
        "failure_type": "submit_intercepted_dry_run",
        "final_action": "submit",
    }

    should_network = service._should_network_after_apply(
        request=request,
        result=apply_result,
        company="Sample Co",
    )

    assert should_network is False


def test_failed_existing_application_is_retriable(db_session):
    job = Job(linkedin_job_id="job-5", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    failed = Application(job_id=job.id, status="failed", error_message="field_unresolved")
    db_session.add(failed)
    db_session.commit()

    service = AutomationService()

    assert service._should_skip_existing_application(failed, dry_run=True) is False


def test_applied_existing_application_is_skipped(db_session):
    job = Job(linkedin_job_id="job-6", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    applied = Application(job_id=job.id, status="applied")
    db_session.add(applied)
    db_session.commit()

    service = AutomationService()

    assert service._should_skip_existing_application(applied, dry_run=True) is True


def test_dry_run_existing_application_is_skipped_only_during_dry_run(db_session):
    job = Job(linkedin_job_id="job-7", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    dry_run_app = Application(job_id=job.id, status="dry_run")
    db_session.add(dry_run_app)
    db_session.commit()

    service = AutomationService()

    assert service._should_skip_existing_application(dry_run_app, dry_run=True) is True
    assert service._should_skip_existing_application(dry_run_app, dry_run=False) is False
