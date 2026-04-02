"""Centralized LinkedIn DOM selector registry with YAML config support."""
import logging
from pathlib import Path
from typing import Optional
import yaml
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Default selectors (used when YAML is not available)
_DEFAULTS = {
    "auth": {
        "feed_indicators": [
            '[data-test-id="feed-sort-dropdown"]',
            ".feed-shared-update-v2",
            ".global-nav__me-photo",
        ],
        "login_page": [".login__form_action"],
    },
    "search": {
        "results_container": [".jobs-search-results-list"],
        "job_card": ['[data-job-id]'],
        "job_card_alt": ['[data-occludable-job-id]'],
        "list_item": [".jobs-search-results__list-item"],
        "pagination": [".artdeco-pagination"],
        "next_button": ['.artdeco-pagination__button--next:not([disabled])'],
    },
    "job_detail": {
        "title": [
            ".jobs-unified-top-card__job-title",
            ".job-details-jobs-unified-top-card__job-title h1",
        ],
        "company": [
            ".jobs-unified-top-card__company-name",
            ".job-details-jobs-unified-top-card__company-name",
        ],
        "location": [
            ".jobs-unified-top-card__bullet",
            ".job-details-jobs-unified-top-card__bullet",
        ],
        "description": [".jobs-description__content", ".jobs-box__html-content"],
        "easy_apply_button": [
            ".jobs-apply-button--top-card button",
            ".jobs-apply-button",
        ],
        "job_insights": [".jobs-unified-top-card__job-insight span"],
        "posted_date": [".jobs-unified-top-card__posted-date", "time"],
        "detail_panel": [".jobs-unified-top-card"],
    },
    "easy_apply": {
        "button": [
            "button.jobs-apply-button",
            ".jobs-apply-button--top-card button",
            'button[aria-label*="Easy Apply"]',
            ".jobs-s-apply button",
        ],
        "modal": [
            ".jobs-easy-apply-modal",
            ".jobs-easy-apply-content",
            "[data-test-modal]",
        ],
        "submit_button": [
            'button[aria-label="Submit application"]',
            'button:has-text("Submit application")',
            'button:has-text("Submit")',
        ],
        "review_button": [
            'button[aria-label="Review your application"]',
            'button:has-text("Review")',
        ],
        "next_button": [
            'button[aria-label="Continue to next step"]',
            'button:has-text("Next")',
            "footer button.artdeco-button--primary",
        ],
        "dismiss_button": [
            'button[aria-label="Dismiss"]',
            ".artdeco-modal__dismiss",
            'button:has-text("Discard")',
        ],
        "error_messages": [
            ".artdeco-inline-feedback--error",
            ".fb-dash-form-element__error-field",
        ],
        "progress_bar": [
            ".artdeco-completeness-meter-linear__progress-element"
        ],
    },
    "captcha": {
        "iframe": [
            'iframe[src*="recaptcha"]',
            'iframe[src*="captcha"]',
            'iframe[title*="recaptcha"]',
            'iframe[title*="CAPTCHA"]',
        ],
        "container": [
            ".captcha-container",
            "#captcha-container",
            'div[class*="captcha"]',
            'div[id*="captcha"]',
        ],
        "authwall": [
            'input[name="captcha"]',
            ".authwall-verification-code",
            'input[aria-label*="verification"]',
            'input[placeholder*="verification"]',
            '[data-test-id="authwall-verification"]',
        ],
    },
    "form": {
        "text_inputs": [
            'input[type="text"]',
            'input[type="email"]',
            'input[type="tel"]',
            'input[type="number"]',
            'input[type="url"]',
            "textarea",
        ],
        "selects": ["select"],
        "fieldsets": ["fieldset"],
        "checkboxes": ['input[type="checkbox"]'],
        "file_input": ['input[type="file"]'],
        "legend": ["legend", ".fb-dash-form-element__label"],
    },
}


class SelectorRegistry:
    """Loads and provides selectors with fallback chains."""

    def __init__(self):
        self._selectors: dict = dict(_DEFAULTS)

    def load_from_yaml(self, path: Path) -> None:
        """Override selectors from a YAML file."""
        if not path.exists():
            logger.info("No selector config at %s, using defaults", path)
            return
        with open(path, "r") as f:
            overrides = yaml.safe_load(f)
        if not overrides:
            return
        # Deep merge: override individual selector lists
        for category, selectors in overrides.items():
            if category not in self._selectors:
                self._selectors[category] = selectors
            else:
                self._selectors[category].update(selectors)
        logger.info("Loaded %d selector categories from %s", len(overrides), path)

    def get(self, category: str, name: str) -> list[str]:
        """Get list of fallback selectors for a given category/name."""
        cat = self._selectors.get(category, {})
        selectors = cat.get(name, [])
        if not selectors:
            logger.warning("No selectors found for %s/%s", category, name)
        return selectors

    def get_css(self, category: str, name: str) -> str:
        """Get a combined CSS selector (comma-separated) for first match."""
        return ", ".join(self.get(category, name))

    async def query_selector(self, page: Page, category: str, name: str):
        """Try each selector in order, return first matching element."""
        for selector in self.get(category, name):
            try:
                el = await page.query_selector(selector)
                if el:
                    return el
            except Exception:
                continue
        return None

    async def query_selector_all(self, page: Page, category: str, name: str) -> list:
        """Get all elements matching the first working selector."""
        for selector in self.get(category, name):
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    return elements
            except Exception:
                continue
        return []


# Global singleton
selectors = SelectorRegistry()
