"""HTTP endpoints for session lifecycle + staged writes."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from palio_bot.core.file_store_local import ReadOnlyFile, UnknownFile
from palio_bot.core.lock_manager import LockConflict
from palio_bot.core.session_service import (
    NotLockHolder,
    SessionService,
    ValidationFailed,
)
from palio_bot.core.session_store import UnknownSession

router = APIRouter(prefix="/api/sessions")


def _service(request: Request) -> SessionService:
    return request.app.state.session_service


class CreateSessionBody(BaseModel):
    label: str


class PutFileBody(BaseModel):
    content: Dict[str, Any]


@router.post("")
async def create_session(body: CreateSessionBody, request: Request):
    svc = _service(request)
    session = svc.create_session(body.label)
    return {
        "id": session.id,
        "label": session.label,
        "created_at": session.created_at.isoformat(),
    }


@router.get("")
async def list_sessions(request: Request):
    return {"sessions": _service(request).list_sessions()}


@router.post("/{session_id}/acquire/{file_name}")
async def acquire(session_id: str, file_name: str, request: Request):
    svc = _service(request)
    try:
        result = svc.acquire(session_id, file_name)
    except UnknownSession:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}")
    except UnknownFile:
        raise HTTPException(status_code=404, detail=f"unknown file {file_name}")
    except LockConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "lock_conflict",
                "file": exc.file_name,
                "holder_session_id": exc.holder_session_id,
            },
        )
    return {"content": result.content, "version": result.version}


@router.put("/{session_id}/files/{file_name}")
async def put_file(
    session_id: str, file_name: str, body: PutFileBody, request: Request
):
    svc = _service(request)
    try:
        version = svc.put(session_id, file_name, body.content)
    except UnknownSession:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}")
    except UnknownFile:
        raise HTTPException(status_code=404, detail=f"unknown file {file_name}")
    except ReadOnlyFile:
        raise HTTPException(status_code=403, detail=f"{file_name} is read-only")
    except NotLockHolder as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "lock_not_held",
                "file": exc.file_name,
                "holder_session_id": exc.holder,
            },
        )
    except ValidationFailed as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    return {"version": version}


@router.post("/{session_id}/commit")
async def commit(session_id: str, request: Request):
    svc = _service(request)
    try:
        versions = svc.commit(session_id)
    except UnknownSession:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}")
    return {"files": versions}


@router.post("/{session_id}/discard")
async def discard(session_id: str, request: Request):
    svc = _service(request)
    try:
        svc.discard(session_id)
    except UnknownSession:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}")
    return {"ok": True}
