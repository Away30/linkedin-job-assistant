"""LinkedIn Easy Apply multi-step modal handler."""
import logging
from pathlib import Path
from typing import Optional
from playwright.async_api import Page
from app.automation.human_simulator import HumanSimulator
from app.automation.form_filler import form_filler
from app.config import settings

logger = logging.getLogger(__name__)


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
                '.jobs-s-apply button',
            ]

            for selector in selectors:
                btn = await page.query_selector(selector)
                if btn:
                    text = await btn.inner_text()
                    if "easy apply" in text.lower() or "apply" in text.lower():
                        await self.human.human_click(btn)
                        await self.human.random_delay(2, 4)
                        return True

            return False
        except Exception as e:
            logger.warning("click_easy_apply_button failed: %s", e)
            return False

    async def is_modal_open(self, page: Page) -> bool:
        """Check if Easy Apply modal is open."""
        modal = await page.query_selector('.jobs-easy-apply-modal, .jobs-easy-apply-content, [data-test-modal]')
        return modal is not None

    async def get_current_step(self, page: Page) -> tuple[int, int]:
        """Get current step info. Uses iterative tracking, not progress estimation."""
        # Step detection is now handled by the apply() loop counter
        # This method is kept for compatibility but steps are tracked externally
        return (1, 1)

    async def fill_current_step(self, page: Page, resume_path: Optional[str] = None) -> bool:
        """Fill all fields in the current step of the Easy Apply form."""
        try:
            await self.human.short_delay()

            # Handle resume upload if file input present
            if resume_path:
                await self._handle_resume_upload(page, resume_path)

            # Fill form fields
            results = await form_filler.detect_and_fill_fields(page)

            await self.human.short_delay()
            return True
        except Exception as e:
            logger.warning("fill_current_step failed: %s", e)
            return False

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

    async def click_next(self, page: Page) -> str:
        """Click Next, Review, or Submit button. Returns which action was taken."""
        try:
            # Check for Submit button first
            submit_selectors = [
                'button[aria-label="Submit application"]',
                'button:has-text("Submit application")',
                'button:has-text("Submit")',
            ]
            for selector in submit_selectors:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    await self.human.human_click(btn)
                    return "submitted"

            # Check for Review button
            review_selectors = [
                'button[aria-label="Review your application"]',
                'button:has-text("Review")',
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
        """Complete the full Easy Apply flow."""
        result = {
            "success": False,
            "steps_completed": 0,
            "errors": [],
        }

        # Click Easy Apply button
        if not await self.click_easy_apply_button(page):
            result["errors"].append("Could not find Easy Apply button")
            return result

        # Wait for modal
        await self.human.random_delay(2, 4)
        if not await self.is_modal_open(page):
            result["errors"].append("Easy Apply modal did not open")
            return result

        # Process steps
        for step in range(max_steps):
            await self.fill_current_step(page, resume_path)

            # Check for errors
            errors = await self.check_for_errors(page)
            if errors:
                result["errors"].extend(errors)

            await self.human.random_delay(1, 3)

            action = await self.click_next(page)
            result["steps_completed"] += 1

            if action == "submitted":
                if dry_run:
                    logger.info("Dry run: skipping submit")
                    result["errors"].append("dry_run: submit skipped")
                    await self.dismiss_modal(page)
                    break
                result["success"] = True
                await self.human.random_delay(2, 4)

                # Handle post-submit modal (e.g., "Application sent")
                try:
                    close_btn = await page.query_selector('button[aria-label="Dismiss"], button:has-text("Done")')
                    if close_btn:
                        await close_btn.click()
                except Exception as e:
                    logger.warning("close post-submit modal failed: %s", e)
                break
            elif action == "review":
                await self.human.random_delay(2, 4)
                # On review page, click submit
                submit_action = await self.click_next(page)
                if submit_action == "submitted":
                    result["success"] = True
                    result["steps_completed"] += 1
                break
            elif action in ("error", "unknown"):
                result["errors"].append(f"Failed at step {step + 1}: could not proceed")
                await self.dismiss_modal(page)
                break

            await self.human.random_delay(2, 4)

        return result


easy_apply_handler = EasyApplyHandler()
