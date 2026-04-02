"""API Key authentication middleware."""
import secrets
import logging
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_or_create_api_key(config_dir: Path) -> str:
    """Get existing API key or generate a new one."""
    key_file = config_dir / "api_key.txt"
    config_dir.mkdir(parents=True, exist_ok=True)

    if key_file.exists():
        return key_file.read_text().strip()

    api_key = secrets.token_urlsafe(32)
    key_file.write_text(api_key)
    logger.info("Generated new API key saved to %s", key_file)
    return api_key


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header on all /api/ routes."""

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # Exempt health check and docs
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # Only protect /api/ routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key or api_key != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
