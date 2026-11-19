from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import JobCard
from app.db.session import get_session
from app.services import cards as svc
from app.services import config

router = APIRouter()
MAX_BYTES = 25 * 1024 * 1024


class CardEdit(BaseModel):
    header: dict = {}
    rows: list[dict] = []
    total_hours: str | None = ""


class ApproveBody(BaseModel):
    by: str | None = "supervisor"


def _get(db: Session, card_id: int) -> JobCard:
    card = db.get(JobCard, card_id)
    if card is None:
        raise HTTPException(404, "Job card not found")
    return card


@router.get("/api/cards")
def list_cards(status: str | None = None, source: str | None = None, limit: int = Query(50, ge=1, le=500),
               db: Session = Depends(get_session)) -> list[dict]:
    return svc.list_cards(db, status or None, source or None, limit)


@router.get("/api/cards/summary")
def cards_summary(db: Session = Depends(get_session)) -> dict:
    """Counts for the KPI strip: how many cards saved automatically vs held for the supervisor."""
    from sqlalchemy import func, select
    rows = db.execute(select(JobCard.status, func.count()).group_by(JobCard.status)).all()
    by = {s: n for s, n in rows}
    photo = dict(db.execute(select(JobCard.status, func.count()).where(JobCard.source == "photo")
                            .group_by(JobCard.status)).all())
    auto = db.scalar(select(func.count()).select_from(JobCard).where(
        JobCard.source == "photo", JobCard.status == "approved", JobCard.approved_by.like("auto%"))) or 0
    return {"total": sum(by.values()), "approved": by.get("approved", 0),
            "needs_review": by.get("needs_review", 0), "failed": by.get("failed", 0),
            "processing": by.get("processing", 0),
            "photo_total": sum(photo.values()), "photo_auto_approved": auto}


@router.post("/api/cards")
async def upload_card(background: BackgroundTasks, file: UploadFile = File(...),
                      db: Session = Depends(get_session)) -> dict:
    name = file.filename or "card"
    ext = Path(name).suffix.lower()
    if ext not in svc.ALLOWED_EXT and file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(400, "Please upload a JPEG or PNG photo of the job card")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The file is empty")
    if len(content) > MAX_BYTES:
        raise HTTPException(400, "The photo is too large (max 25 MB)")
    if ext not in svc.ALLOWED_EXT:
        name = Path(name).stem + (".png" if file.content_type == "image/png" else ".jpg")
    card = svc.create_upload(db, name, content)
    background.add_task(svc.process_card, card.id)
    return {"id": card.id, "status": "processing"}


@router.get("/api/cards/{card_id}")
def get_card(card_id: int, db: Session = Depends(get_session)) -> dict:
    return svc.card_json(_get(db, card_id))


@router.get("/api/cards/{card_id}/image")
def card_image(card_id: int, db: Session = Depends(get_session)):
    path = config.resolve_image(_get(db, card_id).image_path)
    if path is None:
        raise HTTPException(404, "No image for this card")
    return FileResponse(path)


@router.put("/api/cards/{card_id}")
def edit_card(card_id: int, body: CardEdit, db: Session = Depends(get_session)) -> dict:
    card = _get(db, card_id)
    if card.status == "processing":
        raise HTTPException(409, "The card is still being read")
    card = svc.update_card(db, card, body.model_dump())
    return svc.card_json(card)


@router.post("/api/cards/{card_id}/approve")
def approve(card_id: int, body: ApproveBody | None = None, db: Session = Depends(get_session)) -> dict:
    card = _get(db, card_id)
    if card.status == "processing":
        raise HTTPException(409, "The card is still being read")
    card = svc.approve_card(db, card, (body.by if body else None) or "supervisor")
    return svc.card_json(card)
