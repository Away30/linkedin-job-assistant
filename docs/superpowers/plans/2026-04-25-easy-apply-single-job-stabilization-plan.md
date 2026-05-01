# Easy Apply Single-Job Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize one LinkedIn Easy Apply transaction so the fixed sample can reliably reach submit-ready dry-run state before controlled real submission.

**Architecture:** Add an explicit Easy Apply session boundary around the active modal, move field resolution to modal-scoped helpers, and make step validation plus cleanup explicit transaction phases. Persist structured apply results so failures are diagnosable and do not silently degrade into generic "could not proceed" errors.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Playwright async API, pytest, pytest-asyncio

---

## File Structure

### New files

- `backend/app/automation/easy_apply_session.py` - owns modal-scoped transaction state, footer action detection, structured result payloads, and cleanup bookkeeping
- `backend/tests/automation/test_easy_apply_session.py` - unit tests for session state, footer action mapping, and failure/result payloads
- `backend/tests/automation/test_form_filler_modal_scope.py` - regression tests proving field detection stays inside the active modal and reports unresolved fields
- `backend/tests/automation/test_easy_apply_handler.py` - orchestration tests for dry-run interception, validation blocking, and submit flow behavior
- `backend/tests/automation/test_job_scraper_overlay_guard.py` - regression tests for overlay cleanup gating before the next job click
- `backend/tests/automation/test_easy_apply_result_persistence.py` - tests for storing structured apply payloads in application records and logs

### Modified files

- `backend/app/automation/easy_apply.py` - refactor into orchestrator that delegates modal state and step logic to `EasyApplySession`
- `backend/app/automation/form_filler.py` - make field enumeration container-scoped and return structured resolution output
- `backend/app/automation/job_scraper.py` - add overlay guard before clicking another job card
- `backend/app/services/automation_service.py` - persist structured apply payloads and improved logging
- `backend/tests/automation/conftest.py` - reusable fake modal/locator helpers for async unit tests

### Test execution targets

- `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_session.py -v`
- `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_form_filler_modal_scope.py -v`
- `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_handler.py -v`
- `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_job_scraper_overlay_guard.py -v`
- `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_result_persistence.py -v`

### Task 1: Add modal transaction primitives

**Files:**
- Create: `backend/app/automation/easy_apply_session.py`
- Create: `backend/tests/automation/test_easy_apply_session.py`
- Modify: `backend/tests/automation/conftest.py`
- Test: `backend/tests/automation/test_easy_apply_session.py`

- [ ] **Step 1: Write the failing session tests**

```python
# backend/tests/automation/test_easy_apply_session.py
import pytest

from app.automation.easy_apply_session import (
    EasyApplyResult,
    EasyApplySession,
    EasyApplyStepState,
)


class FakeButton:
    def __init__(self, text: str, visible: bool = True):
        self._text = text
        self._visible = visible

    async def is_visible(self):
        return self._visible

    async def inner_text(self):
        return self._text


class FakeModal:
    def __init__(self, buttons):
        self.buttons = buttons

    async def query_selector_all(self, selector: str):
        assert selector == "footer button"
        return self.buttons


@pytest.mark.asyncio
async def test_detect_primary_action_prefers_submit_over_next():
    session = EasyApplySession(modal=FakeModal([
        FakeButton("Next"),
        FakeButton("Submit application"),
    ]))

    action = await session.detect_primary_action()

    assert action == "submit"


@pytest.mark.asyncio
async def test_step_state_tracks_unresolved_and_validation_errors():
    session = EasyApplySession(modal=FakeModal([]))
    session.step_state = EasyApplyStepState(
        step_index=2,
        resolved_fields=["Email"],
        unresolved_fields=["Work authorization"],
        validation_errors=["Select an option"],
    )

    assert session.step_state.unresolved_fields == ["Work authorization"]
    assert session.step_state.validation_errors == ["Select an option"]


def test_result_payload_contains_failure_type_and_cleanup_flag():
    result = EasyApplyResult(
        success=False,
        failure_type="field_unresolved",
        final_action="blocked",
        cleanup_success=False,
        resolved_fields=["Email"],
        unresolved_fields=["Work authorization"],
        validation_errors=["Select an option"],
    )

    payload = result.model_dump()

    assert payload["failure_type"] == "field_unresolved"
    assert payload["cleanup_success"] is False
    assert payload["unresolved_fields"] == ["Work authorization"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.automation.easy_apply_session'`

