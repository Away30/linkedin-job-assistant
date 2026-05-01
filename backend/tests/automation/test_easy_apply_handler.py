import sys
import types

import pytest

playwright_module = types.ModuleType("playwright")
playwright_async_api = types.ModuleType("playwright.async_api")
playwright_async_api.async_playwright = object
playwright_async_api.Browser = object
playwright_async_api.BrowserContext = object
playwright_async_api.Page = object
playwright_async_api.Locator = object
playwright_async_api.Playwright = object
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
                "step_index": 1,
            },
        )()

    async def detect_primary_action(self):
        return self.action


@pytest.mark.asyncio
async def test_apply_dismisses_stale_discard_confirmation_before_clicking_easy_apply(monkeypatch):
    handler = EasyApplyHandler()
    events = []

    class FakeButton:
        async def is_visible(self):
            return True

        async def click(self):
            events.append("discard_clicked")

    class FakeDialog:
        async def is_visible(self):
            return True

        async def query_selector(self, selector):
            assert "data-test-dialog-primary-btn" in selector
            return FakeButton()

    class FakePage:
        def __init__(self):
            self.dialog_available = True

        async def query_selector_all(self, selector):
            if "easy-apply-discard-confirmation" in selector and self.dialog_available:
                self.dialog_available = False
                return [FakeDialog()]
            return []

    async def fake_click_easy_apply_button(page):
        events.append("easy_apply_clicked")
        return False

    async def fake_is_modal_open(page):
        return None

    async def fake_short_delay():
        return None

    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler.human, "short_delay", fake_short_delay)

    result = await handler.apply(page=FakePage(), dry_run=True)

    assert events == ["discard_clicked", "easy_apply_clicked"]
    assert result["success"] is False


@pytest.mark.asyncio
async def test_apply_reopens_easy_apply_when_discard_confirmation_appears_after_click(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="submit")
    events = []
    dismiss_results = iter([False, True, False])

    async def fake_dismiss_discard_confirmation(page):
        dismissed = next(dismiss_results)
        if dismissed:
            events.append("discard_clicked")
        return dismissed

    async def fake_click_easy_apply_button(page):
        events.append("easy_apply_clicked")
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        events.append("fill_step")
        return EasyApplyResult(success=True, final_action="submit")

    async def fake_cleanup_modal(page):
        return True

    async def fake_random_delay(*args, **kwargs):
        return None

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "_dismiss_discard_confirmation", fake_dismiss_discard_confirmation)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)
    monkeypatch.setattr(handler, "_cleanup_modal", fake_cleanup_modal)
    monkeypatch.setattr(handler.human, "random_delay", fake_random_delay)

    result = await handler.apply(page=object(), dry_run=True, max_steps=1)

    assert result["success"] is True
    assert events == ["easy_apply_clicked", "discard_clicked", "easy_apply_clicked", "fill_step"]


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
async def test_apply_attempts_cleanup_on_unresolved_failure(monkeypatch):
    handler = EasyApplyHandler()
    cleaned = {"called": False}

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
            resolved_fields=["Phone"],
            unresolved_fields=["Code pays"],
            validation_errors=[],
        )

    async def fake_cleanup_modal(page):
        cleaned["called"] = True
        return True

    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)
    monkeypatch.setattr(handler, "_cleanup_modal", fake_cleanup_modal)

    result = await handler.apply(page=object(), dry_run=True)

    assert result["failure_type"] == "field_unresolved"
    assert cleaned["called"] is True


