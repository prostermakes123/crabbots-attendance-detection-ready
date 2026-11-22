"""Member management and instant enrolment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from ..db import database as db
from ..services import images as image_utils
from ..services import members as members_service
from . import enrollment as enrollment_service
from .deps import pipeline_or_503, require_admin
from ..services.pipeline import RecognitionPipeline

router = APIRouter(prefix="/api/members", tags=["members"])


async def _read_upload(file: UploadFile, max_mb: float) -> bytes:
    name = (file.filename or "").lower()
    if name and "." in name:
        ext = "." + name.rsplit(".", 1)[-1]
        if ext not in image_utils.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Unsupported image format. Use JPG, PNG or WebP.")
    limit = int(max_mb * 1024 * 1024)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"Image exceeds the {max_mb:.0f} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("")
def list_members(q: str | None = Query(default=None, max_length=80)):
    members = members_service.list_members(q)
    return {"total": len(members), "items": members}


@router.get("/{member_id}")
def get_member(member_id: str):
    member = members_service.get_member(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")
    return member


@router.get("/{member_id}/thumbnail")
def get_thumbnail(member_id: str):
    path = members_service.thumbnail_path(member_id)
    if not path:
        raise HTTPException(status_code=404, detail="No thumbnail stored for this member.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.post("/preview")
async def preview(
    file: UploadFile = File(...),
    pipeline: RecognitionPipeline = Depends(pipeline_or_503),
):
    settings = db.get_settings()
    raw = await _read_upload(file, float(settings["max_upload_mb"]))
    try:
        image = image_utils.decode_image_bytes(raw, max_mb=float(settings["max_upload_mb"]))
        report = enrollment_service.analyze(pipeline, image)
        return report
    except image_utils.ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except enrollment_service.EnrollmentError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": exc.code, "message": exc.message, **exc.details},
        )


@router.post("", status_code=201)
async def create_member(
    name: str = Form(...),
    consent: bool = Form(False),
    file: UploadFile = File(...),
    force_duplicate: bool = Form(False),
    force_duplicate_name: bool = Form(False),
    is_demo: bool = Form(False),
    notes: str | None = Form(None),
    pipeline: RecognitionPipeline = Depends(pipeline_or_503),
):
    settings = db.get_settings()
    raw = await _read_upload(file, float(settings["max_upload_mb"]))
    try:
        image = image_utils.decode_image_bytes(raw, max_mb=float(settings["max_upload_mb"]))
        return enrollment_service.enroll(
            pipeline,
            image,
            name=name,
            consent=consent,
            is_demo=is_demo,
            force_duplicate=force_duplicate,
            force_duplicate_name=force_duplicate_name,
            notes=notes,
            actor=settings.get("operator_name"),
        )
    except image_utils.ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except enrollment_service.EnrollmentError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": exc.code, "message": exc.message, **exc.details},
        )


@router.delete("/{member_id}")
def delete_member(
    member_id: str,
    purge_attendance: bool = Query(default=False),
    _: None = Depends(require_admin),
):
    settings = db.get_settings()
    deleted = members_service.delete_member(
        member_id, purge_attendance=purge_attendance, actor=settings.get("operator_name")
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Member not found.")
    return {"deleted": True, "member_id": member_id, "purged_attendance": purge_attendance}
