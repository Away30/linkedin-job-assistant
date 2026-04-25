"""Session primitives for one LinkedIn Easy Apply modal transaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, Field

PrimaryAction = Literal["submit", "review", "next", "unknown"]
FailureType = Literal[
    "field_unresolved",
    "field_validation_failed",
    "submit_intercepted_dry_run",
    "advance_button_not_found",
    "modal_not_found",
    "cleanup_not_confirmed",
]
FinalAction = Literal["submit", "review", "next", "blocked", "unknown"]


class ModalButton(Protocol):
    async def is_visible(self) -> bool: ...

    async def inner_text(self) -> str: ...


class EasyApplyModal(Protocol):
    async def query_selector_all(self, selector: str) -> list[ModalButton]: ...


class EasyApplyStepState(BaseModel):
    """Current state for a single Easy Apply modal step."""

    step_index: int = 1
    resolved_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class EasyApplyResult(BaseModel):
    """Structured result payload for one Easy Apply transaction."""

    success: bool
    failure_type: FailureType | None = None
    final_action: FinalAction = "unknown"
    cleanup_success: bool = False
    steps_completed: int = 0
    resolved_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


@dataclass
class EasyApplySession:
    """Holds modal state and action detection logic for one apply flow."""

    modal: EasyApplyModal
    step_state: EasyApplyStepState = field(default_factory=EasyApplyStepState)

    async def detect_primary_action(self) -> PrimaryAction:
        """Detect the next primary footer action in priority order."""
        buttons = await self.modal.query_selector_all("footer button")
        seen_actions: set[PrimaryAction] = set()

        for button in buttons:
            if not await button.is_visible():
                continue

            text = (await button.inner_text()).strip().lower()
            if "submit" in text:
                seen_actions.add("submit")
            elif "review" in text:
                seen_actions.add("review")
            elif "next" in text or "continue" in text:
                seen_actions.add("next")

        for action in ("submit", "review", "next"):
            if action in seen_actions:
                return action

        return "unknown"
