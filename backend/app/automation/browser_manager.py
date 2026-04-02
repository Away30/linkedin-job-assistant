"""Playwright browser lifecycle management with stealth."""
import asyncio
import logging
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from app.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser with persistent context and stealth measures."""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self._context is not None

    @property
    def page(self) -> Optional[Page]:
        return self._page

    async def launch(self, headless: bool = False) -> Page:
        """Launch browser with persistent profile for session reuse."""
        if self.is_running:
            return self._page

        profile_dir = str(settings.BROWSER_PROFILE_DIR)
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            viewport={"width": 1366, "height": 768},
            user_agent=settings.BROWSER_USER_AGENT,
            locale="en-US",
            timezone_id="America/New_York",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
        )

        # Apply stealth scripts
        await self._apply_stealth(self._context)

        # Use existing page or create new one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        self._is_running = True
        return self._page

    async def _apply_stealth(self, context: BrowserContext):
        """Apply anti-detection measures."""
        await context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            // Chrome runtime
            window.chrome = { runtime: {} };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)

    async def get_page(self) -> Page:
        """Get current page or launch browser."""
        if not self.is_running:
            return await self.launch()
        return self._page

    async def new_page(self) -> Page:
        """Create a new page/tab."""
        if not self.is_running:
            await self.launch()
        page = await self._context.new_page()
        await self._apply_stealth_to_page(page)
        return page

    async def _apply_stealth_to_page(self, page: Page):
        """Additional per-page stealth."""
        pass  # init_script covers it via context

    async def close(self):
        """Close browser gracefully."""
        self._is_running = False
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.debug("Error closing browser context: %s", e)
                pass
            self._context = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.debug("Error stopping playwright: %s", e)
                pass
            self._playwright = None
        self._page = None


# Singleton instance
browser_manager = BrowserManager()
