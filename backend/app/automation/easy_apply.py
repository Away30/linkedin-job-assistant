"""LinkedIn Easy Apply multi-step modal handler."""
import logging
from pathlib import Path
from typing import Any, Optional

try:
    from playwright.async_api import Page
except ModuleNotFoundError:  # pragma: no cover - test env without playwright
    Page = Any

from app.automation.human_simulator import HumanSimulator
from app.automation.form_filler import form_filler
from app.automation.easy_apply_session import ACTION_LABEL_TOKENS, EasyApplyResult, EasyApplySession
from app.config import settings

logger = logging.getLogger(__name__)

EASY_APPLY_OVERLAY_GUARD_SELECTOR = '[data-test-modal-container], .artdeco-modal-overlay'


class EasyApplyHandler:
    """Handles the LinkedIn Easy Apply modal flow."""

    def __init__(self):
        self.human = HumanSimulator()

    async def click_easy_apply_button(self, page: Page) -> bool:
        """Click the Easy Apply button on a job listing."""
        try:
            # Multiple possible selectors for Easy Apply button
            selectors = [
                'button.jobs-apply-button',
                '.jobs-apply-button--top-card button',
                'button[aria-label*="Easy Apply"]',
                'button[aria-label*="easy apply"]',
                '.jobs-s-apply button',
                'button[data-control-name*="apply"]',
            ]

            for selector in selectors:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await self.human.human_click(btn)
                    await self.human.random_delay(2, 4)
                    return True

            # Fallback: find any visible button containing "apply" text
            apply_btns = await page.query_selector_all('button')
            for btn in apply_btns:
                try:
                    if await btn.is_visible():
                        text = (await btn.inner_text()).strip().lower()
                        if "easy apply" in text or "apply" in text or "投递" in text:
                            await self.human.human_click(btn)
                            await self.human.random_delay(2, 4)
                            return True
                except Exception:
                    continue

            return False
        except Exception as e:
            logger.warning("click_easy_apply_button failed: %s", e)
            return False

    async def is_modal_open(self, page: Page) -> bool:
        """Return the active visible Easy Apply modal/container if open."""
        selector = (
            '.jobs-easy-apply-modal, .jobs-easy-apply-content, '
            '[data-test-easy-apply-modal], .easy-apply-modal, '
            'div[aria-label*="Easy Apply"], div[aria-label*="快速申请"]'
        )
        candidates = await page.query_selector_all(selector)
        if not candidates:
            return None

        for candidate in reversed(candidates):
            try:
                if await candidate.is_visible():
                    return candidate
            except Exception:
                continue

        return None

    async def has_blocking_overlay(self, page: Page) -> bool:
        """Return True when an Easy Apply overlay/modal is still blocking the jobs list."""
        try:
            overlay = await page.query_selector(EASY_APPLY_OVERLAY_GUARD_SELECTOR)
            if overlay:
                try:
                    return bool(await overlay.is_visible())
                except Exception:
                    return True
        except Exception as e:
            logger.debug("Overlay probe failed: %s", e)

        try:
            return bool(await self.is_modal_open(page))
        except Exception as e:
            logger.debug("Modal probe failed while checking blocking overlay: %s", e)
            return False

    async def get_current_step(self, page: Page) -> tuple[int, int]:
        """Get current step info. Uses iterative tracking, not progress estimation."""
        # Step detection is now handled by the apply() loop counter
        # This method is kept for compatibility but steps are tracked externally
        return (1, 1)

    async def fill_current_step(self, page: Page, resume_path: Optional[str] = None) -> bool:
        """Back-compat wrapper that fills the active modal step only."""
        try:
            modal = await self.is_modal_open(page)
            if not modal:
                return False

            session = self._create_session(modal)
            result = await self._fill_and_validate_step(page, session, resume_path)
            return result.success
        except Exception as e:
            logger.warning("fill_current_step failed: %s", e)
            return False

    def _create_session(self, modal: Any) -> EasyApplySession:
        """Create a session wrapper around the active modal."""
        return EasyApplySession(modal=modal)

    async def _fill_and_validate_step(
        self,
        page: Page,
        session: EasyApplySession,
        resume_path: Optional[str],
    ) -> EasyApplyResult:
        """Fill current modal step and map structured field status into a step result."""
        try:
            await self.human.short_delay()
            if resume_path:
                await self._handle_resume_upload(session.modal, resume_path)

            filled = await form_filler.detect_and_fill_fields(session.modal)
            session.step_state.resolved_fields = list(filled.get("resolved_fields", []))
            session.step_state.unresolved_fields = list(filled.get("unresolved_fields", []))
            session.step_state.validation_errors = list(filled.get("validation_errors", []))

            if session.step_state.unresolved_fields:
                return EasyApplyResult(
                    success=False,
                    failure_type="field_unresolved",
                    final_action="blocked",
                    resolved_fields=session.step_state.resolved_fields,
                    unresolved_fields=session.step_state.unresolved_fields,
                    validation_errors=session.step_state.validation_errors,
                )

            if session.step_state.validation_errors:
                return EasyApplyResult(
                    success=False,
                    failure_type="field_validation_failed",
                    final_action="blocked",
                    resolved_fields=session.step_state.resolved_fields,
                    unresolved_fields=session.step_state.unresolved_fields,
                    validation_errors=session.step_state.validation_errors,
                )

            action = await session.detect_primary_action()
            if action not in ("next", "review", "submit"):
                return EasyApplyResult(
                    success=False,
                    failure_type="advance_button_not_found",
                    final_action="unknown",
                    resolved_fields=session.step_state.resolved_fields,
                    unresolved_fields=session.step_state.unresolved_fields,
                    validation_errors=session.step_state.validation_errors,
                )

            return EasyApplyResult(
                success=True,
                final_action=action,
                resolved_fields=session.step_state.resolved_fields,
                unresolved_fields=session.step_state.unresolved_fields,
                validation_errors=session.step_state.validation_errors,
            )
        except Exception as e:
            logger.warning("_fill_and_validate_step failed: %s", e)
            return EasyApplyResult(
                success=False,
                final_action="blocked",
                validation_errors=[f"unexpected_step_error:{e.__class__.__name__}"],
            )

    async def _handle_resume_upload(self, page: Page, resume_path: str):
        """Upload resume if file input is present."""
        try:
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                path = Path(resume_path)
                if path.exists():
                    await file_input.set_input_files(str(path))
                    await self.human.random_delay(1, 3)
        except Exception as e:
            logger.warning("_handle_resume_upload failed: %s", e)

    async def _click_session_action(self, session: EasyApplySession, action: str) -> bool:
        """Click the detected primary action inside the active modal footer."""
        labels = ACTION_LABEL_TOKENS.get(action, ())
        if not labels:
            return False

        try:
            buttons = await session.modal.query_selector_all("footer button")
            for button in buttons:
                if not await button.is_visible():
                    continue
                text = (await button.inner_text()).strip().lower()
                if any(label in text for label in labels):
                    await self.human.human_click(button)
                    return True
        except Exception as e:
            logger.warning("_click_session_action failed: %s", e)

        return False

    async def _cleanup_modal(self, page: Page) -> bool:
        """Best-effort modal cleanup after dry-run interception."""
        try:
            if not await self.is_modal_open(page):
                return True

            await self.dismiss_modal(page)
            await self.human.short_delay()
            return not bool(await self.is_modal_open(page))
        except Exception as e:
            logger.warning("_cleanup_modal failed: %s", e)
            return False

    async def _confirm_submit_success(self, page: Page) -> bool:
        """Confirm submit moved the flow forward by closing modal or showing terminal dialog."""
        try:
            await self.human.random_delay(1, 2)
            if not await self.is_modal_open(page):
                return True

            close_selectors = [
                'button[aria-label="Dismiss"]',
                'button[aria-label="关闭"]',
                'button:has-text("Done")',
                'button:has-text("完成")',
                'button:has-text("关闭")',
                'button:has-text("知道了")',
            ]
            for selector in close_selectors:
                close_btn = await page.query_selector(selector)
                if close_btn and await close_btn.is_visible():
                    await close_btn.click()
                    await self.human.short_delay()
                    break

            return not bool(await self.is_modal_open(page))
        except Exception as e:
            logger.warning("_confirm_submit_success failed: %s", e)
            return False

    @staticmethod
    def _to_payload(step_result: EasyApplyResult, errors: Optional[list[str]] = None) -> dict:
        payload = step_result.model_dump()
        payload["errors"] = errors or []
        return payload

    async def click_next(self, page: Page, dry_run: bool = False) -> str:
        """Click Next, Review, or Submit button. Returns which action was taken."""
        try:
            # Check for Submit button first
            submit_selectors = [
                'button[aria-label="Submit application"]',
                'button[aria-label="提交申请"]',
                'button:has-text("Submit application")',
                'button:has-text("Submit")',
                'button:has-text("提交")',
            ]
            for selector in submit_selectors:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    if dry_run:
                        logger.info("Dry run: detected Submit button, skipping click")
                        return "dry_run_submit"
                    await self.human.human_click(btn)
                    return "submitted"

            # Check for Review button
            review_selectors = [
                'button[aria-label="Review your application"]',
                'button:has-text("Review")',
                'button:has-text("Review your application")',
            ]
            for selector in review_selectors:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await self.human.human_click(btn)
                    return "review"

            # Click Next button
            next_selectors = [
                'button[aria-label="Continue to next step"]',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'footer button.artdeco-button--primary',
            ]
            for selector in next_selectors:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await self.human.human_click(btn)
                    return "next"

            return "unknown"
        except Exception as e:
            logger.warning("click_next failed: %s", e)
            return "error"

    async def check_for_errors(self, page: Page) -> list[str]:
        """Check for validation errors in the form."""
        errors = []
        try:
            error_elements = await page.query_selector_all('.artdeco-inline-feedback--error, .fb-dash-form-element__error-field')
            for el in error_elements:
                text = (await el.inner_text()).strip()
                if text:
                    errors.append(text)
        except Exception as e:
            logger.warning("check_for_errors failed: %s", e)
        return errors

    async def dismiss_modal(self, page: Page):
        """Close the Easy Apply modal."""
        try:
            dismiss_selectors = [
                'button[aria-label="Dismiss"]',
                '.artdeco-modal__dismiss',
                'button:has-text("Discard")',
            ]
            for selector in dismiss_selectors:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await self.human.short_delay()

                    # Handle "Discard application?" confirmation
                    discard_btn = await page.query_selector('button[data-test-dialog-primary-btn], button:has-text("Discard")')
                    if discard_btn:
                        await discard_btn.click()
                    break
        except Exception as e:
            logger.warning("dismiss_modal failed: %s", e)

    async def apply(self, page: Page, resume_path: Optional[str] = None, max_steps: int = 10, dry_run: bool = False) -> dict:
        """Run Easy Apply as a session with modal-scoped field validation."""
        if not await self.click_easy_apply_button(page):
            return self._to_payload(
                EasyApplyResult(success=False),
                errors=["Could not find Easy Apply button"],
            )

        await self.human.random_delay(2, 4)
        modal = await self.is_modal_open(page)
        if not modal:
            return self._to_payload(
                EasyApplyResult(success=False, failure_type="modal_not_found"),
                errors=["Easy Apply modal did not open"],
            )

        session = self._create_session(modal)

        for step in range(max_steps):
            # LinkedIn often re-renders the dialog between steps; always refresh modal handle.
            current_modal = await self.is_modal_open(page)
            if not current_modal:
                return self._to_payload(
                    EasyApplyResult(success=False, failure_type="modal_not_found"),
                    errors=["Easy Apply modal was replaced or closed before step processing"],
                )
            session.modal = current_modal
            session.step_state.step_index = step + 1
            step_result = await self._fill_and_validate_step(page, session, resume_path)
            step_result.steps_completed = step + 1

            if session.step_state.unresolved_fields:
                return self._to_payload(
                    step_result,
                    errors=[f"Unresolved required fields: {', '.join(session.step_state.unresolved_fields)}"],
                )

            if session.step_state.validation_errors:
                return self._to_payload(
                    step_result,
                    errors=[f"Validation failed: {', '.join(session.step_state.validation_errors)}"],
                )

            if step_result.failure_type == "advance_button_not_found":
                return self._to_payload(
                    step_result,
                    errors=["Could not find Next/Review/Submit button in modal footer"],
                )

            if not step_result.success and step_result.failure_type is None:
                errors = ["Unexpected step failure before detecting advance button"]
                if step_result.validation_errors:
                    errors.append("; ".join(step_result.validation_errors))
                return self._to_payload(step_result, errors=errors)

            if step_result.final_action == "submit" and dry_run:
                cleanup_success = await self._cleanup_modal(page)
                intercepted = EasyApplyResult(
                    success=cleanup_success,
                    failure_type="submit_intercepted_dry_run" if cleanup_success else "cleanup_not_confirmed",
                    final_action="submit",
                    cleanup_success=cleanup_success,
                    steps_completed=step + 1,
                    resolved_fields=step_result.resolved_fields,
                    unresolved_fields=step_result.unresolved_fields,
                    validation_errors=step_result.validation_errors,
                )
                if cleanup_success:
                    return self._to_payload(intercepted, errors=["dry_run: submit skipped"])
                return self._to_payload(
                    intercepted,
                    errors=["dry_run: submit skipped but modal cleanup failed"],
                )

            clicked = await self._click_session_action(session, step_result.final_action)
            if not clicked:
                failed_click = EasyApplyResult(
                    success=False,
                    failure_type="advance_button_not_found",
                    final_action="unknown",
                    steps_completed=step + 1,
                    resolved_fields=step_result.resolved_fields,
                    unresolved_fields=step_result.unresolved_fields,
                    validation_errors=step_result.validation_errors,
                )
                return self._to_payload(
                    failed_click,
                    errors=["Detected action but failed to click modal footer button"],
                )

            if step_result.final_action == "submit":
                confirmed = await self._confirm_submit_success(page)
                if not confirmed:
                    submit_unconfirmed = EasyApplyResult(
                        success=False,
                        failure_type="cleanup_not_confirmed",
                        final_action="submit",
                        steps_completed=step + 1,
                        resolved_fields=step_result.resolved_fields,
                        unresolved_fields=step_result.unresolved_fields,
                        validation_errors=step_result.validation_errors,
                    )
                    return self._to_payload(
                        submit_unconfirmed,
                        errors=["Submit click did not confirm completion or modal close"],
                    )

                submitted = EasyApplyResult(
                    success=True,
                    final_action="submit",
                    steps_completed=step + 1,
                    resolved_fields=step_result.resolved_fields,
                    unresolved_fields=step_result.unresolved_fields,
                    validation_errors=step_result.validation_errors,
                )
                return self._to_payload(submitted)

            await self.human.random_delay(1, 3)

        exhausted = EasyApplyResult(
            success=False,
            failure_type="advance_button_not_found",
            final_action="unknown",
            steps_completed=max_steps,
            resolved_fields=session.step_state.resolved_fields,
            unresolved_fields=session.step_state.unresolved_fields,
            validation_errors=session.step_state.validation_errors,
        )
        return self._to_payload(exhausted, errors=[f"Exceeded max steps ({max_steps}) before submit"])


easy_apply_handler = EasyApplyHandler()
