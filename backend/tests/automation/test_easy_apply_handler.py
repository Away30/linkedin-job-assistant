import sys
import types

import pytest

playwright_module = types.ModuleType("playwright")
playwright_async_api = types.ModuleType("playwright.async_api")
playwright_async_api.Page = object
playwright_async_api.Locator = object
playwright_module.async_api = playwright_async_api
sys.modules.setdefault("playwright", playwright_module)
sys.modules.setdefault("playwright.async_api", playwright_async_api)

from app.automation.easy_apply import EasyApplyHandler
from app.automation.easy_apply_session import EasyApplyResult


class StubSession:
    def __init__(self, action: str, unresolved=None, validation_errors=None):
        self.action = action
        self.modal = object()
        self.step_state = type(
            "State",
            (),
            {
                "resolved_fields": ["Email"],
                "unresolved_fields": unresolved or [],
                "validation_errors": validation_errors or [],
            },
        )()

    async def detect_primary_action(self):
        return self.action


@pytest.mark.asyncio
async def test_apply_blocks_when_unresolved_fields_exist(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next", unresolved=["Work authorization"])

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=False,
            failure_type="field_unresolved",
            final_action="blocked",
            cleanup_success=False,
            resolved_fields=["Email"],
            unresolved_fields=["Work authorization"],
            validation_errors=[],
        )

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)

    result = await handler.apply(page=object(), dry_run=True)

    assert result["success"] is False
    assert result["failure_type"] == "field_unresolved"


@pytest.mark.asyncio
async def test_apply_blocks_when_validation_errors_exist(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next", validation_errors=["Invalid phone number"])

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=False,
            failure_type="field_validation_failed",
            final_action="blocked",
            cleanup_success=False,
            resolved_fields=["Email"],
            unresolved_fields=[],
            validation_errors=["Invalid phone number"],
        )

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)

    result = await handler.apply(page=object(), dry_run=True)

    assert result["success"] is False
    assert result["failure_type"] == "field_validation_failed"


@pytest.mark.asyncio
async def test_apply_intercepts_submit_in_dry_run(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="submit")

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=True,
            final_action="submit",
            cleanup_success=False,
            resolved_fields=["Email"],
            unresolved_fields=[],
            validation_errors=[],
        )

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)

    result = await handler.apply(page=object(), dry_run=True)

    assert result["success"] is True
    assert result["failure_type"] == "submit_intercepted_dry_run"
    assert result["final_action"] == "submit"


@pytest.mark.asyncio
async def test_apply_reports_cleanup_failure_in_dry_run(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="submit")

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=True,
            final_action="submit",
            cleanup_success=False,
            resolved_fields=["Email"],
            unresolved_fields=[],
            validation_errors=[],
        )

    async def fake_cleanup_modal(page):
        return False

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)
    monkeypatch.setattr(handler, "_cleanup_modal", fake_cleanup_modal)

    result = await handler.apply(page=object(), dry_run=True)

    assert result["success"] is True
    assert result["failure_type"] == "submit_intercepted_dry_run"
    assert result["cleanup_success"] is False


@pytest.mark.asyncio
async def test_apply_returns_advance_button_not_found_when_no_action(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="unknown")

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=False,
            failure_type="advance_button_not_found",
            final_action="unknown",
            cleanup_success=False,
            resolved_fields=["Email"],
            unresolved_fields=[],
            validation_errors=[],
        )

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)

    result = await handler.apply(page=object(), dry_run=False)

    assert result["success"] is False
    assert result["failure_type"] == "advance_button_not_found"


@pytest.mark.asyncio
async def test_apply_requires_submit_confirmation(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="submit")

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=True,
            final_action="submit",
            cleanup_success=False,
            resolved_fields=["Email"],
            unresolved_fields=[],
            validation_errors=[],
        )

    async def fake_click_session_action(session, action):
        return True

    async def fake_confirm_submit_success(page):
        return False

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)
    monkeypatch.setattr(handler, "_click_session_action", fake_click_session_action)
    monkeypatch.setattr(handler, "_confirm_submit_success", fake_confirm_submit_success)

    result = await handler.apply(page=object(), dry_run=False)

    assert result["success"] is False
    assert result["failure_type"] == "cleanup_not_confirmed"


@pytest.mark.asyncio
async def test_apply_preserves_unexpected_step_failure_classification(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next")

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=False,
            final_action="blocked",
            cleanup_success=False,
            resolved_fields=[],
            unresolved_fields=[],
            validation_errors=["unexpected_step_error:ValueError"],
        )

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)

    result = await handler.apply(page=object(), dry_run=False)

    assert result["success"] is False
    assert result["failure_type"] is None
    assert "Unexpected step failure" in result["errors"][0]


@pytest.mark.asyncio
async def test_fill_and_validate_step_uses_modal_scope(monkeypatch):
    handler = EasyApplyHandler()
    modal = object()
    page = object()

    class SessionWithModal(StubSession):
        def __init__(self):
            super().__init__(action="next")
            self.modal = modal

    session = SessionWithModal()

    called_with = {}

    async def fake_detect_and_fill_fields(container):
        called_with["container"] = container
        return {
            "resolved_fields": ["Email"],
            "unresolved_fields": [],
            "validation_errors": [],
        }

    monkeypatch.setattr("app.automation.easy_apply.form_filler.detect_and_fill_fields", fake_detect_and_fill_fields)

    result = await handler._fill_and_validate_step(page=page, session=session, resume_path=None)

    assert called_with["container"] is modal
    assert result.success is True
    assert result.final_action == "next"


@pytest.mark.asyncio
async def test_fill_and_validate_step_reports_unexpected_error(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next")
    modal = object()
    session.modal = modal

    async def fake_detect_and_fill_fields(container):
        raise ValueError("boom")

    monkeypatch.setattr("app.automation.easy_apply.form_filler.detect_and_fill_fields", fake_detect_and_fill_fields)

    result = await handler._fill_and_validate_step(page=object(), session=session, resume_path=None)

    assert result.success is False
    assert result.failure_type is None
    assert result.final_action == "blocked"
    assert result.validation_errors == ["unexpected_step_error:ValueError"]


@pytest.mark.asyncio
async def test_apply_refreshes_modal_handle_between_steps(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next")
    modal_a = object()
    modal_b = object()
    seen_modals = []
    step_counter = {"count": 0}
    modal_sequence = iter([modal_a, modal_a, modal_b])

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return next(modal_sequence)

    async def fake_fill_and_validate_step(page, session, resume_path):
        seen_modals.append(session.modal)
        if step_counter["count"] == 0:
            step_counter["count"] += 1
            return EasyApplyResult(success=True, final_action="next")
        return EasyApplyResult(success=True, final_action="submit")

    async def fake_click_session_action(session, action):
        return True

    async def fake_cleanup_modal(page):
        return True

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)
    monkeypatch.setattr(handler, "_click_session_action", fake_click_session_action)
    monkeypatch.setattr(handler, "_cleanup_modal", fake_cleanup_modal)

    result = await handler.apply(page=object(), dry_run=True, max_steps=3)

    assert result["success"] is True
    assert seen_modals == [modal_a, modal_b]


@pytest.mark.asyncio
async def test_is_modal_open_uses_easy_apply_specific_selectors():
    handler = EasyApplyHandler()
    observed = {}

    class FakePage:
        async def query_selector(self, selector):
            observed["selector"] = selector
            return None

    await handler.is_modal_open(FakePage())

    assert "[role=\"dialog\"]" not in observed["selector"]
    assert "jobs-easy-apply" in observed["selector"]
