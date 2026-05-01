"""Main automation orchestrator - coordinates search, scrape, and apply."""
import asyncio
import logging
import random
import uuid
import time
from datetime import datetime, date
from typing import Optional, Any
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
            status_message="正在启动自动投递...",
        )

        self._task = asyncio.create_task(self._run_session(request))

    async def stop(self):
        """Gracefully stop the current session."""
        if self.is_running:
            self._stop_event.set()
            self.is_running = False
            self._status.is_running = False
            self._status.status_message = "已手动停止"
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

    @staticmethod
    def _extract_structured_apply_outcome(result: dict[str, Any]) -> dict[str, Any]:
        """Keep diagnosable apply metadata in a stable structure for persistence."""
        return {
            "final_action": result.get("final_action") or "unknown",
            "failure_type": result.get("failure_type"),
            "cleanup_success": bool(result.get("cleanup_success", False)),
            "resolved_fields": list(result.get("resolved_fields") or []),
            "unresolved_fields": list(result.get("unresolved_fields") or []),
            "validation_errors": list(result.get("validation_errors") or []),
        }

    @staticmethod
    def _build_error_message(result: dict[str, Any], structured_outcome: dict[str, Any]) -> Optional[str]:
        """Prefer structured failure type + details over generic string blobs."""
        errors = [str(item) for item in (result.get("errors") or []) if item]
        details = "; ".join(errors)
        failure_type = structured_outcome.get("failure_type")
        if failure_type:
            return f"{failure_type}: {details}" if details else str(failure_type)
        if details:
            return details
        if not result.get("success"):
            return "apply_failed_without_details"
        return None

    def _build_application_record(self, job_id: int, resume_id: Optional[int], result: dict[str, Any]) -> Application:
        """Build a persisted application record from an apply result payload."""
        structured_outcome = self._extract_structured_apply_outcome(result)
        is_dry_run_intercept = self._is_dry_run_submit_intercept(result)
        status = "dry_run" if is_dry_run_intercept else ("applied" if result.get("success") else "failed")
        return Application(
            job_id=job_id,
            resume_id=resume_id,
            status=status,
            apply_method="easy_apply",
            form_answers=structured_outcome,
            error_message=self._build_error_message(result, structured_outcome),
            applied_at=datetime.utcnow() if result.get("success") and not is_dry_run_intercept else None,
        )

    @staticmethod
    def _is_dry_run_submit_intercept(result: dict[str, Any]) -> bool:
        """Return true when dry-run reached the final submit and intentionally skipped it."""
        return result.get("failure_type") == "submit_intercepted_dry_run"

    @staticmethod
    def _should_skip_existing_application(existing_app: Application, dry_run: bool) -> bool:
        """Skip successful applies, and skip prior dry-run hits only while dry-running."""
        if existing_app.status == "applied":
            return True
        if existing_app.status == "dry_run":
            return dry_run
        return False

    def _build_apply_operation_details(
        self,
        job_title: str,
        company: Optional[str],
        result: dict[str, Any],
        structured_outcome: Optional[dict[str, Any]] = None,
    ) -> str:
        """Build a single structured apply diagnostic string for logs and persisted operation trails."""
        outcome = structured_outcome or self._extract_structured_apply_outcome(result)
        prefix = "Dry-run reached submit" if self._is_dry_run_submit_intercept(result) else "Apply outcome"
        return (
            f"{prefix}: {job_title} at {company or 'Unknown company'} - "
            f"success={bool(result.get('success'))} "
            f"final_action={outcome['final_action']} "
            f"failure_type={outcome['failure_type']} "
            f"cleanup_success={outcome['cleanup_success']} "
            f"resolved_fields={outcome['resolved_fields']} "
            f"unresolved_fields={outcome['unresolved_fields']} "
            f"validation_errors={outcome['validation_errors']}"
        )

    def _build_apply_success_log_message(self, job_title: str, result: dict[str, Any]) -> str:
        """Use dry-run language when submit was reached but intentionally not sent."""
        if self._is_dry_run_submit_intercept(result):
            return f"Dry-run reached submit for {job_title}"
        return f"Successfully applied to {job_title}"

    @staticmethod
    def _build_session_summary(completed_count: int, total_jobs: int, dry_run: bool) -> str:
        """Summarize completed attempts without calling dry-runs real applications."""
        if dry_run:
            return f"Completed. Dry-run reached submit for {completed_count} of {total_jobs} jobs."
        return f"Completed. Applied to {completed_count} of {total_jobs} jobs."

    def _should_network_after_apply(
        self,
        request: AutomationStartRequest,
        result: dict[str, Any],
        company: Optional[str],
    ) -> bool:
        """Never send networking actions from dry-run; connect requests are real side effects."""
        if request.dry_run:
            return False
        if not request.enable_networking or not company:
            return False
        if result.get("success"):
            return True
        return result.get("final_action") == "submit" and self._is_dry_run_submit_intercept(result)

    async def _run_session(self, request: AutomationStartRequest):
        """Main automation loop with its own DB session."""
        db = SessionLocal()
        try:
            self._status.daily_applies_remaining = rate_limiter.get_daily_remaining(db)
            await self._execute(db, request)
        except Exception as e:
            logger.exception("Session error")
            self._status.status_message = f"错误：{str(e)}"
            self._log_operation(db, "session", f"Session error: {e}", "error")
        finally:
            self.is_running = False
            self._status.is_running = False
            if not self._status.status_message:
                self._status.status_message = "投递会话已完成"
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
            self._status.status_message = "正在启动浏览器..."
            logger.info("Launching browser")
            page = await browser_manager.launch(headless=False)

            # Step 2: Check login
            self._status.status_message = "正在检查 LinkedIn 登录状态..."
            logger.info("Checking login status")
            if not await linkedin_auth.ensure_logged_in():
                self._status.status_message = "请在浏览器中手动登录 LinkedIn..."
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
            self._status.status_message = f"正在搜索「{keywords}」职位..."
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
                self._status.status_message = f"正在加载第 {pages_loaded + 1} 页..."
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
                self._status.status_message = "未找到符合条件的职位"
                return

            # Step 6: Iterate and apply
            applied_count = 0
            max_applies = min(request.max_applies, rate_limiter.get_daily_remaining(db))
            last_apply_time = time.time()

            for idx, job_id in enumerate(all_job_ids):
                if self._stop_event.is_set():
                    self._status.status_message = "已手动停止"
                    break
                if applied_count >= max_applies:
                    self._status.status_message = f"已达到 {max_applies} 次投递上限"
                    break

                # Check session time limit
                elapsed_min = (time.time() - self._start_time) / 60
                if elapsed_min > settings.MAX_SESSION_MINUTES:
                    self._status.status_message = "已达到会话时间上限"
                    break

                # CAPTCHA check
                if await captcha_detector.is_captcha_present(page):
                    self._status.status_message = "检测到验证码！请在浏览器窗口中手动完成验证..."
                    self._log_operation(db, "captcha", "CAPTCHA detected, waiting for user", "warning")
                    if await captcha_detector.wait_for_captcha_solved(page, timeout=120):
                        self._log_operation(db, "captcha", "CAPTCHA solved", "success")
                        self._status.status_message = "验证码已通过，继续投递..."
                    else:
                        self._log_operation(db, "captcha", "CAPTCHA not solved, stopping", "failed")
                        self._status.status_message = "验证码未通过，会话已停止"
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
                        self._status.status_message = f"休息 {int(break_duration)} 分钟..."
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
                self._status.status_message = f"正在评估职位 {job_num}/{len(all_job_ids)}..."
                logger.info("Reviewing job %s", job_id)
                job_data = await job_scraper.scrape_job_detail(page, job_id)

                if not job_data:
                    self._status.jobs_skipped += 1
                    logger.info("SKIP #%d job_id=%s: scrape returned None", idx + 1, job_id)
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
                    if self._should_skip_existing_application(existing_app, dry_run=request.dry_run):
                        self._status.jobs_skipped += 1
                        logger.info("SKIP #%d '%s': already attempted (%s)", idx + 1, job_data.title, existing_app.status)
                        continue
                    logger.info("Retrying #%d '%s': previous application status=%s", idx + 1, job_data.title, existing_app.status)
                    db.delete(existing_app)
                    db.commit()

                # Check blacklist
                if job_data.company:
                    blacklisted = db.query(Blacklist).filter(
                        Blacklist.company_name.ilike(job_data.company)
                    ).first()
                    if blacklisted:
                        self._status.jobs_skipped += 1
                        logger.info("SKIP #%d '%s': company '%s' blacklisted", idx + 1, job_data.title, job_data.company)
                        continue

                # Check Easy Apply — skip check if search already filtered for Easy Apply
                search_used_easy_apply = (
                    (search_filter and search_filter.easy_apply_only)
                    or (not search_filter)  # default search uses easy_apply=True
                )
                if not search_used_easy_apply and not job_data.is_easy_apply:
                    self._status.jobs_skipped += 1
                    logger.info("SKIP #%d '%s': not Easy Apply", idx + 1, job_data.title)
                    continue

                # Score job — only filter when user explicitly configured required_skills
                from app.automation.job_matcher import job_matcher

                if search_filter and search_filter.required_skills:
                    req_skills = [s.strip() for s in search_filter.required_skills.split(",") if s.strip()]
                    pref_skills = [s.strip() for s in (search_filter.preferred_skills or "").split(",") if s.strip()]
                    min_score = search_filter.min_match_score or 40
                    match_score = job_matcher.score_job(job_data, req_skills, pref_skills or None)
                else:
                    # No required_skills configured → skip matching, accept all jobs
                    match_score = 100
                    min_score = 0

                # Update DB record with score
                db_job.match_score = match_score
                db.commit()

                if min_score > 0 and match_score < min_score:
                    self._status.jobs_skipped += 1
                    logger.info("SKIP #%d '%s': match_score=%d < min_score=%d", idx + 1, job_data.title, match_score, min_score)
                    continue

                logger.info("Job match score: %d%% for %s", match_score, job_data.title)

                self._status.current_job = f"{job_data.title} at {job_data.company} ({match_score}%)"
                self._status.status_message = f"正在投递：{job_data.title}..."
                logger.info("Applying to: %s at %s", job_data.title, job_data.company)

                # Apply
                result = await easy_apply_handler.apply(page, resume_path=resume_path, dry_run=request.dry_run)

                # Record application
                structured_outcome = self._extract_structured_apply_outcome(result)
                app = self._build_application_record(
                    job_id=db_job.id,
                    resume_id=request.resume_id,
                    result=result,
                )
                db.add(app)
                db.commit()
                apply_operation_details = self._build_apply_operation_details(
                    job_title=job_data.title,
                    company=job_data.company,
                    result=result,
                    structured_outcome=structured_outcome,
                )

                logger.info(apply_operation_details)

                if result["success"]:
                    applied_count += 1
                    last_apply_time = time.time()
                    if self._is_dry_run_submit_intercept(result):
                        self._status.jobs_dry_run += 1
                    else:
                        self._status.jobs_applied += 1
                    self._log_operation(db, "apply", apply_operation_details, "success")
                    logger.info(self._build_apply_success_log_message(job_data.title, result))

                    # Post-apply networking has real side effects, so dry-run never reaches it.
                    if self._should_network_after_apply(request, result, job_data.company):
                        await self._network_after_apply(page, db, job_data, db_job.id)
                elif self._should_network_after_apply(request, result, job_data.company):
                    await self._network_after_apply(page, db, job_data, db_job.id)
                else:
                    self._status.jobs_failed += 1
                    self._log_operation(db, "apply", apply_operation_details, "failed")
                    logger.warning("Failed to apply to %s: %s", job_data.title, result["errors"])

                self._status.daily_applies_remaining = rate_limiter.get_daily_remaining(db)

                # Human-like delay between applications
                await human.random_delay()
                await human.maybe_long_break(probability=0.1)

            summary = self._build_session_summary(applied_count, len(all_job_ids), request.dry_run)
            self._status.status_message = summary
            self._status.current_job = None
            self._log_operation(db, "session", summary, "success")
            logger.info(summary)
        finally:
            try:
                await browser_manager.close()
            except Exception:
                pass

    async def _network_after_apply(self, page, db, job_data, job_id: int):
        """Post-apply networking: find and connect with recruiters."""
        from app.automation.networking.networking_service import networking_service

        try:
            self._status.status_message = f"正在搜索 {job_data.company} 的 recruiter..."
            from app.config import settings as app_settings
            results = await networking_service.network_after_apply(
                page=page,
                company=job_data.company,
                role_title=job_data.title or "",
                job_id=job_id,
                db=db,
                max_connects=app_settings.NETWORKING_MAX_PER_SESSION,
                person_types=[t.strip() for t in app_settings.NETWORKING_PERSON_TYPES.split(",")],
            )
            sent_count = sum(1 for r in results if r.get("success"))
            self._status.connections_sent += sent_count
            if sent_count > 0:
                self._log_operation(
                    db, "connect",
                    f"Sent {sent_count} connection requests at {job_data.company}",
                    "success",
                )
                logger.info("Sent %d connections at %s", sent_count, job_data.company)
        except Exception as e:
            logger.warning("Networking failed for %s: %s", job_data.company, e)
            self._log_operation(db, "connect", f"Networking failed: {e}", "failed")
            # Don't fail the main session


# Singleton
automation_service = AutomationService()