- [ ] **Step 3: Write the minimal session implementation**

```python
# backend/app/automation/easy_apply_session.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


FooterAction = Literal["next", "review", "submit", "unknown"]
FailureType = Literal[
    "modal_not_found",
    "field_unresolved",
    "field_validation_failed",
    "advance_button_not_found",
    "overlay_not_cleared",
    "submit_intercepted_dry_run",
    "submit_failed",
]


class EasyApplyStepState(BaseModel):
    step_index: int = 1
    resolved_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class EasyApplyResult(BaseModel):
    success: bool = False
    failure_type: str | None = None
    final_action: str = "unknown"
    cleanup_success: bool = False
    steps_completed: int = 0
    resolved_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class EasyApplySession:
    def __init__(self, modal):
        self.modal = modal
        self.step_state = EasyApplyStepState()

    async def detect_primary_action(self) -> FooterAction:
        buttons = await self.modal.query_selector_all("footer button")
        labels = []
        for button in buttons:
            if await button.is_visible():
                labels.append((await button.inner_text()).strip().lower())
        if any("submit" in label for label in labels):
            return "submit"
        if any("review" in label for label in labels):
            return "review"
        if any(label in {"next", "continue"} or "next" in label for label in labels):
            return "next"
        return "unknown"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_session.py -v`
Expected: PASS with `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/automation/easy_apply_session.py backend/tests/automation/test_easy_apply_session.py backend/tests/automation/conftest.py
git commit -m "test: add easy apply session primitives"
```

### Task 2: Make form filling modal-scoped and structured

**Files:**
- Modify: `backend/app/automation/form_filler.py`
- Create: `backend/tests/automation/test_form_filler_modal_scope.py`
- Test: `backend/tests/automation/test_form_filler_modal_scope.py`

- [ ] **Step 1: Write the failing modal-scope tests**

```python
# backend/tests/automation/test_form_filler_modal_scope.py
import pytest

from app.automation.form_filler import FormFiller


class FakeElement:
    def __init__(self, label: str, field_type: str = "text", enabled: bool = True):
        self.label = label
        self.field_type = field_type
        self.enabled = enabled
        self.value = None

    async def get_attribute(self, name: str):
        mapping = {
            "aria-label": self.label,
            "type": self.field_type,
            "id": self.label.lower().replace(" ", "-"),
        }
        return mapping.get(name)

    async def is_enabled(self):
        return self.enabled

    async def click(self):
        return None

    async def fill(self, value: str):
        self.value = value


class FakeContainer:
    def __init__(self, text_inputs=None, selects=None, fieldsets=None, checkboxes=None):
        self.text_inputs = text_inputs or []
        self.selects = selects or []
        self.fieldsets = fieldsets or []
        self.checkboxes = checkboxes or []

    async def query_selector_all(self, selector: str):
        if selector.startswith("input[type=\"text\"]"):
            return self.text_inputs
        if selector == "select":
            return self.selects
        if selector == "fieldset":
            return self.fieldsets
        if selector == 'input[type="checkbox"]':
            return self.checkboxes
        return []


@pytest.mark.asyncio
async def test_detect_and_fill_fields_uses_only_modal_container():
    filler = FormFiller()
    filler.form_answers = {"email": "away@example.com"}
    modal = FakeContainer(text_inputs=[FakeElement("Email")])

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == ["Email"]
    assert result["unresolved_fields"] == []


@pytest.mark.asyncio
async def test_unresolved_required_field_is_reported():
    filler = FormFiller()
    filler.form_answers = {"email": "away@example.com"}
    modal = FakeContainer(text_inputs=[FakeElement("Work authorization")])

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == []
    assert result["unresolved_fields"] == ["Work authorization"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_form_filler_modal_scope.py -v`
