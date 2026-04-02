"""Job matching engine — scores jobs by relevance to user's target skills."""
import logging
import re
from typing import Optional
from app.schemas.schemas import JobCreate

logger = logging.getLogger(__name__)


class JobMatcher:
    """Scores jobs based on keyword matching against user's target skills."""

    def __init__(self):
        # Default stop words — don't count these as skill matches
        self._stop_words = {
            "and", "or", "the", "a", "an", "in", "of", "with", "for", "to",
            "is", "are", "be", "been", "being", "have", "has", "had", "do",
            "does", "did", "will", "would", "could", "should", "may", "might",
            "must", "shall", "can", "need", "not", "no", "yes", "all", "any",
            "each", "every", "both", "few", "more", "most", "other", "some",
            "such", "than", "too", "very", "just", "also", "now", "here",
            "there", "when", "where", "how", "what", "which", "who", "whom",
            "this", "that", "these", "those", "but", "if", "as", "at", "by",
            "from", "on", "into", "through", "during", "before", "after",
            "above", "below", "up", "down", "out", "off", "over", "under",
            "then", "once", "well", "using", "including", "etc", "ie", "eg",
        }

    def score_job(
        self,
        job: JobCreate,
        required_skills: list[str],
        preferred_skills: Optional[list[str]] = None,
    ) -> int:
        """Score a job from 0-100 based on skill match.

        Scoring:
        - Title match: 40% weight
        - Description match (required): 40% weight
        - Description match (preferred): 20% weight
        """
        if not required_skills:
            return 50  # neutral score if no skills configured

        title_score = self._match_score(job.title or "", required_skills)
        desc_required = self._match_score(job.description or "", required_skills)
        desc_preferred = (
            self._match_score(job.description or "", preferred_skills)
            if preferred_skills
            else 0.5
        )

        raw = (
            title_score * 0.40
            + desc_required * 0.40
            + desc_preferred * 0.20
        )
        score = min(100, max(0, int(raw * 100)))

        logger.debug(
            "Job '%s' scored %d (title=%.0f%% desc_req=%.0f%% desc_pref=%.0f%%)",
            job.title, score,
            title_score * 100, desc_required * 100, desc_preferred * 100,
        )
        return score

    def _match_score(self, text: str, skills: list[str]) -> float:
        """Return 0.0-1.0 representing fraction of skills found in text."""
        if not skills or not text:
            return 0.0

        text_lower = text.lower()
        matched = 0
        total = len(skills)

        for skill in skills:
            skill_lower = skill.strip().lower()
            if not skill_lower:
                continue

            # Multi-word skill: exact phrase match
            if " " in skill_lower or "." in skill_lower or "-" in skill_lower:
                if skill_lower in text_lower:
                    matched += 1
                continue

            # Single-word skill: word boundary match
            pattern = r'\b' + re.escape(skill_lower) + r'\b'
            if re.search(pattern, text_lower):
                matched += 1

        return matched / total if total > 0 else 0.0

    def filter_by_score(
        self, jobs: list[JobCreate], required_skills: list[str],
        min_score: int = 40, preferred_skills: Optional[list[str]] = None,
    ) -> list[tuple[JobCreate, int]]:
        """Score and filter jobs, returning (job, score) tuples above min_score."""
        scored = []
        for job in jobs:
            score = self.score_job(job, required_skills, preferred_skills)
            if score >= min_score:
                scored.append((job, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


# Singleton
job_matcher = JobMatcher()
