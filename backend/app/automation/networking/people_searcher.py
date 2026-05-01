"""LinkedIn People search — find recruiters and engineers at a company."""
import logging
import urllib.parse
from typing import Optional
from playwright.async_api import Page
from app.automation.human_simulator import HumanSimulator

logger = logging.getLogger(__name__)


class PeopleSearcher:
    """Searches LinkedIn People for specific roles at a company."""

    BASE_URL = "https://www.linkedin.com/search/results/people/"

    def __init__(self):
        self.human = HumanSimulator()

    async def search_people(
        self,
        page: Page,
        company: str,
        role_keywords: list[str],
        max_results: int = 5,
    ) -> list[dict]:
        """Search for people matching role keywords at a company.

        Returns list of dicts: profile_url, person_name, title, person_type
        """
        keywords = f"{company} {' '.join(role_keywords)}"
        params = {"keywords": keywords}
        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}?{query_string}"

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await self.human.random_delay(3, 6)

        # Wait for results
        try:
            await page.wait_for_selector(
                ".reusable-search__result-container, "
                ".search-results-container .reusable-search__result, "
                ".entity-result",
                timeout=10000,
            )
        except Exception:
            logger.debug("No people search results found for: %s", keywords)

        await self.human.scroll_naturally(page, "down", 400)
        await self.human.short_delay()

        results = []
        cards = await page.query_selector_all(
            ".reusable-search__result-container, "
            ".search-results-container .reusable-search__result, "
            ".entity-result"
        )
        for card in cards[: max_results * 2]:
            person = await self._extract_person(card)
            if person:
                results.append(person)

        # Deduplicate by profile_url
        seen = set()
        unique = []
        for p in results:
            if p["profile_url"] not in seen:
                seen.add(p["profile_url"])
                unique.append(p)

        return unique[:max_results]

    async def _extract_person(self, card) -> Optional[dict]:
        """Extract person info from a search result card."""
        try:
            # Name + profile URL
            name_el = await card.query_selector(
                ".entity-result__title-text a, .app-aware-link"
            )
            if not name_el:
                return None
            raw_name = (await name_el.inner_text()).strip()
            # LinkedIn shows "Name\n3rd+" — take first line
            name = raw_name.split("\n")[0].strip()
            profile_url = await name_el.get_attribute("href")
            if profile_url:
                profile_url = profile_url.split("?")[0]  # Strip query params
            if not profile_url or not name:
                return None

            # Title / headline
            title_el = await card.query_selector(
                ".entity-result__primary-subtitle, .entity-result__summary"
            )
            title = (
                (await title_el.inner_text()).strip() if title_el else ""
            )

            person_type = self._classify_person(title)

            return {
                "profile_url": profile_url,
                "person_name": name,
                "title": title,
                "person_type": person_type,
            }
        except Exception as e:
            logger.debug("Failed to extract person from card: %s", e)
            return None

    def _classify_person(self, title: str) -> str:
        """Classify a person by their title text using word-boundary matching."""
        import re
        t = title.lower()
        # Multi-word phrases first (more specific). Order matters: hiring_manager
        # is checked before recruiter so "Head of Engineering" classifies as a
        # hiring manager, not as a recruiter.
        phrase_patterns = [
            ("recruiter", [r"talent acquisition", r"head of (?:talent|recruit)", r"people ops", r"human resources"]),
            ("hiring_manager", [r"head of"]),
        ]
        for ptype, patterns in phrase_patterns:
            if any(re.search(pat, t) for pat in patterns):
                return ptype

        # Single-word matching using word boundaries
        recruiter_words = [
            "recruiter", "talent", "hiring",
        ]
        hiring_manager_words = [
            "director", "vp", "cto", "manager", "principal", "lead",
        ]
        engineer_words = [
            "engineer", "developer", "sde", "software", "programmer", "architect",
        ]

        words = set(re.findall(r"[a-z]+", t))
        if any(w in words for w in recruiter_words):
            return "recruiter"
        if any(w in words for w in hiring_manager_words):
            return "hiring_manager"
        if any(w in words for w in engineer_words):
            return "engineer"
        # Fallback: substring for "hr" (too short for word matching)
        if re.search(r"\bhr\b", t):
            return "recruiter"
        return "other"
