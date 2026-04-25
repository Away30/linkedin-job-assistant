"""Session primitives for one LinkedIn Easy Apply modal transaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class EasyApplyStepState(BaseModel):
    """Current state for a single Easy Apply modal step."""

    step_index: int = 0
    resolved_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class EasyApplyResult(BaseModel):
    """Structured result payload for one Easy Apply transaction."""

    success: bool
    failure_type: str | None = None
    final_action: str = "unknown"
    cleanup_success: bool = True
    steps_completed: int = 0
    resolved_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


@dataclass
class EasyApplySession:
    """Holds modal state and action detection logic for one apply flow."""

    modal: Any
    step_state: EasyApplyStepState = field(default_factory=EasyApplyStepState)

    async def detect_primary_action(self) -> str:
        """Detect the next primary footer action in priority order."""
        buttons = await self.modal.query_selector_all("footer button")
        seen_actions: set[str] = set()

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
