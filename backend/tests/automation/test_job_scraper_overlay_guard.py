import sys
import types

import pytest

# Provide a lightweight Playwright stub for unit tests.
if "playwright.async_api" not in sys.modules:
    playwright_module = types.ModuleType("playwright")
    async_api_module = types.ModuleType("playwright.async_api")
    async_api_module.Page = object
    async_api_module.Locator = object
    playwright_module.async_api = async_api_module
    sys.modules["playwright"] = playwright_module
    sys.modules["playwright.async_api"] = async_api_module

from app.automation.job_scraper import JobScraper


class FakePage:
    def __init__(self, overlay_visible: bool):
        self.overlay_visible = overlay_visible
        self.clicked = False

    async def query_selector(self, selector: str):
        if selector == '[data-test-modal-container], .artdeco-modal-overlay':
            return object() if self.overlay_visible else None
        if selector == '[data-job-id="123"]':
            return self
        return None

    async def click(self):
        self.clicked = True


@pytest.mark.asyncio
async def test_scrape_job_detail_stops_when_overlay_is_still_open():
    scraper = JobScraper()
    page = FakePage(overlay_visible=True)

    result = await scraper.scrape_job_detail(page, "123")

    assert result is None
    assert page.clicked is False


@pytest.mark.asyncio
async def test_guard_overlay_returns_true_when_page_is_clear():
    scraper = JobScraper()
    page = FakePage(overlay_visible=False)

    result = await scraper._guard_overlay(page)

    assert result is True
