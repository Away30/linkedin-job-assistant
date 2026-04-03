import os
from pathlib import Path
from pydantic_settings import BaseSettings


def _build_cors_origins() -> list[str]:
    """Build CORS origins from environment configuration."""
    extension_id = os.environ.get("LJA_EXTENSION_ID", "")
    if extension_id:
        return [f"chrome-extension://{extension_id}", "http://localhost:8899"]
    # Development mode: allow all chrome extensions and localhost
    return ["chrome-extension://*", "http://localhost:*"]


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

    # CORS
    CORS_ORIGINS: list[str] = _build_cors_origins()

    class Config:
        env_prefix = "LJA_"

    def model_post_init(self, __context):
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DB_PATH}"

settings = Settings()
