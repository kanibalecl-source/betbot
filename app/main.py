from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.routes import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.realtime.worker import realtime_loop
from app.core.security import validate_security_configuration
import asyncio

configure_logging()
settings = get_settings()
validate_security_configuration()


@asynccontextmanager
async def lifespan(application: FastAPI):
    task = None
    if settings.realtime_enabled:
        task = asyncio.create_task(realtime_loop(settings.realtime_tick_seconds))
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

app = FastAPI(
    title=settings.app_name,
    version=settings.model_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(v1_router)

@app.get("/")
def root():
    return {
        "ok": True,
        "service": settings.app_name,
        "version": settings.model_version,
        "betting_enabled": settings.betting_enabled,
    }