Expected: FAIL because `detect_and_fill_fields()` currently expects a full `Page` object and returns a flat dict instead of structured resolution output

- [ ] **Step 3: Write the minimal modal-scoped implementation**

```python
# backend/app/automation/form_filler.py
class FormFiller:
    # keep existing __init__, _load_answers, reload_answers, and _find_answer

    async def detect_and_fill_fields(self, container) -> dict[str, list[str]]:
        result = {
            "resolved_fields": [],
            "unresolved_fields": [],
            "validation_errors": [],
        }

        text_inputs = await container.query_selector_all(
            'input[type="text"], input[type="email"], input[type="tel"], input[type="number"], input[type="url"], textarea'
        )
        for inp in text_inputs:
            label = await self._get_field_label(container, inp)
            if not label:
                continue
            if hasattr(inp, "is_enabled") and not await inp.is_enabled():
                continue
            filled = await self.fill_text_field(container, inp, label)
            if filled:
                result["resolved_fields"].append(label)
            else:
                result["unresolved_fields"].append(label)

        return result

    async def fill_text_field(self, page_or_container, locator, label: str) -> bool:
        answer = self._find_answer(label)
        if not answer:
            return False
        input_type = await locator.get_attribute("type") or ""
        if input_type == "number":
            try:
                if float(answer) <= 0:
                    return False
            except ValueError:
                return False
        await locator.click()
        await locator.fill("")
        if hasattr(locator, "press_sequentially"):
            await self.human.type_like_human(locator, answer)
        else:
            await locator.fill(answer)
        return True

    async def _get_field_label(self, container, element) -> str:
        aria = await element.get_attribute("aria-label")
        return aria.strip() if aria else ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_form_filler_modal_scope.py -v`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/automation/form_filler.py backend/tests/automation/test_form_filler_modal_scope.py
git commit -m "test: scope form filling to active easy apply modal"
```

### Task 3: Refactor Easy Apply orchestration around session validation

**Files:**
- Modify: `backend/app/automation/easy_apply.py`
- Create: `backend/tests/automation/test_easy_apply_handler.py`
- Test: `backend/tests/automation/test_easy_apply_handler.py`

- [ ] **Step 1: Write the failing handler tests**

```python
# backend/tests/automation/test_easy_apply_handler.py
import pytest

from app.automation.easy_apply import EasyApplyHandler
from app.automation.easy_apply_session import EasyApplyResult


class StubSession:
    def __init__(self, action: str, unresolved=None, validation_errors=None):
        self.action = action
        self.step_state = type("State", (), {
            "resolved_fields": ["Email"],
            "unresolved_fields": unresolved or [],
            "validation_errors": validation_errors or [],
        })()

    async def detect_primary_action(self):
        return self.action


@pytest.mark.asyncio
async def test_apply_blocks_when_unresolved_fields_exist(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="next", unresolved=["Work authorization"])

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)

    result = await handler.apply(page=object(), dry_run=True)

    assert result["success"] is False
    assert result["failure_type"] == "field_unresolved"


@pytest.mark.asyncio
async def test_apply_intercepts_submit_in_dry_run(monkeypatch):
    handler = EasyApplyHandler()
    session = StubSession(action="submit")

    async def fake_click_easy_apply_button(page):
        return True

    async def fake_is_modal_open(page):
        return object()

    async def fake_fill_and_validate_step(page, session, resume_path):
        return EasyApplyResult(
            success=False,
            final_action="submit",
            cleanup_success=False,
            resolved_fields=["Email"],
            unresolved_fields=[],
            validation_errors=[],
        )

    monkeypatch.setattr(handler, "_create_session", lambda page: session)
    monkeypatch.setattr(handler, "click_easy_apply_button", fake_click_easy_apply_button)
    monkeypatch.setattr(handler, "is_modal_open", fake_is_modal_open)
    monkeypatch.setattr(handler, "_fill_and_validate_step", fake_fill_and_validate_step)

    result = await handler.apply(page=object(), dry_run=True)

    assert result["success"] is True
    assert result["failure_type"] == "submit_intercepted_dry_run"
    assert result["final_action"] == "submit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_handler.py -v`
