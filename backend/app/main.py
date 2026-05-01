from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import init_db
from app.api.routes import router as api_router
from app.api.connections_routes import router as connections_router
from app.utils.logging_config import setup_logging
from app.middleware.auth import APIKeyMiddleware, get_or_create_api_key

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting LinkedIn Job Assistant")
    init_db()
    yield
    # Shutdown
    from app.services.automation_service import automation_service
    await automation_service.stop()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# API Key authentication middleware
api_key = get_or_create_api_key(settings.DATA_DIR / "config")
app.add_middleware(APIKeyMiddleware, api_key=api_key)
logging.info("API Key authentication enabled.")
logging.info("=" * 60)
logging.info("  YOUR API KEY: %s", api_key)
logging.info("  请复制此 Key 到 Chrome 扩展设置页")
logging.info("=" * 60)

# CORS: with allow_credentials=True a wildcard origin is rejected by the
# browser. We keep credentials off in dev mode (regex-based origins) and on
# only when LJA_EXTENSION_ID pins a single origin.
if settings.CORS_ORIGIN_REGEX:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logging.info("CORS: dev mode (regex match, credentials off)")
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logging.info("CORS: pinned origins=%s", settings.CORS_ORIGINS)

app.include_router(api_router, prefix=settings.API_PREFIX)
app.include_router(connections_router, prefix=settings.API_PREFIX)

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
