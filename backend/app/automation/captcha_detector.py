"""CAPTCHA detection and handling for LinkedIn automation."""
import asyncio
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class CaptchaDetector:
    """Detects CAPTCHA challenges and waits for manual resolution."""

    CAPTCHA_SELECTORS = [
        'iframe[src*="recaptcha"]',
        'iframe[src*="captcha"]',
        'iframe[title*="recaptcha"]',
        'iframe[title*="CAPTCHA"]',
        '.captcha-container',
        '#captcha-container',
        'div[class*="captcha"]',
        'div[id*="captcha"]',
    ]

    LINKEDIN_AUTH_SELECTORS = [
        'input[name="captcha"]',
        '.authwall-verification-code',
        'input[aria-label*="verification"]',
        'input[placeholder*="verification"]',
        '[data-test-id="authwall-verification"]',
    ]

    def is_captcha_page(self, page: Page) -> bool:
        """Quick check based on URL patterns."""
        url = page.url.lower()
        if "checkpoint" in url or "challenges" in url:
            return True
        if "authwall" in url and "login" not in url:
            return True
        return False

    async def is_captcha_present(self, page: Page) -> bool:
        """Check if a CAPTCHA or verification challenge is visible."""
        # URL-based check
        if self.is_captcha_page(page):
            return True

        # Selector-based check
        for selector in self.CAPTCHA_SELECTORS + self.LINKEDIN_AUTH_SELECTORS:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    return True
            except Exception:
                continue

        # Check for security challenge text
        try:
            body_text = await page.inner_text("body")
            captcha_keywords = [
                "verify you are human",
                "security verification",
                "unusual activity",
                "automated access",
                "please verify",
                "security check",
                "confirm your identity",
            ]
            for keyword in captcha_keywords:
                if keyword in body_text.lower():
                    return True
        except Exception:
            pass

        return False

    async def wait_for_captcha_solved(self, page: Page, timeout: int = 120) -> bool:
        """Wait for the user to solve the CAPTCHA. Returns True if solved."""
        logger.info("Waiting for CAPTCHA to be solved (timeout=%ds)", timeout)
        elapsed = 0
        check_interval = 3
        while elapsed < timeout:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            if not await self.is_captcha_present(page):
                # Extra wait after CAPTCHA disappears to let page settle
                await asyncio.sleep(3)
                # Verify we're back to normal LinkedIn
                url = page.url.lower()
                if "checkpoint" not in url and "challenges" not in url:
                    return True
        return False


captcha_detector = CaptchaDetector()
