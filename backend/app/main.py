from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import init_db
from app.api.routes import router as api_router
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
logging.info("API Key authentication enabled. Key file: %s", settings.DATA_DIR / "config" / "api_key.txt")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