Expected: FAIL because `apply()` still returns only `success`, `steps_completed`, and `errors`

- [ ] **Step 3: Write the minimal handler orchestration**

```python
# backend/app/automation/easy_apply.py
from app.automation.easy_apply_session import EasyApplyResult, EasyApplySession


class EasyApplyHandler:
    # keep __init__, click_easy_apply_button, and modal-opening helpers

    def _create_session(self, modal):
        return EasyApplySession(modal=modal)

    async def _fill_and_validate_step(self, page, session: EasyApplySession, resume_path: str | None):
        if resume_path:
            await self._handle_resume_upload(session.modal, resume_path)
        field_result = await form_filler.detect_and_fill_fields(session.modal)
        session.step_state.resolved_fields = field_result["resolved_fields"]
        session.step_state.unresolved_fields = field_result["unresolved_fields"]
        session.step_state.validation_errors = field_result["validation_errors"]
        action = await session.detect_primary_action()
        return EasyApplyResult(
            success=False,
            final_action=action,
            resolved_fields=field_result["resolved_fields"],
            unresolved_fields=field_result["unresolved_fields"],
            validation_errors=field_result["validation_errors"],
        )

    async def apply(self, page, resume_path: str | None = None, max_steps: int = 10, dry_run: bool = False) -> dict:
        if not await self.click_easy_apply_button(page):
            return EasyApplyResult(success=False, failure_type="modal_not_found").model_dump()
        await self.human.random_delay(2, 4)
        modal = await self.is_modal_open(page)
        if not modal:
            return EasyApplyResult(success=False, failure_type="modal_not_found").model_dump()

        session = self._create_session(modal)
        result = await self._fill_and_validate_step(page, session, resume_path)
        if result.unresolved_fields:
            result.failure_type = "field_unresolved"
            return result.model_dump()
        if result.validation_errors:
            result.failure_type = "field_validation_failed"
            return result.model_dump()
        if result.final_action == "submit" and dry_run:
            result.success = True
            result.failure_type = "submit_intercepted_dry_run"
            return result.model_dump()
        if result.final_action == "unknown":
            result.failure_type = "advance_button_not_found"
            return result.model_dump()
        return result.model_dump()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_handler.py -v`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/automation/easy_apply.py backend/tests/automation/test_easy_apply_handler.py
git commit -m "test: add structured easy apply orchestration"
```

### Task 4: Enforce cleanup before the next job click

**Files:**
- Modify: `backend/app/automation/easy_apply.py`
- Modify: `backend/app/automation/job_scraper.py`
- Create: `backend/tests/automation/test_job_scraper_overlay_guard.py`
- Test: `backend/tests/automation/test_job_scraper_overlay_guard.py`

- [ ] **Step 1: Write the failing overlay cleanup tests**

```python
# backend/tests/automation/test_job_scraper_overlay_guard.py
import pytest

from app.automation.job_scraper import JobScraper


class FakePage:
    def __init__(self, overlay_visible: bool):
        self.overlay_visible = overlay_visible
        self.clicked = False

    async def query_selector(self, selector: str):
        if selector == '[data-test-modal-container], .artdeco-modal-overlay':
            return object() if self.overlay_visible else None
        if selector == '[data-job-id="123"]':
            return self
        return None

    async def click(self):
        self.clicked = True


@pytest.mark.asyncio
async def test_scrape_job_detail_stops_when_overlay_is_still_open():
    scraper = JobScraper()
    page = FakePage(overlay_visible=True)

    result = await scraper.scrape_job_detail(page, "123")

    assert result is None


