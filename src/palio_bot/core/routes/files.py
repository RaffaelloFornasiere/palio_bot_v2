"""Read-only file endpoints.

Shape: `GET /api/files/{file_name}[/{year}]` plus legacy aliases
`GET /api/{palio,leaderboard,palio_games_status}[/{year}]` for the React
SDK generated from the retired api_server.

Two read modes, branched on bearer-auth presence:
  * **Authenticated** (editor webapp / CLI / agent): working tree HEAD —
    the in-progress state, including intra-session writes not yet saved.
  * **Anonymous** (public webapp): `refs/palio/last_save` — the last
    fully-saved state. Intra-session edits are invisible to the public
    until the user saves.

Year-scoped endpoints always read directly from `data/<year>/` and
ignore the auth branch: archived years are immutable snapshots and not
tracked by the history layer.
"""

import json
from pathlib import Path
from typing import List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Request
from pydantic import BaseModel

from palio_bot.core.auth import is_authenticated
from palio_bot.core.history import LAST_SAVE_REF, HistoryService
from palio_bot.models.game_status_models import PalioGamesStatus
from palio_bot.models.leaderboard_models import Leaderboard
from palio_bot.models.palio_models import PalioData

router = APIRouter(prefix="/api")

_FILE_KEYS: dict[str, Tuple[str, Type[BaseModel]]] = {
    "palio": ("palio_file_path", PalioData),
    "leaderboard": ("leaderboard_file_path", Leaderboard),
    "palio_games_status": ("palio_games_status_path", PalioGamesStatus),
}


class AvailableYearsResponse(BaseModel):
    years: List[int]


def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{label} not found at {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in {label}")


def _load_current(request: Request, file_name: str, authed: bool) -> dict:
    """Return canonical content for `file_name`.

    Authenticated → working tree (HEAD). Anonymous → last_save ref via
    HistoryService.read_at_ref, with a fallback to working tree if the
    history layer is unavailable or the ref hasn't been initialised yet.
    """
    attr, validator = _FILE_KEYS[file_name]
    path: Path = getattr(request.app.state.config, attr)

    if not authed:
        history: HistoryService | None = getattr(
            request.app.state, "history", None
        )
        if history is not None:
            blob = history.read_at_ref(path.name, ref=LAST_SAVE_REF)
            if blob is not None:
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=500, detail=f"Invalid JSON in {file_name}"
                    )

    return _load_json(path, file_name)


@router.get("/files/{file_name}")
async def get_file(
    file_name: str, request: Request, authed: bool = Depends(is_authenticated)
):
    if file_name not in _FILE_KEYS:
        raise HTTPException(status_code=404, detail=f"unknown file: {file_name}")
    _, validator = _FILE_KEYS[file_name]
    data = _load_current(request, file_name, authed)
    return validator.model_validate(data).model_dump()


@router.get("/files/{file_name}/{year}")
async def get_file_by_year(
    file_name: str,
    request: Request,
    year: int = PathParam(..., ge=1900, le=2100),
):
    if file_name not in _FILE_KEYS:
        raise HTTPException(status_code=404, detail=f"unknown file: {file_name}")
    _, validator = _FILE_KEYS[file_name]
    data_dir: Path = request.app.state.config.data_dir
    path = data_dir / str(year) / f"{file_name}.json"
    data = _load_json(path, f"{file_name} ({year})")
    return validator.model_validate(data).model_dump()


@router.get("/years", response_model=AvailableYearsResponse)
async def get_available_years(request: Request) -> AvailableYearsResponse:
    data_dir: Path = request.app.state.config.data_dir
    years: list[int] = []
    if data_dir.exists():
        for item in data_dir.iterdir():
            if item.is_dir() and item.name.isdigit() and (item / "palio.json").exists():
                years.append(int(item.name))
    years.sort(reverse=True)
    return AvailableYearsResponse(years=years)


# ---------- legacy aliases (React SDK compatibility) ----------


def _bind_alias(file_name: str) -> None:
    """Register `GET /api/{file_name}[/{year}]` pointing at the generic handler."""
    _, validator = _FILE_KEYS[file_name]

    async def _current(
        request: Request, authed: bool = Depends(is_authenticated)
    ):
        data = _load_current(request, file_name, authed)
        return validator.model_validate(data).model_dump()

    async def _by_year(
        request: Request,
        year: int = PathParam(..., ge=1900, le=2100),
    ):
        data_dir: Path = request.app.state.config.data_dir
        path = data_dir / str(year) / f"{file_name}.json"
        data = _load_json(path, f"{file_name} ({year})")
        return validator.model_validate(data).model_dump()

    router.add_api_route(
        f"/{file_name}",
        _current,
        response_model=validator,
        methods=["GET"],
        operation_id=f"get_{file_name}_data",
    )
    router.add_api_route(
        f"/{file_name}/{{year}}",
        _by_year,
        response_model=validator,
        methods=["GET"],
        operation_id=f"get_{file_name}_data_by_year",
    )


for _name in _FILE_KEYS:
    _bind_alias(_name)
