"""HTTP endpoints for session lifecycle + write-through edits."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from palio_bot.core.auth import require_auth
from palio_bot.core.file_store_local import ReadOnlyFile, UnknownFile
from palio_bot.core.session_service import SessionService, ValidationFailed
from palio_bot.core.session_store import UnknownSession

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_auth)])


def _service(request: Request) -> SessionService:
    return request.app.state.session_service


class CreateSessionBody(BaseModel):
    label: str


class PutFileBody(BaseModel):
    content: Dict[str, Any]
    tool: Optional[str] = None


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
    return {"content": result.content, "version": result.version}


@router.put("/{session_id}/files/{file_name}")
async def put_file(
    session_id: str, file_name: str, body: PutFileBody, request: Request
):
    svc = _service(request)
    try:
        version = svc.put(session_id, file_name, body.content, tool=body.tool)
    except UnknownSession:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}")
    except UnknownFile:
        raise HTTPException(status_code=404, detail=f"unknown file {file_name}")
    except ReadOnlyFile:
        raise HTTPException(status_code=403, detail=f"{file_name} is read-only")
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


@router.get("/{session_id}/history/{file_name}")
async def session_history(
    session_id: str, file_name: str, request: Request, limit: int = 10
):
    svc = _service(request)
    try:
        entries = svc.list_session_history(session_id, file_name, limit=limit)
    except UnknownSession:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}")
    except UnknownFile:
        raise HTTPException(status_code=404, detail=f"unknown file {file_name}")
    return {"entries": entries}


class RevertBody(BaseModel):
    n_steps: int


@router.post("/{session_id}/revert/{file_name}")
async def session_revert(
    session_id: str, file_name: str, body: RevertBody, request: Request
):
    svc = _service(request)
    try:
        sha = svc.revert(session_id, file_name, body.n_steps)
    except UnknownSession:
        raise HTTPException(status_code=404, detail=f"unknown session {session_id}")
    except UnknownFile:
        raise HTTPException(status_code=404, detail=f"unknown file {file_name}")
    if sha is None:
        raise HTTPException(
            status_code=400,
            detail=f"cannot revert {body.n_steps} step(s): out of range",
        )
    return {"applied": True, "n_steps": body.n_steps}
