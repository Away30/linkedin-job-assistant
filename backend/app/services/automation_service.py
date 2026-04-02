"""Main automation orchestrator - coordinates search, scrape, and apply."""
import asyncio
import logging
import random
import uuid
import time
from datetime import datetime, date, timezone
from typing import Optional
from app.config import settings
from app.schemas.schemas import AutomationStartRequest, AutomationStatus
from app.db.session import SessionLocal
from app.models import Job, Application, Resume, SearchFilter, OperationLog, Blacklist
from app.safety.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class AutomationService:
    """Orchestrates the auto-apply session lifecycle."""

    def __init__(self):
        self.is_running = False
        self.session_id: Optional[str] = None
        self._status = AutomationStatus()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._start_time: Optional[float] = None
        self._lock = asyncio.Lock()

    def get_status(self) -> AutomationStatus:
        if self._start_time and self.is_running:
            self._status.elapsed_seconds = int(time.time() - self._start_time)
        return self._status

    async def start(self, request: AutomationStartRequest):
        """Start an auto-apply session in a background task."""
        if self.is_running:
            return

        self.is_running = True
        self.session_id = str(uuid.uuid4())[:8]
        self._stop_event.clear()
        self._start_time = time.time()

        self._status = AutomationStatus(
            is_running=True,
            session_id=self.session_id,
            status_message="Starting automation...",
        )

        self._task = asyncio.create_task(self._run_session(request))

    async def stop(self):
        """Gracefully stop the current session."""
        if self.is_running:
            self._stop_event.set()
            self.is_running = False
            self._status.is_running = False
            self._status.status_message = "Stopped by user"
            if self._task and not self._task.done():
                self._task.cancel()

    def _log_operation(self, db, operation_type: str, details: str, status: str):
        """Record an operation log to the database."""
        try:
            log = OperationLog(
                operation_type=operation_type,
                details=details,
                status=status,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.warning("Failed to log operation: %s", e)
            db.rollback()

    async def _run_session(self, request: AutomationStartRequest):
        """Main automation loop with its own DB session."""
        db = SessionLocal()
        try:
            self._status.daily_applies_remaining = rate_limiter.get_daily_remaining(db)
            await self._execute(db, request)
        except Exception as e:
            logger.exception("Session error")
            self._status.status_message = f"Error: {str(e)}"
            self._log_operation(db, "session", f"Session error: {e}", "error")
        finally:
            self.is_running = False
            self._status.is_running = False
            if not self._status.status_message:
                self._status.status_message = "Session completed"
            db.close()

    async def _execute(self, db, request: AutomationStartRequest):
        from app.automation.browser_manager import browser_manager
        from app.automation.linkedin_auth import linkedin_auth
        from app.automation.job_searcher import job_searcher
        from app.automation.job_scraper import job_scraper
        from app.automation.easy_apply import easy_apply_handler
        from app.automation.human_simulator import HumanSimulator
        from app.automation.captcha_detector import captcha_detector

        human = HumanSimulator()

        try:
            # Step 1: Launch browser
            self._status.status_message = "Launching browser..."
            logger.info("Launching browser")
            page = await browser_manager.launch(headless=False)

            # Step 2: Check login
            self._status.status_message = "Checking LinkedIn login..."
            logger.info("Checking login status")
            if not await linkedin_auth.ensure_logged_in():
                self._status.status_message = "Login required - please log in manually"
                self._log_operation(db, "auth", "Login timeout", "failed")
                return

            self._log_operation(db, "auth", "Login verified", "success")

            # Step 3: Get search filter or use request params
            search_filter = None
            if request.filter_id:
                search_filter = db.query(SearchFilter).filter(SearchFilter.id == request.filter_id).first()

            keywords = request.keywords or (search_filter.keywords if search_filter else "")
            location = request.location or (search_filter.location if search_filter else "")

            # Step 4: Get resume
            resume_path = None
            if request.resume_id:
                resume = db.query(Resume).filter(Resume.id == request.resume_id).first()
                if resume:
                    resume_path = resume.file_path
            else:
                default_resume = db.query(Resume).filter(Resume.is_default == True).first()
                if default_resume:
                    resume_path = default_resume.file_path

            # Step 5: Search for jobs
            self._status.status_message = f"Searching for '{keywords}' jobs..."
            logger.info("Searching jobs: keywords=%s location=%s", keywords, location)
            all_job_ids = await job_searcher.search(
                page, keywords=keywords, location=location,
                search_filter=search_filter,
            )

            # Pagination - load more pages if available
            pages_loaded = 1
            max_pages = 5
            while pages_loaded < max_pages and await job_searcher.has_more_pages(page):
                if self._stop_event.is_set():
                    break
                self._status.status_message = f"Loading page {pages_loaded + 1}..."
                logger.info("Loading page %d", pages_loaded + 1)
                next_ids = await job_searcher.next_page(page)
                if next_ids:
                    seen = set(all_job_ids)
                    new_ids = [jid for jid in next_ids if jid not in seen]
                    all_job_ids.extend(new_ids)
                    pages_loaded += 1
                else:
                    break

            self._status.jobs_found = len(all_job_ids)
            self._log_operation(db, "search", f"Found {len(all_job_ids)} jobs across {pages_loaded} pages for '{keywords}'", "success")

            if not all_job_ids:
                self._status.status_message = "No jobs found matching criteria"
                return

            # Step 6: Iterate and apply
            applied_count = 0
            max_applies = min(request.max_applies, rate_limiter.get_daily_remaining(db))
            last_apply_time = time.time()

            for idx, job_id in enumerate(all_job_ids):
                if self._stop_event.is_set():
                    self._status.status_message = "Stopped by user"
                    break
                if applied_count >= max_applies:
                    self._status.status_message = f"Reached limit of {max_applies} applications"
                    break

                # Check session time limit
                elapsed_min = (time.time() - self._start_time) / 60
                if elapsed_min > settings.MAX_SESSION_MINUTES:
                    self._status.status_message = "Session time limit reached"
                    break

                # CAPTCHA check
                if await captcha_detector.is_captcha_present(page):
                    self._status.status_message = "CAPTCHA detected! Please solve it in the browser window..."
                    self._log_operation(db, "captcha", "CAPTCHA detected, waiting for user", "warning")
                    if await captcha_detector.wait_for_captcha_solved(page, timeout=120):
                        self._log_operation(db, "captcha", "CAPTCHA solved", "success")
                        self._status.status_message = "CAPTCHA solved, continuing..."
                    else:
                        self._log_operation(db, "captcha", "CAPTCHA not solved, stopping", "failed")
                        self._status.status_message = "CAPTCHA not solved, session stopped"
                        break

                # Break interval check
                if applied_count > 0 and settings.BREAK_INTERVAL_MINUTES_MIN > 0:
                    minutes_since_last = (time.time() - last_apply_time) / 60
                    break_threshold = random.uniform(
                        settings.BREAK_INTERVAL_MINUTES_MIN,
                        settings.BREAK_INTERVAL_MINUTES_MAX,
                    )
                    if minutes_since_last >= break_threshold:
                        break_duration = random.uniform(
                            settings.BREAK_DURATION_MINUTES_MIN,
                            settings.BREAK_DURATION_MINUTES_MAX,
                        )
                        logger.info("Taking a %.1f minute break", break_duration)
                        self._status.status_message = f"Taking a {int(break_duration)} min break..."
                        self._log_operation(db, "break", f"Taking {break_duration:.1f} min break", "success")
                        break_seconds = int(break_duration * 60)
                        for _ in range(break_seconds):
                            if self._stop_event.is_set():
                                break
                            await asyncio.sleep(1)
                        last_apply_time = time.time()

                # Rate limit check
                can_apply, msg = rate_limiter.can_apply(db)
                if not can_apply:
                    self._status.status_message = msg
                    self._log_operation(db, "rate_limit", msg, "warning")
                    break
                self._status.daily_applies_remaining = rate_limiter.get_daily_remaining(db)

                # Scrape job details
                job_num = idx + 1
                self._status.status_message = f"Reviewing job {job_num}/{len(all_job_ids)}..."
                logger.info("Reviewing job %s", job_id)
                job_data = await job_scraper.scrape_job_detail(page, job_id)

                if not job_data:
                    self._status.jobs_skipped += 1
                    continue

                # Save job to DB
                existing_job = db.query(Job).filter(Job.linkedin_job_id == job_data.linkedin_job_id).first()
                if existing_job:
                    db_job = existing_job
                else:
                    db_job = Job(**job_data.model_dump())
                    db.add(db_job)
                    db.commit()
                    db.refresh(db_job)

                # Check if already applied
                existing_app = db.query(Application).filter(
                    Application.job_id == db_job.id
                ).first()
                if existing_app:
                    self._status.jobs_skipped += 1
                    logger.info("Skipping already applied: %s", job_data.title)
                    continue

                # Check blacklist
                if job_data.company:
                    blacklisted = db.query(Blacklist).filter(
                        Blacklist.company_name.ilike(job_data.company)
                    ).first()
                    if blacklisted:
                        self._status.jobs_skipped += 1
                        logger.info("Skipping blacklisted company: %s", job_data.company)
                        continue

                # Check Easy Apply
                if not job_data.is_easy_apply:
                    self._status.jobs_skipped += 1
                    logger.info("Skipping non-Easy Apply: %s", job_data.title)
                    continue

                # Score job against required skills
                match_score = 0
                if search_filter and search_filter.required_skills:
                    from app.automation.job_matcher import job_matcher
                    req_skills = [s.strip() for s in search_filter.required_skills.split(",") if s.strip()]
                    pref_skills = [s.strip() for s in (search_filter.preferred_skills or "").split(",") if s.strip()]
                    min_score = search_filter.min_match_score or 40
                    match_score = job_matcher.score_job(job_data, req_skills, pref_skills or None)

                    # Update DB record with score
                    db_job.match_score = match_score
                    db.commit()

                    if match_score < min_score:
                        self._status.jobs_skipped += 1
                        logger.info("Skipping low match (%d%%): %s", match_score, job_data.title)
                        continue

                    logger.info("Job match score: %d%% for %s", match_score, job_data.title)

                self._status.current_job = f"{job_data.title} at {job_data.company} ({match_score}%)"
                self._status.status_message = f"Applying to {job_data.title}..."
                logger.info("Applying to: %s at %s", job_data.title, job_data.company)

                # Apply
                result = await easy_apply_handler.apply(page, resume_path=resume_path, dry_run=request.dry_run)

                # Record application
                app = Application(
                    job_id=db_job.id,
                    resume_id=request.resume_id,
                    status="applied" if result["success"] else "failed",
                    apply_method="easy_apply",
                    error_message="; ".join(result["errors"]) if result["errors"] else None,
                    applied_at=datetime.now(timezone.utc) if result["success"] else None,
                )
                db.add(app)
                db.commit()

                if result["success"]:
                    applied_count += 1
                    last_apply_time = time.time()
                    self._status.jobs_applied += 1
                    self._log_operation(db, "apply", f"Applied to {job_data.title} at {job_data.company}", "success")
                    logger.info("Successfully applied to %s", job_data.title)
                else:
                    self._status.jobs_failed += 1
                    self._log_operation(db, "apply", f"Failed: {job_data.title} - {result['errors']}", "failed")
                    logger.warning("Failed to apply to %s: %s", job_data.title, result["errors"])

                self._status.daily_applies_remaining = rate_limiter.get_daily_remaining(db)

                # Human-like delay between applications
                await human.random_delay()
                await human.maybe_long_break(probability=0.1)

            summary = f"Completed. Applied to {applied_count} of {len(all_job_ids)} jobs."
            self._status.status_message = summary
            self._status.current_job = None
            self._log_operation(db, "session", summary, "success")
            logger.info(summary)
        finally:
            try:
                await browser_manager.close()
            except Exception:
                pass


# Singleton
automation_service = AutomationService()
