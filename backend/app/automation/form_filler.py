"""Form field detection and filling using label matching."""
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Any
import yaml

try:
    from playwright.async_api import Page, Locator
except ModuleNotFoundError:  # pragma: no cover - test env without playwright
    Page = Any
    Locator = Any

try:
    from app.automation.human_simulator import HumanSimulator
except ModuleNotFoundError:  # pragma: no cover - test env without playwright
    class HumanSimulator:
        async def short_delay(self):
            return None

        async def type_like_human(self, locator: Any, text: str):
            await locator.fill(text)

        async def human_click(self, locator: Any):
            await locator.click()
from app.config import settings

logger = logging.getLogger(__name__)


class FormFiller:
    """Detects form fields and fills them using pre-configured answers."""

    def __init__(self):
        self.human = HumanSimulator()
        self.form_answers: dict = {}
        self._load_answers()

    def _load_answers(self):
        """Load form answers from YAML config."""
        yaml_path = settings.FORM_ANSWERS_PATH
        if yaml_path.exists():
            with open(yaml_path, "r") as f:
                self.form_answers = yaml.safe_load(f) or {}

    def reload_answers(self):
        """Reload answers from YAML (for hot-reload)."""
        self._load_answers()

    def _find_answer(self, label: str) -> Optional[str]:
        """Find matching answer for a form field label using fuzzy matching."""
        label_lower = label.lower().strip()

        # Direct match
        for key, value in self.form_answers.items():
            if key.lower() == label_lower:
                return str(value)

        # Partial/keyword match
        for key, value in self.form_answers.items():
            key_lower = key.lower()
            if key_lower in label_lower or label_lower in key_lower:
                return str(value)

        # Common pattern matching
        patterns = {
            r'years?\s*of\s*experience': 'years_of_experience',
            r'work\s*authorization|authorized\s*to\s*work|legally\s*authorized': 'work_authorization',
            r'sponsor': 'sponsorship',
            r'salary|compensation|pay': 'salary_expectation',
            r'start\s*date|earliest\s*start|when\s*can\s*you\s*start': 'start_date',
            r'willing\s*to\s*relocate|relocation': 'willing_to_relocate',
            r'gender|sex': 'gender',
            r'race|ethnicity': 'ethnicity',
            r'veteran': 'veteran_status',
            r'disability|disabilities': 'disability_status',
            r'phone|mobile|cell': 'phone_number',
            r'email': 'email',
            r'city': 'city',
            r'state': 'state',
            r'country': 'country',
            r'zip\s*code|postal': 'zip_code',
            r'linkedin': 'linkedin_url',
            r'website|portfolio|github': 'website',
            r'cover\s*letter': 'cover_letter',
            r'how\s*did\s*you\s*hear': 'how_did_you_hear',
            r'first\s*name': 'first_name',
            r'last\s*name': 'last_name',
        }

        for pattern, answer_key in patterns.items():
            if re.search(pattern, label_lower):
                if answer_key in self.form_answers:
                    return str(self.form_answers[answer_key])

        return None

    async def fill_text_field(self, page: Page, locator: Locator, label: str) -> bool:
        """Fill a text input field."""
        answer = self._find_answer(label)
        if not answer:
            return False

        try:
            # Validate number fields — skip if answer is not a positive number
            input_type = await locator.get_attribute("type") or ""
            if input_type == "number":
                try:
                    val = float(answer)
                    if val <= 0:
                        logger.debug("Skipping number field '%s': value %s <= 0", label, answer)
                        return False
                except ValueError:
                    logger.debug("Skipping number field '%s': '%s' is not a number", label, answer)
                    return False

            await locator.click()
            await locator.fill("")  # Clear first
            await self.human.short_delay()
            try:
                await self.human.type_like_human(locator, answer)
            except Exception:
                await locator.fill(answer)
            return True
        except Exception as e:
            logger.warning("fill_text_field failed for '%s': %s", label, e)
            return False

    async def fill_select_field(self, page: Page, locator: Locator, label: str) -> bool:
        """Fill a select/dropdown field."""
        answer = self._find_answer(label)
        if not answer:
            return False

        try:
            # Try to find matching option
            options = await locator.locator("option").all()
            answer_lower = answer.lower()

            best_match = None
            for opt in options:
                opt_text = (await opt.inner_text()).strip().lower()
                opt_value = (await opt.get_attribute("value") or "").lower()

                if answer_lower == opt_text or answer_lower == opt_value:
                    best_match = await opt.get_attribute("value")
                    break
                elif answer_lower in opt_text:
                    best_match = await opt.get_attribute("value")

            if best_match:
                await locator.select_option(value=best_match)
                return True

            # Try selecting by visible text containing answer
            try:
                await locator.select_option(label=answer)
                return True
            except Exception:
                pass

            # Select first non-empty option as fallback for "Yes/No" type questions
            if answer_lower in ["yes", "true", "1"]:
                for opt in options:
                    val = await opt.get_attribute("value")
                    text = (await opt.inner_text()).strip().lower()
                    if text in ["yes", "true"] or val in ["yes", "true", "1"]:
                        await locator.select_option(value=val)
                        return True

            return False
        except Exception as e:
            logger.warning("fill_select_field failed for '%s': %s", label, e)
            return False

    async def fill_radio_field(self, page: Page, fieldset: Locator, label: str) -> bool:
        """Fill a radio button group."""
        answer = self._find_answer(label)
        if not answer:
            return False

        try:
            answer_lower = answer.lower()
            radios = await fieldset.locator('input[type="radio"]').all()

            for radio in radios:
                # Get associated label
                radio_id = await radio.get_attribute("id")
                if radio_id:
                    radio_label = await fieldset.locator(f'label[for="{radio_id}"]').first.inner_text()
                    if answer_lower in radio_label.lower():
                        await self.human.human_click(radio)
                        return True

            return False
        except Exception as e:
            logger.warning("fill_radio_field failed for '%s': %s", label, e)
            return False

    async def fill_checkbox_field(self, page: Page, locator: Locator, label: str) -> bool:
        """Fill a checkbox field."""
        answer = self._find_answer(label)
        if not answer:
            return False

        try:
            should_check = answer.lower() in ["yes", "true", "1", "checked"]
            is_checked = await locator.is_checked()

            if should_check != is_checked:
                await self.human.human_click(locator)
            return True
        except Exception as e:
            logger.warning("fill_checkbox_field failed for '%s': %s", label, e)
            return False

    async def detect_and_fill_fields(self, container: Page) -> dict[str, list[str]]:
        """Detect and fill visible/editable text fields inside a modal/container."""
        result = {
            "resolved_fields": [],
            "unresolved_fields": [],
            "validation_errors": [],
        }

        text_inputs = await container.query_selector_all(
            'input[type="text"], input[type="email"], input[type="tel"], input[type="number"], input[type="url"], textarea'
        )
        for field in text_inputs:
            if not await self._is_visible_and_editable(field):
                continue

            label = await self._get_field_label(container, field)
            if not label:
                continue

            filled = await self.fill_text_field(container, field, label)
            if filled:
                result["resolved_fields"].append(label)
                continue

            if await self._is_required_field(field):
                result["unresolved_fields"].append(label)

        return result

    async def _is_visible_and_editable(self, field: Any) -> bool:
        """Return True when field is visible and enabled/editable."""
        try:
            is_visible = True
            if hasattr(field, "is_visible"):
                is_visible = await field.is_visible()

            is_enabled = True
            if hasattr(field, "is_enabled"):
                is_enabled = await field.is_enabled()

            readonly = await field.get_attribute("readonly")
            aria_readonly = await field.get_attribute("aria-readonly")
            is_readonly = (readonly is not None) or (str(aria_readonly).lower() == "true")

            return bool(is_visible and is_enabled and not is_readonly)
        except Exception:
            return False

    async def _is_required_field(self, field: Any) -> bool:
        """Check if a field is explicitly marked as required."""
        required = await field.get_attribute("required")
        aria_required = await field.get_attribute("aria-required")
        return (required is not None) or (str(aria_required).lower() == "true")

    async def _get_field_label(self, page, element) -> str:
        """Get the label text for a form element."""
        try:
            # Try aria-label
            aria = await element.get_attribute("aria-label")
            if aria:
                return aria.strip()

            # Try associated label element
            el_id = await element.get_attribute("id")
            if el_id:
                label = await page.query_selector(f'label[for="{el_id}"]')
                if label:
                    return (await label.inner_text()).strip()

            # Try placeholder
            placeholder = await element.get_attribute("placeholder")
            if placeholder:
                return placeholder.strip()

            # Try parent label
            parent = await element.evaluate_handle("el => el.closest('label')")
            if parent:
                text = await parent.evaluate("el => el.textContent")
                if text:
                    return text.strip()[:100]
        except Exception as e:
            logger.debug("_get_field_label failed: %s", e)
        return ""


form_filler = FormFiller()