@pytest.mark.asyncio
async def test_guard_overlay_returns_true_when_page_is_clear():
    scraper = JobScraper()
    page = FakePage(overlay_visible=False)

    result = await scraper._guard_overlay(page)

    assert result is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_job_scraper_overlay_guard.py -v`
Expected: FAIL because `JobScraper` has no overlay guard and still clicks immediately

- [ ] **Step 3: Write the minimal cleanup guard implementation**

```python
# backend/app/automation/job_scraper.py
class JobScraper:
    # keep __init__ and existing extraction helpers

    async def _guard_overlay(self, page: Page) -> bool:
        overlay = await page.query_selector('[data-test-modal-container], .artdeco-modal-overlay')
        if overlay:
            logger.warning("Overlay still active before scraping next job")
            return False
        return True

    async def scrape_job_detail(self, page: Page, linkedin_job_id: str):
        if not await self._guard_overlay(page):
            return None
        card = await page.query_selector(f'[data-job-id="{linkedin_job_id}"]')
        if not card:
            card = await page.query_selector(f'[data-occludable-job-id="{linkedin_job_id}"]')
        if not card:
            logger.warning("Job card not found for ID: %s", linkedin_job_id)
            return None
        await self.human.human_click(card)
        await self.human.random_delay(2, 4)
        return await self._extract_job_data(page, linkedin_job_id)

    async def _extract_job_data(self, page: Page, linkedin_job_id: str):
        title = await self._get_text(page, '.jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title h1')
        if not title:
            return None
        return JobCreate(
            linkedin_job_id=linkedin_job_id,
            title=title.strip(),
            company=(await self._get_text(page, '.jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name') or None),
            location=(await self._get_text(page, '.jobs-unified-top-card__bullet, .job-details-jobs-unified-top-card__bullet') or None),
            description=(await self._get_text(page, '.jobs-description__content, .jobs-box__html-content') or None),
            job_url=f'https://www.linkedin.com/jobs/view/{linkedin_job_id}/',
            is_easy_apply=True,
        )
```

```python
# backend/app/automation/easy_apply.py
class EasyApplyHandler:
    async def cleanup_modal(self, page, session: EasyApplySession) -> bool:
        dismiss_selectors = [
            'button[aria-label="Dismiss"]',
            'button:has-text("Done")',
            '.artdeco-modal__dismiss',
        ]
        for selector in dismiss_selectors:
            btn = await session.modal.query_selector(selector)
            if btn:
                await self.human.human_click(btn)
                await self.human.short_delay()
                return True
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_job_scraper_overlay_guard.py -v`
Expected: PASS with `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/automation/easy_apply.py backend/app/automation/job_scraper.py backend/tests/automation/test_job_scraper_overlay_guard.py
git commit -m "test: gate next job on easy apply overlay cleanup"
```

### Task 5: Persist structured apply outcomes in the automation service

**Files:**
- Modify: `backend/app/services/automation_service.py`
- Create: `backend/tests/automation/test_easy_apply_result_persistence.py`
- Test: `backend/tests/automation/test_easy_apply_result_persistence.py`

- [ ] **Step 1: Write the failing persistence tests**

```python
# backend/tests/automation/test_easy_apply_result_persistence.py
from app.models import Job
from app.services.automation_service import AutomationService


