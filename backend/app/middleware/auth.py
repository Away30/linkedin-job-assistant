"""API Key authentication middleware — pure ASGI to support SSE streaming."""
import secrets
import logging
from pathlib import Path
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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


class APIKeyMiddleware:
    """Pure ASGI middleware — validates X-API-Key on /api/ routes.

    Unlike BaseHTTPMiddleware, this does not buffer StreamingResponse,
    so SSE streams work correctly.
    """

    def __init__(self, app, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Exempt non-API routes
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Exempt health check and docs
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            await self.app(scope, receive, send)
            return

        # Extract headers from scope; use constant-time compare to avoid timing oracles.
        for name, value in scope.get("headers", []):
            if name == b"x-api-key":
                try:
                    candidate = value.decode("ascii")
                except UnicodeDecodeError:
                    break
                if secrets.compare_digest(candidate, self.api_key):
                    await self.app(scope, receive, send)
                    return
                break

        # No valid API key — return 401
        response = JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key"},
        )
        await response(scope, receive, send)
