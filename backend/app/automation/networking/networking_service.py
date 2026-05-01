"""Networking orchestrator — post-apply recruiter connection flow."""
import logging
from datetime import datetime
from typing import Optional
from playwright.async_api import Page
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Connection
from app.safety.rate_limiter import rate_limiter
from app.automation.human_simulator import HumanSimulator
from app.automation.networking.people_searcher import PeopleSearcher
from app.automation.networking.connection_sender import ConnectionSender
from app.automation.networking.message_templates import (
    MessageTemplateEngine,
    MessageContext,
)

logger = logging.getLogger(__name__)


class NetworkingService:
    """Orchestrates post-apply networking: search -> personalize -> connect."""

    def __init__(self):
        self.searcher = PeopleSearcher()
        self.sender = ConnectionSender()
        self.templates = MessageTemplateEngine(settings.CONNECTION_MESSAGES_PATH)
        self.human = HumanSimulator()

    async def network_after_apply(
        self,
        page: Page,
        company: str,
        role_title: str,
        job_id: int,
        db: Session,
        max_connects: int = 3,
        person_types: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search for and connect with recruiters after applying.

        Returns list of connection results.
        """
        person_types = person_types or ["recruiter"]
        role_keywords = person_types + ["hiring"]

        # Check connection rate limit
        can, msg = rate_limiter.can_connect(db)
        if not can:
            logger.info("Connection rate limit reached: %s", msg)
            return []

        remaining = rate_limiter.get_daily_connect_remaining(db)
        max_connects = min(max_connects, remaining)

        # Search for people
        logger.info(
            "Searching for %s at %s (max %d)",
            ", ".join(person_types),
            company,
            max_connects,
        )
        people = await self.searcher.search_people(
            page, company, role_keywords, max_results=max_connects * 2
        )

        # Filter by desired person types
        filtered = [
            p for p in people if p["person_type"] in person_types
        ][:max_connects]

        if not filtered:
            logger.info("No matching people found for %s", company)
            return []

        results = []
        for person in filtered:
            # Skip if already connected / pending
            existing = (
                db.query(Connection)
                .filter(Connection.profile_url == person["profile_url"])
                .first()
            )
            if existing:
                logger.debug(
                    "Skipping existing connection: %s", person["person_name"]
                )
                continue

            # Generate personalized message
            message = self.templates.generate(
                MessageContext(
                    person_name=person["person_name"],
                    company_name=company,
                    role_title=role_title,
                    person_title=person["title"],
                    person_type=person["person_type"],
                )
            )

            # Send connection request
            logger.info(
                "Connecting with %s (%s) at %s",
                person["person_name"],
                person["person_type"],
                company,
            )
            send_result = await self.sender.send_connection(
                page, person["profile_url"], message
            )

            # Record in database
            connection = Connection(
                job_id=job_id,
                profile_url=person["profile_url"],
                person_name=person["person_name"],
                title=person["title"],
                company=company,
                person_type=person["person_type"],
                message=message,
                status="sent" if send_result["success"] else "failed",
                error_message=send_result.get("error"),
                sent_at=datetime.utcnow() if send_result["success"] else None,
            )
            db.add(connection)
            db.commit()

            results.append(
                {
                    "person": person["person_name"],
                    "type": person["person_type"],
                    "success": send_result["success"],
                }
            )

            if send_result["success"]:
                logger.info("Connected with %s", person["person_name"])
            else:
                logger.warning(
                    "Failed to connect with %s: %s",
                    person["person_name"],
                    send_result.get("error"),
                )

            # Human-like delay between connections
            await self.human.random_delay()
            await self.human.maybe_long_break(probability=0.1)

        return results


# Singleton
networking_service = NetworkingService()
