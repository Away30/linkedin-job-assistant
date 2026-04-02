"""Form field detection and filling using label matching."""
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Any
import yaml
from playwright.async_api import Page, Locator
from app.automation.human_simulator import HumanSimulator
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
            await locator.click()
            await locator.fill("")  # Clear first
            await self.human.short_delay()
            await self.human.type_like_human(locator, answer)
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

    async def detect_and_fill_fields(self, page: Page) -> dict[str, bool]:
        """Detect all form fields on the page and attempt to fill them."""
        results = {}

        # Text inputs
        text_inputs = await page.query_selector_all('input[type="text"], input[type="email"], input[type="tel"], input[type="number"], input[type="url"], textarea')
        for inp in text_inputs:
            label = await self._get_field_label(page, inp)
            if label:
                inp_id = await inp.get_attribute("id")
                locator = page.locator(f'#{inp_id}') if inp_id else inp
                results[label] = await self.fill_text_field(page, locator, label)

        # Select dropdowns
        selects = await page.query_selector_all('select')
        for sel in selects:
            label = await self._get_field_label(page, sel)
            if label:
                sel_id = await sel.get_attribute("id")
                if sel_id:
                    locator = page.locator(f'#{sel_id}')
                    results[label] = await self.fill_select_field(page, locator, label)

        # Radio groups
        fieldsets = await page.query_selector_all('fieldset')
        for fs in fieldsets:
            legend = await fs.query_selector('legend, .fb-dash-form-element__label')
            if legend:
                label = (await legend.inner_text()).strip()
                locator = page.locator(f'fieldset:has-text("{label[:30]}")')
                results[label] = await self.fill_radio_field(page, locator, label)

        # Standalone checkboxes (e.g., "I agree to terms")
        checkboxes = await page.query_selector_all('input[type="checkbox"]')
        for cb in checkboxes:
            cb_id = await cb.get_attribute("id")
            label = await self._get_field_label(page, cb)
            if label and cb_id:
                locator = page.locator(f'#{cb_id}')
                results[label] = await self.fill_checkbox_field(page, locator, label)

        return results

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
