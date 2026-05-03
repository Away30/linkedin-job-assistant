"""End-to-end tests for the networking flow:
people_searcher → message_templates → connection_sender → networking_service.

All Playwright Page interactions are stubbed so the tests run without a browser.
"""
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Stub playwright so the test suite can import app modules without playwright
# installed in the CI environment.
# ---------------------------------------------------------------------------
_pw = types.ModuleType("playwright")
_pw_async = types.ModuleType("playwright.async_api")
_pw_async.async_playwright = object
_pw_async.Browser = object
_pw_async.BrowserContext = object
_pw_async.Page = object
_pw_async.Locator = object
_pw_async.Playwright = object
_pw.async_api = _pw_async
sys.modules.setdefault("playwright", _pw)
sys.modules.setdefault("playwright.async_api", _pw_async)

from app.automation.networking.people_searcher import PeopleSearcher
from app.automation.networking.message_templates import (
    MessageTemplateEngine,
    MessageContext,
)
from app.automation.networking.connection_sender import ConnectionSender
from app.automation.networking.networking_service import NetworkingService


# ---------------------------------------------------------------------------
# Helpers — lightweight Page stub
# ---------------------------------------------------------------------------

class _FakeElement:
    """Stub DOM element returned by query_selector / query_selector_all."""

    def __init__(self, text="", href="", visible=True, sub_elements=None):
        self._text = text
        self._href = href
        self._visible = visible
        self._sub_elements = sub_elements or {}

    async def inner_text(self):
        return self._text

    async def get_attribute(self, name):
        if name == "href":
            return self._href
        return None

    async def is_visible(self):
        return self._visible

    async def click(self):
        pass

    async def fill(self, value):
        pass

    async def query_selector(self, selector):
        return self._sub_elements.get(selector)


class FakePage:
    """Minimal async stub satisfying the Page protocol used by networking."""

    def __init__(self, cards=None, connect_button=None, add_note_button=None,
                 send_button=None, note_textarea=None):
        self._cards = cards or []
        self._connect_button = connect_button
        self._add_note_button = add_note_button
        self._send_button = send_button
        self._note_textarea = note_textarea
        self.goto_log = []

    async def goto(self, url, **kwargs):
        self.goto_log.append(url)

    async def wait_for_selector(self, selector, **kwargs):
        pass

    async def query_selector(self, selector):
        s = selector.lower()
        # ConnectionSender selectors
        if "connect" in s and self._connect_button is not None:
            return self._connect_button
        if "add a note" in s and self._add_note_button is not None:
            return self._add_note_button
        if "send" in s and self._send_button is not None:
            return self._send_button
        if ("custom-message" in s or "textarea" in s) and self._note_textarea is not None:
            return self._note_textarea
        return None

    async def query_selector_all(self, selector):
        return self._cards


class _FakeHuman:
    """Stub that records calls but does not sleep."""

    async def random_delay(self, *a, **kw):
        pass

    async def short_delay(self, *a, **kw):
        pass

    async def scroll_naturally(self, *a, **kw):
        pass

    async def maybe_long_break(self, *a, **kw):
        pass

    async def human_click(self, el):
        pass

    async def type_like_human(self, el, text, **kw):
        pass


# ---------------------------------------------------------------------------
# Tests — PeopleSearcher._classify_person
# ---------------------------------------------------------------------------

class TestClassifyPerson:
    def setup_method(self):
        self.searcher = PeopleSearcher()
        # Replace human simulator to avoid real delays in search_people tests
        self.searcher.human = _FakeHuman()

    def test_recruiter_by_word(self):
        assert self.searcher._classify_person("Senior Technical Recruiter") == "recruiter"

    def test_talent_acquisition_is_recruiter(self):
        assert self.searcher._classify_person("Talent Acquisition Specialist") == "recruiter"

    def test_head_of_talent_is_recruiter_not_hiring_manager(self):
        assert self.searcher._classify_person("Head of Talent Acquisition") == "recruiter"

    def test_head_of_engineering_is_hiring_manager(self):
        assert self.searcher._classify_person("Head of Engineering") == "hiring_manager"

    def test_vp_is_hiring_manager(self):
        assert self.searcher._classify_person("VP of Product") == "hiring_manager"

    def test_engineer(self):
        assert self.searcher._classify_person("Staff Software Engineer") == "engineer"

    def test_hr_is_recruiter(self):
        assert self.searcher._classify_person("HR Business Partner") == "recruiter"

    def test_unknown_is_other(self):
        assert self.searcher._classify_person("Co-Founder & CEO") == "other"


# ---------------------------------------------------------------------------
# Tests — PeopleSearcher.search_people (with stubbed page)
# ---------------------------------------------------------------------------