@pytest.mark.asyncio
async def test_apply_continues_when_easy_apply_modal_is_already_open(monkeypatch):
    handler = EasyApplyHandler()
    modal = object()

    async def fake_click_easy_apply_button(page):
        return False

    async def fake_is_modal_open(page):
        return modal

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=False,
            failure_type="field_unresolved",
            final_action="blocked",
            cleanup_success=False,
            resolved_fields=["Phone"],
            unresolved_fields=["Code pays"],
            validation_errors=[],
        )

    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)

    result = await handler.apply(page=object(), dry_run=True)

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

    async def fake_cleanup_modal(page):
        return True

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)
    monkeypatch.setattr(handler, "_cleanup_modal", fake_cleanup_modal)

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

    assert result["success"] is False
    assert result["failure_type"] == "cleanup_not_confirmed"
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
async def test_fill_and_validate_step_returns_field_unresolved(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next")
    session.modal = object()

    async def fake_detect_and_fill_fields(container):
        return {
            "resolved_fields": ["Email"],
            "unresolved_fields": ["Work authorization"],
            "validation_errors": [],
        }

    monkeypatch.setattr("app.automation.easy_apply.form_filler.detect_and_fill_fields", fake_detect_and_fill_fields)

    result = await handler._fill_and_validate_step(page=object(), session=session, resume_path=None)

    assert result.success is False
    assert result.failure_type == "field_unresolved"
    assert result.final_action == "blocked"
    assert result.unresolved_fields == ["Work authorization"]


@pytest.mark.asyncio
async def test_fill_and_validate_step_returns_field_validation_failed(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next")
    session.modal = object()

    async def fake_detect_and_fill_fields(container):
        return {
            "resolved_fields": ["Email"],
            "unresolved_fields": [],
            "validation_errors": ["Years: answer must be numeric"],
        }

    monkeypatch.setattr("app.automation.easy_apply.form_filler.detect_and_fill_fields", fake_detect_and_fill_fields)

    result = await handler._fill_and_validate_step(page=object(), session=session, resume_path=None)

    assert result.success is False
    assert result.failure_type == "field_validation_failed"
    assert result.final_action == "blocked"
    assert result.validation_errors == ["Years: answer must be numeric"]


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
        async def query_selector_all(self, selector):
            observed["selector"] = selector
            return []

    await handler.is_modal_open(FakePage())

    assert "[role=\"dialog\"]" not in observed["selector"]
    assert "jobs-easy-apply" in observed["selector"]


@pytest.mark.asyncio
async def test_is_modal_open_prefers_visible_current_modal():
    handler = EasyApplyHandler()

    class FakeModal:
        def __init__(self, visible):
            self.visible = visible

        async def is_visible(self):
            return self.visible

    hidden_modal = FakeModal(False)
    visible_modal = FakeModal(True)

    class FakePage:
        async def query_selector_all(self, selector):
            return [hidden_modal, visible_modal]

    selected = await handler.is_modal_open(FakePage())

    assert selected is visible_modal


@pytest.mark.asyncio
async def test_apply_localized_submit_detects_and_clicks_action(monkeypatch):
    handler = EasyApplyHandler()
    clicked = {"value": False}

    class FakeButton:
        def __init__(self, text):
            self._text = text

        async def is_visible(self):
            return True

        async def inner_text(self):
            return self._text

        async def click(self):
            clicked["value"] = True

    class FakeModal:
        async def query_selector_all(self, selector):
            assert selector == "footer button"
            return [FakeButton("投递申请")]

        async def query_selector(self, selector):
            return None

    modal = FakeModal()
    session = handler._create_session(modal)

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return modal

    async def fake_detect_and_fill_fields(container):
        return {
            "resolved_fields": ["Email"],
            "unresolved_fields": [],
            "validation_errors": [],
        }

    async def fake_confirm_submit_success(page):
        return True

    async def fake_short_delay():
        return None

    async def fake_random_delay(*args, **kwargs):
        return None

    async def fake_human_click(locator):
        await locator.click()

    monkeypatch.setattr(handler, "_create_session", lambda _: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_confirm_submit_success", fake_confirm_submit_success)
    monkeypatch.setattr("app.automation.easy_apply.form_filler.detect_and_fill_fields", fake_detect_and_fill_fields)
    monkeypatch.setattr(handler.human, "short_delay", fake_short_delay)
    monkeypatch.setattr(handler.human, "random_delay", fake_random_delay)
    monkeypatch.setattr(handler.human, "human_click", fake_human_click)

    result = await handler.apply(page=object(), dry_run=False, max_steps=1)

    assert result["success"] is True
    assert result["final_action"] == "submit"
    assert clicked["value"] is True


@pytest.mark.asyncio
async def test_cleanup_modal_clears_discard_confirmation_before_dismiss(monkeypatch):
    handler = EasyApplyHandler()
    state = {"modal_open": True, "discard_clicked": False}

    async def fake_is_modal_open(page):
        return object() if state["modal_open"] else None

    async def fake_dismiss_discard_confirmation(page):
        state["discard_clicked"] = True
        state["modal_open"] = False
        return True

    async def fake_dismiss_modal(page):
        raise AssertionError("dismiss_modal should not click under discard confirmation")

    async def fake_short_delay():
        return None

    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_dismiss_discard_confirmation", fake_dismiss_discard_confirmation)
    monkeypatch.setattr(handler, "dismiss_modal", fake_dismiss_modal)
    monkeypatch.setattr(handler.human, "short_delay", fake_short_delay)

    assert await handler._cleanup_modal(page=object()) is True
    assert state["discard_clicked"] is True


@pytest.mark.asyncio
async def test_apply_localized_submit_confirmation_uses_real_confirmation_logic(monkeypatch):
    handler = EasyApplyHandler()
    clicked_submit = {"value": False}
    clicked_close = {"value": False}
    state = {"modal_open": True}

    class FakeButton:
        def __init__(self, text, click_fn=None):
            self._text = text
            self._click_fn = click_fn

        async def is_visible(self):
            return True

        async def inner_text(self):
            return self._text

        async def click(self):
            if self._click_fn:
                self._click_fn()

    class FakeModal:
        async def query_selector_all(self, selector):
            assert selector == "footer button"
            return [FakeButton("投递申请", click_fn=lambda: clicked_submit.update(value=True))]

        async def query_selector(self, selector):
            return None

        async def is_visible(self):
            return True

    modal = FakeModal()
    session = handler._create_session(modal)

    class FakePage:
        async def query_selector_all(self, selector):
            if state["modal_open"]:
                return [modal]
            return []

        async def query_selector(self, selector):
            if "完成" in selector:
                return FakeButton("完成", click_fn=lambda: (clicked_close.update(value=True), state.update(modal_open=False)))
            return None

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_detect_and_fill_fields(container):
        return {
            "resolved_fields": ["Email"],
            "unresolved_fields": [],
            "validation_errors": [],
        }

    async def fake_short_delay():
        return None

    async def fake_random_delay(*args, **kwargs):
        return None

    async def fake_human_click(locator):
        await locator.click()

    monkeypatch.setattr(handler, "_create_session", lambda _: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr("app.automation.easy_apply.form_filler.detect_and_fill_fields", fake_detect_and_fill_fields)
    monkeypatch.setattr(handler.human, "short_delay", fake_short_delay)
    monkeypatch.setattr(handler.human, "random_delay", fake_random_delay)
    monkeypatch.setattr(handler.human, "human_click", fake_human_click)

    result = await handler.apply(page=FakePage(), dry_run=False, max_steps=1)

    assert result["success"] is True
    assert clicked_submit["value"] is True
    assert clicked_close["value"] is True
