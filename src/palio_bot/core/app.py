"""FastAPI app assembly for palio_bot.core.

Call `create_app()` in tests to inject a CoreConfig pointed at a temp dir.
The module-level `app` is built with defaults for uvicorn entry.
"""

import logging
from pathlib import Path
from typing import Callable, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from palio_bot.core.config import CoreConfig
from palio_bot.core.stream import Stream
from palio_bot.core.file_store_local import LocalFileStore
from palio_bot.core.lock_manager import LockManager
from palio_bot.core.registry_factory import build_registry
from palio_bot.core.routes import admin, events_ws, files, sessions
from palio_bot.core.session_service import SessionService
from palio_bot.core.session_store import SessionStore
from palio_bot.leaderboard_updater import LeaderboardUpdater

# Project root for locating the React build.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REACT_BUILD_PATH = _PROJECT_ROOT / "website" / "build"

# Static assets shipped with palio-core (not the React build).
_CORE_STATIC_PATH = Path(__file__).resolve().parent / "static"

logger = logging.getLogger(__name__)


def _leaderboard_hook(config: CoreConfig) -> Callable[[List[str]], None]:
    updater = LeaderboardUpdater(
        palio_file_path=config.palio_file_path,
        palio_games_status_path=config.palio_games_status_path,
        leaderboard_file_path=config.leaderboard_file_path,
    )

    triggers = {"palio", "palio_games_status"}

    def hook(committed_files: List[str]) -> None:
        if not triggers.intersection(committed_files):
            return
        try:
            updater.update_leaderboard()
        except Exception:
            logger.exception("core: leaderboard recompute failed")

    return hook


def create_app(
    config: Optional[CoreConfig] = None,
    *,
    enable_leaderboard_hook: bool = True,
) -> FastAPI:
    config = config or CoreConfig()
    app = FastAPI(title="palio-core", version="0.1.0")

    registry = build_registry(config)
    file_store = LocalFileStore(registry)
    session_store = SessionStore()
    lock_manager = LockManager()
    stream = Stream()

    on_commit: Optional[Callable[[List[str]], None]] = (
        _leaderboard_hook(config) if enable_leaderboard_hook else None
    )

    session_service = SessionService(
        registry=registry,
        file_store=file_store,
        session_store=session_store,
        lock_manager=lock_manager,
        stream=stream,
        on_commit=on_commit,
    )

    app.state.config = config
    app.state.registry = registry
    app.state.file_store = file_store
    app.state.session_store = session_store
    app.state.lock_manager = lock_manager
    app.state.stream = stream
    app.state.session_service = session_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(files.router)
    app.include_router(sessions.router)
    app.include_router(admin.router)
    app.include_router(events_ws.router)

    _mount_events_viewer(app)
    _mount_react_app(app)

    return app


def _mount_events_viewer(app: FastAPI) -> None:
    """Thin standalone page that tails the unified WS bus.

    Registered before the React catch-all so it wins path resolution; reads
    its WS URL from `window.location`, so it works wherever core is served.
    """
    viewer_path = _CORE_STATIC_PATH / "events_viewer.html"
    if not viewer_path.exists():
        return

    @app.get("/events-viewer", include_in_schema=False)
    async def serve_events_viewer():
        return FileResponse(str(viewer_path))


def _mount_react_app(app: FastAPI) -> None:
    """Serve the React build at `/` with a catch-all for client-side routing.

    Preserved from the retired `api/api_server.py`. No-op if the build
    directory is absent (dev mode: the frontend runs on Vite).
    """
    if not (_REACT_BUILD_PATH.exists() and _REACT_BUILD_PATH.is_dir()):
        return

    static_dir = _REACT_BUILD_PATH / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        index_path = _REACT_BUILD_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="React app not found")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_app(full_path: str):
        if full_path.startswith(("api/", "admin/", "events", "docs", "redoc", "openapi.json", "static/")):
            raise HTTPException(status_code=404, detail="Not found")
        index_path = _REACT_BUILD_PATH / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="React app not found")


app = create_app()