class TestSearchPeople:
    def setup_method(self):
        self.searcher = PeopleSearcher()
        self.searcher.human = _FakeHuman()

    @pytest.mark.asyncio
    async def test_extracts_persons_from_cards(self):
        name_sub = _FakeElement(
            text="Alice Johnson\n3rd+",
            href="https://linkedin.com/in/alice-johnson?param=1",
        )
        title_sub = _FakeElement(text="Senior Recruiter at Google")
        card = _FakeElement(
            text="Alice Johnson\n3rd+\nSenior Recruiter at Google",
            href="https://linkedin.com/in/alice-johnson?param=1",
            sub_elements={
                ".entity-result__title-text a, .app-aware-link": name_sub,
                ".entity-result__primary-subtitle, .entity-result__summary": title_sub,
            },
        )
        page = FakePage(cards=[card])
        results = await self.searcher.search_people(
            page, "Google", ["recruiter"], max_results=5,
        )
        assert len(results) >= 1
        first = results[0]
        assert first["person_name"] == "Alice Johnson"
        assert first["profile_url"] == "https://linkedin.com/in/alice-johnson"

    @pytest.mark.asyncio
    async def test_deduplication(self):
        cards = [
            _FakeElement(text="Bob Smith\n3rd+", href="https://linkedin.com/in/bob"),
            _FakeElement(text="Senior Engineer"),
            _FakeElement(text="Bob Smith\n3rd+", href="https://linkedin.com/in/bob"),
            _FakeElement(text="Senior Engineer"),
        ]
        page = FakePage(cards=cards)
        results = await self.searcher.search_people(
            page, "Meta", ["engineer"], max_results=10,
        )
        urls = [r["profile_url"] for r in results]
        assert len(urls) == len(set(urls))

    @pytest.mark.asyncio
    async def test_respects_max_results(self):
        cards = [
            _FakeElement(text=f"Person {i}\n3rd+", href=f"https://linkedin.com/in/p{i}")
            for i in range(10)
        ]
        # Each card needs a title element too — but since we only have one
        # element per card in _extract_person (both name_el and title_el come
        # from the same card via different selectors), we just provide enough.
        page = FakePage(cards=cards)
        results = await self.searcher.search_people(
            page, "Apple", ["engineer"], max_results=2,
        )
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Tests — MessageTemplateEngine
# ---------------------------------------------------------------------------

class TestMessageTemplateEngine:
    def test_recruiter_template(self):
        engine = MessageTemplateEngine()
        msg = engine.generate(MessageContext(
            person_name="Alice Johnson",
            company_name="Google",
            role_title="Software Engineer",
            person_title="Senior Recruiter",
            person_type="recruiter",
        ))
        assert "Alice" in msg
        assert "Google" in msg
        assert "Software Engineer" in msg

    def test_hiring_manager_template(self):
        engine = MessageTemplateEngine()
        msg = engine.generate(MessageContext(
            person_name="Bob",
            company_name="Meta",
            role_title="Product Manager",
            person_title="VP of Product",
            person_type="hiring_manager",
        ))
        assert "Bob" in msg
        assert "Meta" in msg

    def test_engineer_template(self):
        engine = MessageTemplateEngine()
        msg = engine.generate(MessageContext(
            person_name="Carol",
            company_name="Apple",
            role_title="iOS Developer",
            person_title="Staff Engineer",
            person_type="engineer",
        ))
        assert "Carol" in msg

    def test_fallback_default_template(self):
        engine = MessageTemplateEngine()
        msg = engine.generate(MessageContext(
            person_name="Dave",
            company_name="Netflix",
            role_title="Data Scientist",
            person_title="Co-Founder",
            person_type="other",
        ))
        assert "Dave" in msg
        assert "Netflix" in msg

    def test_max_length_300(self):
        engine = MessageTemplateEngine()
        msg = engine.generate(MessageContext(
            person_name="E" * 500,
            company_name="Company",
            role_title="Role",
            person_title="Title",
            person_type="recruiter",
        ))
        assert len(msg) <= 300

    def test_yaml_override(self, tmp_path):
        override = tmp_path / "messages.yaml"
        override.write_text("recruiter: 'Custom msg for {name}'\n")
        engine = MessageTemplateEngine(config_path=override)
        msg = engine.generate(MessageContext(
            person_name="Test",
            company_name="Co",
            role_title="Role",
            person_title="Recruiter",
            person_type="recruiter",
        ))
        assert msg == "Custom msg for Test"

    def test_yaml_hot_reload(self, tmp_path):
        override = tmp_path / "messages.yaml"
        override.write_text("recruiter: 'First {name}'\n")
        engine = MessageTemplateEngine(config_path=override)
        assert "First" in engine.generate(MessageContext(
            "A", "Co", "R", "T", "recruiter",
        ))
        override.write_text("recruiter: 'Second {name}'\n")
        msg = engine.generate(MessageContext(
            "A", "Co", "R", "T", "recruiter",
        ))
        assert "Second" in msg


