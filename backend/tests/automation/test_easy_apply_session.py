import pytest

from app.automation.easy_apply_session import (
    EasyApplyResult,
    EasyApplySession,
    EasyApplyStepState,
)


class FakeButton:
    def __init__(self, text: str, visible: bool = True):
        self._text = text
        self._visible = visible

    async def is_visible(self):
        return self._visible

    async def inner_text(self):
        return self._text


class FakeModal:
    def __init__(self, buttons):
        self.buttons = buttons

    async def query_selector_all(self, selector: str):
        assert selector == "footer button"
        return self.buttons


@pytest.mark.asyncio
async def test_detect_primary_action_prefers_submit_over_next():
    session = EasyApplySession(modal=FakeModal([
        FakeButton("Next"),
        FakeButton("Submit application"),
    ]))

    action = await session.detect_primary_action()

    assert action == "submit"


@pytest.mark.asyncio
async def test_detect_primary_action_returns_review_when_no_submit():
    session = EasyApplySession(modal=FakeModal([
        FakeButton("Review your application"),
        FakeButton("Next"),
    ]))

    action = await session.detect_primary_action()

    assert action == "review"


@pytest.mark.asyncio
async def test_detect_primary_action_maps_continue_to_next():
    session = EasyApplySession(modal=FakeModal([
        FakeButton("Continue to next step"),
    ]))

    action = await session.detect_primary_action()

    assert action == "next"


@pytest.mark.asyncio
async def test_detect_primary_action_ignores_hidden_buttons_and_returns_unknown():
    session = EasyApplySession(modal=FakeModal([
        FakeButton("Submit application", visible=False),
    ]))

    action = await session.detect_primary_action()

    assert action == "unknown"


@pytest.mark.asyncio
async def test_step_state_tracks_unresolved_and_validation_errors():
    session = EasyApplySession(modal=FakeModal([]))
    session.step_state = EasyApplyStepState(
        step_index=2,
        resolved_fields=["Email"],
        unresolved_fields=["Work authorization"],
        validation_errors=["Select an option"],
    )

    assert session.step_state.unresolved_fields == ["Work authorization"]
    assert session.step_state.validation_errors == ["Select an option"]


def test_result_payload_contains_failure_type_and_cleanup_flag():
    result = EasyApplyResult(
        success=False,
        failure_type="field_unresolved",
        final_action="blocked",
        cleanup_success=False,
        resolved_fields=["Email"],
        unresolved_fields=["Work authorization"],
        validation_errors=["Select an option"],
    )

    payload = result.model_dump()

    assert payload["failure_type"] == "field_unresolved"
    assert payload["cleanup_success"] is False
    assert payload["unresolved_fields"] == ["Work authorization"]
