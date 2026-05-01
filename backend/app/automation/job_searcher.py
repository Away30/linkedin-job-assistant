"""LinkedIn job search navigation and pagination."""
import asyncio
import logging
import urllib.parse
from typing import Optional
from playwright.async_api import Page
from app.automation.browser_manager import browser_manager
from app.automation.human_simulator import HumanSimulator
from app.schemas.schemas import SearchFilterRead

logger = logging.getLogger(__name__)


class JobSearcher:
    """Navigates LinkedIn job search with filters and pagination."""

    BASE_SEARCH_URL = "https://www.linkedin.com/jobs/search/"

    def __init__(self):
        self.human = HumanSimulator()
        self.current_page_num = 0

    def build_search_url(self, keywords: str = "", location: str = "",
                         job_type: str = "", experience_level: str = "",
                         remote_filter: str = "", date_posted: str = "",
                         easy_apply: bool = True, start: int = 0) -> str:
        """Build LinkedIn job search URL with filters."""
        params = {}
        if keywords:
            params["keywords"] = keywords
        if location:
            params["location"] = location
        if easy_apply:
            params["f_AL"] = "true"

        # Job type mapping
        job_type_map = {
            "full-time": "F", "part-time": "P", "contract": "C",
            "temporary": "T", "internship": "I", "volunteer": "V",
        }
        if job_type and job_type.lower() in job_type_map:
            params["f_JT"] = job_type_map[job_type.lower()]

        # Experience level mapping
        exp_map = {
            "internship": "1", "entry": "2", "associate": "3",
            "mid-senior": "4", "director": "5", "executive": "6",
        }
        if experience_level and experience_level.lower() in exp_map:
            params["f_E"] = exp_map[experience_level.lower()]

        # Remote filter
        remote_map = {"on-site": "1", "remote": "2", "hybrid": "3"}
        if remote_filter and remote_filter.lower() in remote_map:
            params["f_WT"] = remote_map[remote_filter.lower()]

        # Date posted
        date_map = {"past-24h": "r86400", "past-week": "r604800", "past-month": "r2592000"}
        if date_posted and date_posted.lower() in date_map:
            params["f_TPR"] = date_map[date_posted.lower()]

        if start > 0:
            params["start"] = str(start)

        # Sort by date (newest first) so user applies to freshest jobs
        params["sortBy"] = "DD"

        query_string = urllib.parse.urlencode(params)
        return f"{self.BASE_SEARCH_URL}?{query_string}"

    async def search(self, page: Page, keywords: str = "", location: str = "",
                     easy_apply: bool = True, search_filter: Optional[SearchFilterRead] = None,
                     **kwargs) -> list[str]:
        """Execute search and return list of job card elements."""
        if search_filter:
            url = self.build_search_url(
                keywords=search_filter.keywords or keywords,
                location=search_filter.location or location,
                job_type=search_filter.job_type or "",
                experience_level=search_filter.experience_level or "",
                remote_filter=search_filter.remote_filter or "",
                date_posted=search_filter.date_posted or "",
                easy_apply=search_filter.easy_apply_only if search_filter.easy_apply_only is not None else easy_apply,
            )
        else:
            url = self.build_search_url(keywords=keywords, location=location,
                                        easy_apply=easy_apply, **kwargs)

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await self.human.random_delay(3, 6)

        # Wait for job cards to load
        try:
            await page.wait_for_selector('.jobs-search-results-list', timeout=10000)
        except Exception as e:
            logger.debug("search: wait_for_selector timeout: %s", e)

        await self.human.scroll_naturally(page, "down", 500)
        await self.human.short_delay()

        self.current_page_num = 0
        return await self._get_job_card_ids(page)

    async def _get_job_card_ids(self, page: Page) -> list[str]:
        """Extract job IDs from current search results page."""
        job_ids = []
        cards = await page.query_selector_all('[data-job-id]')
        for card in cards:
            job_id = await card.get_attribute('data-job-id')
            if job_id:
                job_ids.append(job_id.strip())

        # Fallback: try alternate selectors
        if not job_ids:
            cards = await page.query_selector_all('.jobs-search-results__list-item')
            for card in cards:
                job_id = await card.get_attribute('data-occludable-job-id')
                if job_id:
                    job_ids.append(job_id.strip())

        return list(dict.fromkeys(job_ids))  # deduplicate preserving order

    def _build_next_page_url(self, current_url: str, start: int) -> str:
        """Return URL with deterministic next-page `start` query parameter."""
        parsed = urllib.parse.urlsplit(current_url)
        query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)

        next_query_params = []
        start_updated = False
        for key, value in query_params:
            if key == "start":
                if not start_updated:
                    next_query_params.append(("start", str(start)))
                    start_updated = True
                continue
            next_query_params.append((key, value))

        if not start_updated:
            next_query_params.append(("start", str(start)))

        next_query = urllib.parse.urlencode(next_query_params, doseq=True)
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, next_query, parsed.fragment)
        )

    async def next_page(self, page: Page) -> list[str]:
        """Navigate to next page of results."""
        self.current_page_num += 1
        start = self.current_page_num * 25

        # Prefer URL-based pagination to avoid overlay click interception.
        try:
            new_url = self._build_next_page_url(page.url, start)
            await page.goto(new_url, wait_until="domcontentloaded", timeout=30000)
            await self.human.random_delay(3, 6)
            ids = await self._get_job_card_ids(page)
            if ids:
                return ids
        except Exception as e:
            logger.warning("URL pagination failed: %s", e)

        # Fallback: click pagination controls.
        next_btn = None
        page_btn = await page.query_selector(f'[aria-label="Page {self.current_page_num + 1}"]')
        if page_btn:
            next_btn = page_btn
        else:
            next_btn = await page.query_selector('.artdeco-pagination__button--next:not([disabled])')

        if next_btn:
            try:
                await self.human.human_click(next_btn)
                await self.human.random_delay(3, 6)
                ids = await self._get_job_card_ids(page)
                if ids:
                    return ids
            except Exception as e:
                logger.warning("Pagination button click failed: %s", e)

        # Last retry: URL-based navigation.
        new_url = self._build_next_page_url(page.url, start)
        await page.goto(new_url, wait_until="domcontentloaded", timeout=30000)
        await self.human.random_delay(3, 6)
        return await self._get_job_card_ids(page)

    async def has_more_pages(self, page: Page) -> bool:
        """Check if there are more search result pages."""
        pagination = await page.query_selector('.artdeco-pagination')
        if not pagination:
            return False
        next_btn = await page.query_selector('.artdeco-pagination__button--next:not([disabled])')
        return next_btn is not None


job_searcher = JobSearcher()