# ---------------------------------------------------------------------------
# Tests — ConnectionSender
# ---------------------------------------------------------------------------

class TestConnectionSender:
    def setup_method(self):
        self.sender = ConnectionSender()
        self.sender.human = _FakeHuman()

    @pytest.mark.asyncio
    async def test_send_connection_success_with_note(self):
        connect_btn = _FakeElement(text="Connect", visible=True)
        add_note_btn = _FakeElement(text="Add a note", visible=True)
        note_ta = _FakeElement(text="", visible=True)
        send_btn = _FakeElement(text="Send", visible=True)

        page = FakePage(
            connect_button=connect_btn,
            add_note_button=add_note_btn,
            note_textarea=note_ta,
            send_button=send_btn,
        )
        result = await self.sender.send_connection(
            page, "https://linkedin.com/in/alice", "Hi Alice!"
        )
        assert result["success"] is True
        assert result["error"] is None
        assert page.goto_log[-1] == "https://linkedin.com/in/alice"

    @pytest.mark.asyncio
    async def test_send_connection_no_connect_button(self):
        page = FakePage(connect_button=None)
        result = await self.sender.send_connection(
            page, "https://linkedin.com/in/bob", "Hi Bob!"
        )
        assert result["success"] is False
        assert "No Connect" in result["error"]

    @pytest.mark.asyncio
    async def test_send_connection_send_button_missing(self):
        connect_btn = _FakeElement(text="Connect", visible=True)
        add_note_btn = _FakeElement(text="Add a note", visible=True)
        note_ta = _FakeElement(text="", visible=True)
        page = FakePage(
            connect_button=connect_btn,
            add_note_button=add_note_btn,
            note_textarea=note_ta,
            send_button=None,
        )
        result = await self.sender.send_connection(
            page, "https://linkedin.com/in/carol", "Hi Carol!"
        )
        assert result["success"] is False
        assert "Send button" in result["error"]


# ---------------------------------------------------------------------------
# Tests — NetworkingService (full orchestration with stubbed sub-components)
# ---------------------------------------------------------------------------

