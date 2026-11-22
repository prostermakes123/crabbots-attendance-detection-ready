"""FastAPI application factory."""

from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import (
    routes_attendance,
    routes_detection,
    routes_live,
    routes_members,
    routes_recognition,
    routes_sessions,
    routes_settings,
    routes_system,
)
from .core.config import CONFIG
from .core.logging import configure_logging, get_logger
from .db import database as db
from .runtime import ModelNotReady, get_pipeline
from .services import sessions as sessions_service

log = get_logger("main")
STATIC_DIR = CONFIG.static_dir
INDEX_FILE = STATIC_DIR / "index.html"


def _warm_models() -> None:
    try:
        get_pipeline()
    except ModelNotReady as exc:
        log.warning("models not ready: %s", exc)
    except Exception:  # noqa: BLE001
        log.exception("unexpected error while warming models")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(CONFIG.log_level)
    db.init_db()
    sessions_service.ensure_active_session()
    log.info("CrabBots Attendance %s starting", __version__)
    threading.Thread(target=_warm_models, name="model-warmup", daemon=True).start()
    yield
    log.info("shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="CrabBots Attendance",
        version=__version__,
        description="Face recognition and attendance tracking for CrabBots.",
        lifespan=lifespan,
    )

    for module in (
        routes_system,
        routes_members,
        routes_recognition,
        routes_sessions,
        routes_attendance,
        routes_detection,
        routes_settings,
        routes_live,
    ):
        app.include_router(module.router)

    @app.exception_handler(ModelNotReady)
    async def _model_not_ready(_: Request, exc: ModelNotReady):
        return JSONResponse(status_code=503, content={"detail": str(exc), "code": "models_missing"})

    @app.middleware("http")
    async def _headers_and_timing(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
            "connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
            elapsed = (time.perf_counter() - started) * 1000
            if elapsed > 400:
                log.debug("slow %s %s %.0fms", request.method, request.url.path, elapsed)
        return response

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        path = STATIC_DIR / "favicon.svg"
        if path.is_file():
            return FileResponse(path, media_type="image/svg+xml")
        return JSONResponse(status_code=404, content={"detail": "not found"})

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(INDEX_FILE, media_type="text/html")

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str):
        if path.startswith(("api/", "ws/")):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (STATIC_DIR / path).resolve()
        if candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(INDEX_FILE, media_type="text/html")

    return app


app = create_app()
