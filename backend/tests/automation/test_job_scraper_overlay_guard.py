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
from app.automation.easy_apply import EasyApplyHandler


class FakeOverlay:
    def __init__(self, visible: bool):
        self.visible = visible

    async def is_visible(self):
        return self.visible


class FakeModal:
    def __init__(self, visible: bool):
        self.visible = visible

    async def is_visible(self):
        return self.visible


class FakePage:
    def __init__(
        self,
        overlay_states: list[bool],
        easy_apply_modal_open: bool = False,
        raise_overlay_probe_error: bool = False,
    ):
        self.overlays = [FakeOverlay(state) for state in overlay_states]
        self.easy_apply_modal_open = easy_apply_modal_open
        self.raise_overlay_probe_error = raise_overlay_probe_error
        self.clicked = False

    async def query_selector(self, selector: str):
        if selector == '[data-test-modal-container], .artdeco-modal-overlay':
            return self.overlays[0] if self.overlays else None
        if selector == '[data-job-id="123"]':
            return self
        return None

    async def query_selector_all(self, selector: str):
        if selector == '[data-test-modal-container], .artdeco-modal-overlay':
            if self.raise_overlay_probe_error:
                raise RuntimeError("dom churn")
            return self.overlays
        if selector == ".jobs-unified-top-card__job-insight span":
            return []
        if "jobs-easy-apply-modal" in selector:
            return [FakeModal(True)] if self.easy_apply_modal_open else []
        return []

    async def wait_for_selector(self, selector: str, timeout: int):
        return None

    async def click(self):
        self.clicked = True


@pytest.mark.asyncio
async def test_scrape_job_detail_stops_when_overlay_is_still_open():
    scraper = JobScraper()
    page = FakePage(overlay_states=[True])

    result = await scraper.scrape_job_detail(page, "123")

    assert result is None
    assert page.clicked is False


@pytest.mark.asyncio
async def test_scrape_job_detail_clicks_when_overlay_is_clear(monkeypatch):
    scraper = JobScraper()
    page = FakePage(overlay_states=[])

    async def fake_click(card):
        await card.click()

    async def no_delay(*args, **kwargs):
        return None

    async def fake_get_text(_page, selector):
        if "job-title" in selector:
            return "Backend Engineer"
        return ""

    monkeypatch.setattr(scraper.human, "human_click", fake_click)
    monkeypatch.setattr(scraper.human, "random_delay", no_delay)
    monkeypatch.setattr(scraper, "_get_text", fake_get_text)

    result = await scraper.scrape_job_detail(page, "123")

    assert result is not None
    assert result.linkedin_job_id == "123"
    assert page.clicked is True


@pytest.mark.asyncio
async def test_has_blocking_overlay_checks_all_overlay_matches():
    handler = EasyApplyHandler()
    page = FakePage(overlay_states=[False, True], easy_apply_modal_open=False)

    result = await handler.has_blocking_overlay(page)

    assert result is True


@pytest.mark.asyncio
async def test_scrape_job_detail_stops_when_modal_is_open_without_overlay():
    scraper = JobScraper()
    page = FakePage(overlay_states=[], easy_apply_modal_open=True)

    result = await scraper.scrape_job_detail(page, "123")

    assert result is None
    assert page.clicked is False


@pytest.mark.asyncio
async def test_has_blocking_overlay_fails_closed_on_overlay_probe_error():
    handler = EasyApplyHandler()
    page = FakePage(overlay_states=[], raise_overlay_probe_error=True)

    result = await handler.has_blocking_overlay(page)

    assert result is True
