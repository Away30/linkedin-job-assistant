"""Extract job data from LinkedIn job detail pages."""
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page
from app.automation.human_simulator import HumanSimulator
from app.schemas.schemas import JobCreate

logger = logging.getLogger(__name__)


class JobScraper:
    """Scrapes job details from LinkedIn job listings."""

    def __init__(self):
        self.human = HumanSimulator()

    async def scrape_job_detail(self, page: Page, linkedin_job_id: str) -> Optional[JobCreate]:
        """Click on a job card and extract full details."""
        try:
            # Click the job card to load details
            card = await page.query_selector(f'[data-job-id="{linkedin_job_id}"]')
            if not card:
                card = await page.query_selector(f'[data-occludable-job-id="{linkedin_job_id}"]')

            if not card:
                logger.warning("Job card not found for ID: %s", linkedin_job_id)
                return None

            if card:
                await self.human.human_click(card)
                await self.human.random_delay(2, 4)

            # Wait for detail panel
            try:
                await page.wait_for_selector('.jobs-unified-top-card', timeout=8000)
            except Exception:
                pass

            # Extract data
            title = await self._get_text(page, '.jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title h1')
            company = await self._get_text(page, '.jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name')
            location = await self._get_text(page, '.jobs-unified-top-card__bullet, .job-details-jobs-unified-top-card__bullet')

            # Description
            description = await self._get_text(page, '.jobs-description__content, .jobs-box__html-content')

            # Easy Apply check
            easy_apply_btn = await page.query_selector('.jobs-apply-button--top-card button, .jobs-apply-button')
            easy_apply_text = await self._get_text(page, '.jobs-apply-button--top-card button, .jobs-apply-button') if easy_apply_btn else ""
            is_easy_apply = "easy apply" in easy_apply_text.lower() if easy_apply_text else False

            # Job URL
            job_url = f"https://www.linkedin.com/jobs/view/{linkedin_job_id}/"

            # Additional details
            details_items = await page.query_selector_all('.jobs-unified-top-card__job-insight span')
            experience_level = ""
            job_type = ""
            for item in details_items:
                text = (await item.inner_text()).strip().lower()
                if any(level in text for level in ["entry", "associate", "mid-senior", "director", "executive", "internship"]):
                    experience_level = text
                elif any(jt in text for jt in ["full-time", "part-time", "contract", "temporary", "internship"]):
                    job_type = text

            # Posted date
            posted_date = await self._get_text(page, '.jobs-unified-top-card__posted-date, time')

            if not title:
                return None

            return JobCreate(
                linkedin_job_id=linkedin_job_id,
                title=title.strip(),
                company=company.strip() if company else None,
                location=location.strip() if location else None,
                description=description[:5000] if description else None,
                job_url=job_url,
                is_easy_apply=is_easy_apply,
                experience_level=experience_level or None,
                job_type=job_type or None,
                posted_date=posted_date.strip() if posted_date else None,
            )
        except Exception as e:
            logger.warning("scrape_job_detail failed for job %s: %s", linkedin_job_id, e)
            return None

    async def _get_text(self, page: Page, selector: str) -> str:
        """Safely get text content from selector."""
        try:
            el = await page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception as e:
            logger.debug("_get_text failed for selector '%s': %s", selector, e)
        return ""

    async def scrape_jobs_from_list(self, page: Page, job_ids: list[str]) -> list[JobCreate]:
        """Scrape details for a list of job IDs from search results."""
        jobs = []
        for job_id in job_ids:
            job = await self.scrape_job_detail(page, job_id)
            if job:
                jobs.append(job)
            await self.human.random_delay(1, 3)
        return jobs


job_scraper = JobScraper()
