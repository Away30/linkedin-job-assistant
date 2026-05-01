import json
import logging
import os
from pathlib import Path
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


# Settings the user is allowed to override at runtime via /settings POST.
# Anything NOT in this set must come from .env or defaults — protects DB_PATH,
# CORS_ORIGINS, BASE_DIR, and similar load-bearing config from being mutated
# by a UI request.
RUNTIME_OVERRIDABLE_KEYS: frozenset[str] = frozenset({
    "MAX_APPLIES_PER_DAY",
    "MAX_CONNECTS_PER_DAY",
    "ACTION_DELAY_MIN",
    "ACTION_DELAY_MAX",
    "NETWORKING_ENABLED",
    "NETWORKING_MAX_PER_SESSION",
    "NETWORKING_PERSON_TYPES",
})


def _build_cors_origins() -> tuple[list[str], str | None]:
    """Build CORS origins from environment configuration.

    Returns ``(origins, regex)``. When ``LJA_EXTENSION_ID`` is set the origins
    list is exact (no wildcard) — that is the safe production mode and is
    compatible with ``allow_credentials=True``. Without an extension ID we
    fall back to a regex that matches any chrome-extension://… or localhost
    HTTP origin so dev mode keeps working; in that mode credentials are
    intentionally disabled by the app to avoid the spec-banned
    "credentials + wildcard" combination.
    """
    extension_id = os.environ.get("LJA_EXTENSION_ID", "").strip()
    if extension_id:
        return (
            [
                f"chrome-extension://{extension_id}",
                "http://localhost:8899",
                "http://127.0.0.1:8899",
            ],
            None,
        )
    return ([], r"^(chrome-extension://[a-z0-9]+|http://(localhost|127\.0\.0\.1)(:\d+)?)$")


_DEFAULT_CORS_ORIGINS, _DEFAULT_CORS_ORIGIN_REGEX = _build_cors_origins()


class Settings(BaseSettings):
    APP_NAME: str = "LinkedIn Job Assistant"
    API_PREFIX: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8899

    # Database
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "db" / "linkedin_assistant.db"
    DATABASE_URL: str = ""

    # Resume storage
    RESUME_DIR: Path = DATA_DIR / "resumes"

    # Browser
    BROWSER_PROFILE_DIR: Path = DATA_DIR / "browser_profile"
    BROWSER_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"

    # Browser connection: CDP = connect to user's Chrome, fallback = launch new browser
    USE_CDP: bool = True
    CDP_ENDPOINT: str = "http://localhost:9222"

    # Proxy (optional): set LJA_PROXY_SERVER to e.g. "socks5://127.0.0.1:1080" or "http://proxy:8080"
    PROXY_SERVER: str = ""
    PROXY_USERNAME: str = ""
    PROXY_PASSWORD: str = ""

    # Form answers
    FORM_ANSWERS_PATH: Path = DATA_DIR / "config" / "form_answers.yaml"

    # Rate limits
    MAX_APPLIES_PER_DAY: int = 25
    MAX_CONNECTS_PER_DAY: int = 20

    # Warmup (days to reach full rate)
    WARMUP_DAYS: int = 7
    WARMUP_START_APPLIES: int = 3

    # Session limits
    MAX_SESSION_MINUTES: int = 120
    BREAK_INTERVAL_MINUTES_MIN: int = 40
    BREAK_INTERVAL_MINUTES_MAX: int = 60
    BREAK_DURATION_MINUTES_MIN: int = 5
    BREAK_DURATION_MINUTES_MAX: int = 15

    # Delays (seconds)
    ACTION_DELAY_MIN: float = 3.0
    ACTION_DELAY_MAX: float = 12.0
    LONG_BREAK_MIN: float = 30.0
    LONG_BREAK_MAX: float = 120.0

    # Networking (post-apply recruiter connection)
    NETWORKING_ENABLED: bool = False
    NETWORKING_MAX_PER_SESSION: int = 5
    NETWORKING_PERSON_TYPES: str = "recruiter"  # comma-separated
    CONNECTION_MESSAGES_PATH: Path = DATA_DIR / "config" / "connection_messages.yaml"

    # CORS — exact origin list when LJA_EXTENSION_ID is set, otherwise the
    # regex below matches dev origins (and credentials are turned off in
    # main.py to avoid the spec-banned "credentials + wildcard" combo).
    CORS_ORIGINS: list[str] = _DEFAULT_CORS_ORIGINS
    CORS_ORIGIN_REGEX: str | None = _DEFAULT_CORS_ORIGIN_REGEX

    class Config:
        env_prefix = "LJA_"
        validate_assignment = True

    def runtime_overrides_path(self) -> Path:
        return self.DATA_DIR / "config" / "runtime_settings.json"

    def model_post_init(self, __context):
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DB_PATH}"
        self._apply_runtime_overrides()

    def _apply_runtime_overrides(self) -> None:
        """Read DATA_DIR/config/runtime_settings.json and apply allowlisted keys."""
        path = self.runtime_overrides_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load runtime overrides at %s: %s", path, exc)
            return

        for raw_key, value in data.items():
            key = raw_key.upper()
            if key not in RUNTIME_OVERRIDABLE_KEYS:
                continue
            try:
                setattr(self, key, value)
            except Exception as exc:  # pydantic validation
                logger.warning("Skipping invalid runtime override %s=%r: %s", key, value, exc)

    def persist_runtime_overrides(self, updates: dict) -> dict:
        """Validate, persist, and apply runtime setting updates.

        Returns the dict that was actually written. Raises ValueError on
        unknown keys or pydantic validation failures so the caller can map
        to a 4xx response.
        """
        cleaned: dict = {}
        for raw_key, value in updates.items():
            key = raw_key.upper()
            if key not in RUNTIME_OVERRIDABLE_KEYS:
                raise ValueError(f"Setting '{raw_key}' is not user-editable")
            try:
                setattr(self, key, value)
            except Exception as exc:
                raise ValueError(f"Invalid value for '{raw_key}': {exc}") from exc
            cleaned[key] = getattr(self, key)

        path = self.runtime_overrides_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f) or {}
            except (OSError, json.JSONDecodeError):
                existing = {}
        existing.update(cleaned)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        return cleaned

settings = Settings()
