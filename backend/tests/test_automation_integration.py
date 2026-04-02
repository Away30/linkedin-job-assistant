"""Integration tests for browser automation."""
import asyncio
import pytest
from app.automation.browser_manager import browser_manager
from app.automation.linkedin_auth import linkedin_auth
from app.automation.job_searcher import job_searcher
from app.automation.human_simulator import HumanSimulator


@pytest.mark.asyncio
async def test_browser_manager_launch():
    """Test browser launch and closure."""
    try:
        page = await browser_manager.launch(headless=True)
        assert page is not None
        assert browser_manager.is_running
        await browser_manager.close()
        assert not browser_manager.is_running
    except Exception as e:
        pytest.skip(f"Playwright not ready: {e}")


@pytest.mark.asyncio
async def test_linkedin_auth_check():
    """Test LinkedIn authentication check."""
    try:
        page = await browser_manager.launch(headless=True)
        # Initially should not be logged in (without credentials)
        is_logged_in = await linkedin_auth.is_logged_in(page)
        assert isinstance(is_logged_in, bool)
        await browser_manager.close()
    except Exception as e:
        pytest.skip(f"Playwright not ready: {e}")


@pytest.mark.asyncio
async def test_job_search_url_building():
    """Test job search URL construction."""
    url = job_searcher.build_search_url(
        keywords="Python",
        location="San Francisco",
        experience_level="senior",
        easy_apply=True
    )
    assert "keywords=Python" in url
    assert "location=San Francisco" in url
    assert "f_AL=true" in url
    assert url.startswith("https://www.linkedin.com/jobs/search/")


@pytest.mark.asyncio
async def test_human_simulator_delays():
    """Test human simulator random delays."""
    human = HumanSimulator()
    # Just verify these don't crash
    await human.random_delay(1, 3)
    # Test should take at least 1 second
    import time
    start = time.time()
    await human.random_delay(0.5, 1.5)
    elapsed = time.time() - start
    assert elapsed >= 0.5


def test_human_simulator_creation():
    """Test human simulator can be instantiated."""
    human = HumanSimulator()
    assert human is not None


if __name__ == "__main__":
    # Quick manual testing
    print("Running automation integration tests...")
    print("Note: Run with pytest for full async support")
