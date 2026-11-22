"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException

from ..core.config import CONFIG
from ..runtime import ModelNotReady, get_pipeline
from ..services.pipeline import RecognitionPipeline


def pipeline_or_503() -> RecognitionPipeline:
    try:
        return get_pipeline()
    except ModelNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Protect dangerous endpoints when CRABBOTS_ADMIN_TOKEN is configured.

    In a local demo the token is empty and the UI is the access boundary. Any
    shared deployment should set the token; the Settings page surfaces whether
    it is enabled.
    """
    if not CONFIG.admin_token:
        return
    if x_admin_token != CONFIG.admin_token:
        raise HTTPException(status_code=403, detail="Admin token required for this action.")
