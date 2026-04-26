import pytest

from app.automation.job_searcher import JobSearcher



def test_build_next_page_url_replaces_existing_start_param():
    searcher = JobSearcher()
    url = "https://www.linkedin.com/jobs/search/?keywords=Python&start=25&f_AL=true"

    new_url = searcher._build_next_page_url(url, 50)

    assert "start=50" in new_url
    assert "start=25" not in new_url
    assert "keywords=Python" in new_url
    assert "f_AL=true" in new_url



def test_build_next_page_url_appends_start_when_missing():
    searcher = JobSearcher()
    url = "https://www.linkedin.com/jobs/search/?keywords=Python&f_AL=true"

    new_url = searcher._build_next_page_url(url, 25)

    assert "start=25" in new_url
    assert "keywords=Python" in new_url
    assert "f_AL=true" in new_url


class FakePage:
    def __init__(self):
        self.url = "https://www.linkedin.com/jobs/search/?keywords=Python&f_AL=true"
        self.goto_calls = []
        self.query_calls = []

    async def goto(self, url, wait_until=None, timeout=None):
        self.url = url
        self.goto_calls.append(url)

    async def query_selector(self, selector):
        self.query_calls.append(selector)
        return None


@pytest.mark.asyncio
async def test_next_page_prefers_url_navigation(monkeypatch):
    searcher = JobSearcher()
    page = FakePage()

    async def fake_get_job_card_ids(_page):
        return ["123", "456"]

    async def fake_random_delay(*args, **kwargs):
        return None

    async def fail_if_clicked(*args, **kwargs):
        raise AssertionError("pagination button path should not run when URL pagination succeeds")

    monkeypatch.setattr(searcher, "_get_job_card_ids", fake_get_job_card_ids)
    monkeypatch.setattr(searcher.human, "random_delay", fake_random_delay)
    monkeypatch.setattr(searcher.human, "human_click", fail_if_clicked)
    searcher.current_page_num = 0

    result = await searcher.next_page(page)

    assert result == ["123", "456"]
    assert page.goto_calls
    assert "start=25" in page.goto_calls[0]
    assert not page.query_calls