def test_build_application_record_persists_structured_form_answers(db_session):
    job = Job(linkedin_job_id="job-1", title="Sample Job", company="Sample Co")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    service = AutomationService()
    apply_result = {
        "success": False,
        "failure_type": "field_unresolved",
        "final_action": "blocked",
        "cleanup_success": False,
        "resolved_fields": ["Email"],
        "unresolved_fields": ["Work authorization"],
        "validation_errors": ["Select an option"],
    }

    record = service._build_application_record(
        job_id=job.id,
        resume_id=None,
        result=apply_result,
    )
    db_session.add(record)
    db_session.commit()

    stored = db_session.get(type(record), record.id)

    assert stored.form_answers["failure_type"] == "field_unresolved"
    assert stored.form_answers["unresolved_fields"] == ["Work authorization"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_result_persistence.py -v`
Expected: FAIL because the current service path does not persist structured apply payloads to `Application.form_answers`

- [ ] **Step 3: Write the minimal persistence changes**

```python
# backend/app/services/automation_service.py
def _build_application_record(self, job_id: int, resume_id: int | None, result: dict) -> Application:
    return Application(
        job_id=job_id,
        resume_id=resume_id,
        status="applied" if result["success"] else "failed",
        apply_method="easy_apply",
        form_answers={
            "final_action": result.get("final_action"),
            "failure_type": result.get("failure_type"),
            "cleanup_success": result.get("cleanup_success"),
            "resolved_fields": result.get("resolved_fields", []),
            "unresolved_fields": result.get("unresolved_fields", []),
            "validation_errors": result.get("validation_errors", []),
        },
        error_message="; ".join(result.get("validation_errors", []) or result.get("errors", [])) or result.get("failure_type"),
        applied_at=datetime.utcnow() if result["success"] else None,
    )
```

```python
# backend/app/services/automation_service.py
application = self._build_application_record(
    job_id=db_job.id,
    resume_id=request.resume_id,
    result=result,
)
db.add(application)

# keep the operation log call below
self._log_operation(
    db,
    "apply",
    f"Apply result job={job_data.title} action={result.get('final_action')} failure={result.get('failure_type')} unresolved={result.get('unresolved_fields', [])}",
    "success" if result["success"] else "failed",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_easy_apply_result_persistence.py -v`
Expected: PASS with `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/automation_service.py backend/tests/automation/test_easy_apply_result_persistence.py
git commit -m "test: persist structured easy apply outcomes"
```

### Task 6: Run the targeted regression suite and manual sample validation

**Files:**
- Modify: `backend/tests/automation/test_easy_apply_handler.py`
- Modify: `backend/tests/automation/test_job_scraper_overlay_guard.py`
- Test: `backend/tests/automation/test_easy_apply_session.py`
- Test: `backend/tests/automation/test_form_filler_modal_scope.py`
- Test: `backend/tests/automation/test_easy_apply_handler.py`
- Test: `backend/tests/automation/test_job_scraper_overlay_guard.py`
- Test: `backend/tests/automation/test_easy_apply_result_persistence.py`

- [ ] **Step 1: Run the focused backend regression suite**

Run:

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && \
pytest tests/automation/test_easy_apply_session.py \
       tests/automation/test_form_filler_modal_scope.py \
       tests/automation/test_easy_apply_handler.py \
       tests/automation/test_job_scraper_overlay_guard.py \
       tests/automation/test_easy_apply_result_persistence.py -v
```

Expected: PASS for all targeted Easy Apply stabilization tests

- [ ] **Step 2: Run the existing dry-run regression to catch schema regressions**

Run: `cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend && pytest tests/automation/test_dry_run.py -v`
Expected: PASS with `1 passed`

- [ ] **Step 3: Run manual dry-run validation against the primary sample**

Run:

```bash
cd /Users/away/Desktop/Linkedin投递/linkedin-job-assistant/backend
source venv/bin/activate
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8899
```

Then in the extension popup start automation with:

```json
{
  "filter_id": 1,
  "max_applies": 1,
  "dry_run": true,
  "enable_networking": false
}
```

Expected:

- the fixed Turing sample reaches submit-ready state
- logs show `failure_type=submit_intercepted_dry_run`
- the modal is closed cleanly after interception
- no `City, state, or zip code` background interaction appears in `backend/data/logs/automation.log`

- [ ] **Step 4: Run the simpler safety-regression sample**

Run the same dry-run flow against the exact simpler sample `BeaconFire Inc. / Java Software Engineer`.

Expected:

- still reaches submit-ready state
- no overlay remains active afterward
- no previously passing simple flow regresses

- [ ] **Step 5: Commit the verification updates and notes**

```bash
git add backend/tests/automation/test_easy_apply_handler.py backend/tests/automation/test_job_scraper_overlay_guard.py
git commit -m "test: verify easy apply stabilization regressions"
```