class TestNetworkingServiceOrchestration:
    """Integration test wiring searcher → templates → sender → DB."""

    @pytest.mark.asyncio
    async def test_full_flow_creates_connections_in_db(self, monkeypatch):
        from tests.conftest import _load_app_test_dependencies

        if not _load_app_test_dependencies():
            pytest.skip("sqlalchemy not installed")

        from tests.conftest import engine as test_engine, Base
        from sqlalchemy.orm import sessionmaker

        SessionLocal = sessionmaker(bind=test_engine)
        db = SessionLocal()

        # Stub the sub-components to avoid real browser interactions.
        svc = NetworkingService()

        async def fake_search_people(page, company, keywords, max_results=5):
            return [
                {
                    "profile_url": "https://linkedin.com/in/alice",
                    "person_name": "Alice Recruiter",
                    "title": "Senior Recruiter at Google",
                    "person_type": "recruiter",
                },
                {
                    "profile_url": "https://linkedin.com/in/bob",
                    "person_name": "Bob Manager",
                    "title": "Engineering Manager",
                    "person_type": "hiring_manager",
                },
            ]

        async def fake_send_connection(page, url, message):
            return {"success": True, "error": None}

        monkeypatch.setattr(svc.searcher, "search_people", fake_search_people)
        monkeypatch.setattr(svc.sender, "send_connection", fake_send_connection)
        monkeypatch.setattr(svc, "human", _FakeHuman())

        # Monkey-patch rate limiter to allow connections.
        from app.safety.rate_limiter import rate_limiter
        monkeypatch.setattr(rate_limiter, "can_connect", lambda db_: (True, "ok"))
        monkeypatch.setattr(rate_limiter, "get_daily_connect_remaining", lambda db_: 10)

        page = FakePage()
        results = await svc.network_after_apply(
            page=page,
            company="Google",
            role_title="Software Engineer",
            job_id=42,
            db=db,
            max_connects=3,
            person_types=["recruiter", "hiring_manager"],
        )

        # Both people should be processed (filtered by person_types)
        assert len(results) == 2
        assert all(r["success"] for r in results)

        # Verify DB records
        from app.models import Connection
        conns = db.query(Connection).all()
        assert len(conns) == 2
        urls = {c.profile_url for c in conns}
        assert "https://linkedin.com/in/alice" in urls
        assert "https://linkedin.com/in/bob" in urls
        for c in conns:
            assert c.status == "sent"
            assert c.company == "Google"
            assert c.job_id == 42

        db.close()

    @pytest.mark.asyncio
    async def test_skips_existing_connections(self, monkeypatch):
        from tests.conftest import _load_app_test_dependencies

        if not _load_app_test_dependencies():
            pytest.skip("sqlalchemy not installed")

        from tests.conftest import engine as test_engine, Base
        from sqlalchemy.orm import sessionmaker
        from app.models import Connection

        SessionLocal = sessionmaker(bind=test_engine)
        db = SessionLocal()

        # Pre-seed an existing connection
        existing = Connection(
            job_id=1,
            profile_url="https://linkedin.com/in/alice",
            person_name="Alice Recruiter",
            title="Recruiter",
            company="Google",
            person_type="recruiter",
            message="Hi",
            status="sent",
        )
        db.add(existing)
        db.commit()

        svc = NetworkingService()

        async def fake_search_people(page, company, keywords, max_results=5):
            return [
                {
                    "profile_url": "https://linkedin.com/in/alice",
                    "person_name": "Alice Recruiter",
                    "title": "Senior Recruiter",
                    "person_type": "recruiter",
                },
                {
                    "profile_url": "https://linkedin.com/in/newperson",
                    "person_name": "New Person",
                    "title": "Engineer",
                    "person_type": "engineer",
                },
            ]

        async def fake_send_connection(page, url, message):
            return {"success": True, "error": None}

        monkeypatch.setattr(svc.searcher, "search_people", fake_search_people)
        monkeypatch.setattr(svc.sender, "send_connection", fake_send_connection)
        monkeypatch.setattr(svc, "human", _FakeHuman())

        from app.safety.rate_limiter import rate_limiter
        monkeypatch.setattr(rate_limiter, "can_connect", lambda db_: (True, "ok"))
        monkeypatch.setattr(rate_limiter, "get_daily_connect_remaining", lambda db_: 10)

        page = FakePage()
        results = await svc.network_after_apply(
            page=page,
            company="Google",
            role_title="SWE",
            job_id=99,
            db=db,
            max_connects=5,
            person_types=["recruiter", "engineer"],
        )

        # Alice skipped, New Person processed
        assert len(results) == 1
        assert results[0]["person"] == "New Person"

        conns = db.query(Connection).filter(Connection.job_id == 99).all()
        assert len(conns) == 1
        assert conns[0].profile_url == "https://linkedin.com/in/newperson"

        db.close()

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_all(self, monkeypatch):
        from tests.conftest import _load_app_test_dependencies

        if not _load_app_test_dependencies():
            pytest.skip("sqlalchemy not installed")

        from tests.conftest import engine as test_engine
        from sqlalchemy.orm import sessionmaker

        SessionLocal = sessionmaker(bind=test_engine)
        db = SessionLocal()

        svc = NetworkingService()
        from app.safety.rate_limiter import rate_limiter
        monkeypatch.setattr(rate_limiter, "can_connect", lambda db_: (False, "limit reached"))

        page = FakePage()
        results = await svc.network_after_apply(
            page=page,
            company="Google",
            role_title="SWE",
            job_id=1,
            db=db,
        )
        assert results == []
        db.close()

    @pytest.mark.asyncio
    async def test_filters_by_person_type(self, monkeypatch):
        from tests.conftest import _load_app_test_dependencies

        if not _load_app_test_dependencies():
            pytest.skip("sqlalchemy not installed")

        from tests.conftest import engine as test_engine
        from sqlalchemy.orm import sessionmaker

        SessionLocal = sessionmaker(bind=test_engine)
        db = SessionLocal()

        svc = NetworkingService()

        async def fake_search_people(page, company, keywords, max_results=5):
            return [
                {"profile_url": "https://linkedin.com/in/r1", "person_name": "R1",
                 "title": "Recruiter", "person_type": "recruiter"},
                {"profile_url": "https://linkedin.com/in/e1", "person_name": "E1",
                 "title": "Engineer", "person_type": "engineer"},
                {"profile_url": "https://linkedin.com/in/h1", "person_name": "H1",
                 "title": "Director", "person_type": "hiring_manager"},
            ]

        async def fake_send_connection(page, url, message):
            return {"success": True, "error": None}

        monkeypatch.setattr(svc.searcher, "search_people", fake_search_people)
        monkeypatch.setattr(svc.sender, "send_connection", fake_send_connection)
        monkeypatch.setattr(svc, "human", _FakeHuman())

        from app.safety.rate_limiter import rate_limiter
        monkeypatch.setattr(rate_limiter, "can_connect", lambda db_: (True, "ok"))
        monkeypatch.setattr(rate_limiter, "get_daily_connect_remaining", lambda db_: 10)

        page = FakePage()
        results = await svc.network_after_apply(
            page=page,
            company="Co",
            role_title="SWE",
            job_id=1,
            db=db,
            max_connects=10,
            person_types=["recruiter"],  # Only recruiters
        )

        assert len(results) == 1
        assert results[0]["type"] == "recruiter"
        db.close()
