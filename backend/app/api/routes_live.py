"""Live recognition over WebSocket.

The browser owns the camera (getUserMedia) and streams compressed frames; the
server returns tracked detections. That keeps the server camera-agnostic and
lets the same code run on a laptop or in a container.
"""

from __future__ import annotations

import asyncio
import base64
import binascii

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.logging import get_logger
from ..db import database as db
from ..runtime import ModelNotReady, get_pipeline
from ..services import images as image_utils
from ..services import sessions as sessions_service
from ..services.tracker import MultiFaceTracker

log = get_logger("live")
router = APIRouter()


@router.websocket("/ws/live")
async def live_socket(websocket: WebSocket, session_id: str | None = None, source: str = "browser camera"):
    await websocket.accept()
    try:
        pipeline = get_pipeline()
    except ModelNotReady as exc:
        await websocket.send_json({"type": "error", "code": "models_missing", "message": str(exc)})
        await websocket.close(code=1013)
        return

    settings = db.get_settings()
    tracker = MultiFaceTracker()
    max_mb = float(settings.get("max_upload_mb", 12))
    resolved_session = session_id
    if not resolved_session:
        resolved_session = await asyncio.to_thread(sessions_service.ensure_active_session)
        resolved_session = resolved_session["id"]

    await websocket.send_json({"type": "ready", "session_id": resolved_session})

    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await websocket.send_json({"type": "error", "code": "bad_message", "message": "WebSocket messages must be JSON objects."})
                continue
            kind = message.get("type")
            if kind == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if kind == "reset":
                tracker.reset()
                await websocket.send_json({"type": "reset_ok"})
                continue
            if kind != "frame":
                continue
            try:
                frame = image_utils.decode_data_url(message.get("image", ""), max_mb=max_mb)
            except (image_utils.ImageValidationError, binascii.Error, ValueError) as exc:
                await websocket.send_json({"type": "error", "code": "bad_frame", "message": str(exc)})
                continue

            target_session = message.get("session_id") or resolved_session
            if not message.get("session_id"):
                active = await asyncio.to_thread(sessions_service.get_active_session)
                target_session = active["id"] if active else None
            result = await asyncio.to_thread(
                pipeline.process_frame,
                frame,
                tracker,
                target_session,
                message.get("source") or source,
                message.get("record", True) is True,
                "live",
            )
            result.update({"type": "result", "client_ts": message.get("ts")})
            await websocket.send_json(result)
    except WebSocketDisconnect:
        log.info("live socket closed")
    except Exception:  # noqa: BLE001
        log.exception("live socket failure")
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass
