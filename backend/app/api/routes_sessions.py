"""Session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import database as db
from ..services import sessions as sessions_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    is_demo: bool = False


@router.get("")
def list_sessions(limit: int = 50):
    return {"items": sessions_service.list_sessions(limit=min(max(limit, 1), 200))}


@router.get("/active")
def active_session():
    return {"session": sessions_service.get_active_session()}


@router.post("", status_code=201)
def create_session(payload: SessionCreate):
    session = sessions_service.create_session(payload.name, is_demo=payload.is_demo)
    return session


@router.post("/{session_id}/start")
def start_session(session_id: str):
    if not sessions_service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return sessions_service.start_session(session_id)


@router.post("/{session_id}/end")
def end_session(session_id: str):
    session = sessions_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Session is not active.")
    ended = sessions_service.end_session(session_id)
    db.audit("session.end", "session", session_id, db.get_settings().get("operator_name"), {})
    return ended
