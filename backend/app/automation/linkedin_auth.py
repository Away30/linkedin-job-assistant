"""LinkedIn authentication via manual login with session persistence."""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from app.automation.browser_manager import browser_manager
from app.automation.human_simulator import HumanSimulator

logger = logging.getLogger(__name__)


class LinkedInAuth:
    """Handles LinkedIn authentication - manual login only for safety."""

    LINKEDIN_URL = "https://www.linkedin.com"
    FEED_URL = "https://www.linkedin.com/feed/"
    LOGIN_URL = "https://www.linkedin.com/login"

    def __init__(self):
        self.human = HumanSimulator()

    async def is_logged_in(self, page: Optional[Page] = None) -> bool:
        """Check if user is currently logged into LinkedIn."""
        page = page or await browser_manager.get_page()
        try:
            current_url = page.url
            if "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                return True

            await page.goto(self.FEED_URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)

            # Check if redirected to login page
            if "login" in page.url or "authwall" in page.url:
                return False

            # Look for feed indicators
            feed_indicator = await page.query_selector('[data-test-id="feed-sort-dropdown"]') or \
                             await page.query_selector('.feed-shared-update-v2') or \
                             await page.query_selector('.global-nav__me-photo')
            return feed_indicator is not None
        except Exception as e:
            logger.warning("is_logged_in check failed: %s", e)
            return False

    async def wait_for_manual_login(self, timeout_seconds: int = 300) -> bool:
        """Navigate to login page and wait for user to log in manually."""
        page = await browser_manager.get_page()

        if await self.is_logged_in(page):
            return True

        await page.goto(self.LOGIN_URL, wait_until="domcontentloaded")

        # Wait for user to complete login — check URL/DOM without navigating
        elapsed = 0
        while elapsed < timeout_seconds:
            await asyncio.sleep(3)
            elapsed += 3
            # Check current page URL directly (no navigation)
            current_url = page.url
            if "linkedin.com/feed" in current_url or "linkedin.com/in/" in current_url:
                await self.human.random_delay(2, 5)
                return True
            # Check for feed indicators (user may have navigated manually)
            feed_indicator = await page.query_selector('.global-nav__me-photo')
            if feed_indicator:
                await self.human.random_delay(2, 5)
                return True

        return False

    async def ensure_logged_in(self) -> bool:
        """Ensure user is logged in, prompt for manual login if needed."""
        page = await browser_manager.get_page()
        if await self.is_logged_in(page):
            return True
        return await self.wait_for_manual_login()


linkedin_auth = LinkedInAuth()
