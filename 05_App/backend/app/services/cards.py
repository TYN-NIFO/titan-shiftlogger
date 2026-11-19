"""Job-card storage: create, read (background), edit, approve, and the Card JSON shape."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reading.common import (
    HEADER_FIELDS, ROW_FIELDS, duration_minutes, clock_minutes, master_data, norm_code, norm_date,
    norm_int, norm_letters, norm_mc, norm_short_code, s,
)
from app.core.reading.validate import FLAG_TEXT, nearest_machine, validate
from app.db.models import CardRow, JobCard, ReviewLog
from app.db.session import SessionLocal
from app.services import config
from app.services.reading_service import read_card, shape_card

log = logging.getLogger("titan.cards")

ALLOWED_EXT = {".jpg", ".jpeg", ".png"}


# ------------------------------------------------------------------ helpers

def card_ref_from_filename(name: str) -> str:
    stem = Path(name or "card").stem
    ref = stem.split("_", 1)[0].strip() or stem
    return re.sub(r"[^\w\-]", "", ref)[:40] or "CARD"


def _parse_date(v: str) -> date | None:
    d = norm_date(v)
    if not d:
        return None
    day, month, yy = d
    try:
        return date(2000 + yy, month, day)
    except ValueError:
        return None


def _str_or_none(v, n: int) -> str | None:
    v = s(v)
    return v[:n] if v else None


def _row_minutes(r: dict, md: dict) -> int | None:
    """Paid minutes of a row: the written Total Hours; else the From-To span (minus the break
    when the span covers a whole shift)."""
    total = duration_minutes(r.get("total_hours"))
    if total is not None:
        return total
    a, b = clock_minutes(r.get("time_from"), r.get("shift")), clock_minutes(r.get("time_to"), r.get("shift"))
    if a is None or b is None or b <= a:
        return None
    span = b - a
    brk = md["shifts"].get(s(r.get("shift")).upper(), {}).get("break_minutes", 30)
    return span - brk if span > 8 * 60 else span


def _machine(header_mc: str, md: dict) -> str | None:
    if not s(header_mc):
        return None
    n = norm_mc(header_mc)
    if n in md["machines"]:
        return n
    match = nearest_machine(header_mc, md)            # 60402008 -> 604020.08
    return (match or n or s(header_mc))[:16]


def build_card_rows(rows: list[dict], md: dict) -> list[CardRow]:
    out = []
    for i, r in enumerate(rows, start=1):
        comp = norm_int(r.get("comp_code"))
        out.append(CardRow(
            row_no=i,
            raw={**{k: s(r.get(k)) for k in ROW_FIELDS}, "unclear": list(r.get("unclear") or [])},
            emp_no=(str(norm_int(r.get("emp_no"))) if norm_int(r.get("emp_no")) is not None else None),
            shift=(norm_letters(r.get("shift"))[:2] or None),
            opn_code=(norm_code(r.get("opn_code"))[:12] or None),
            wo_no=_str_or_none(r.get("wo_no"), 30),
            comp_code=(str(comp)[:12] if comp is not None else None),
            qty_prod=norm_int(r.get("qty_prod")),
            qty_accp=norm_int(r.get("qty_accp")),
            rej_code=(norm_short_code(r.get("rej_code"))[:6] or None),
            rej_qty=norm_int(r.get("rej_qty")),
            rework_code=(norm_short_code(r.get("rework_code"))[:6] or None),
            rework_qty=norm_int(r.get("rework_qty")),
            time_from=_str_or_none(r.get("time_from"), 8),
            time_to=_str_or_none(r.get("time_to"), 8),
            minutes=_row_minutes(r, md),
        ))
    return out


def apply_card_values(card: JobCard, values: dict, md: dict | None = None) -> None:
    """Write header/rows/total_hours (strings, as written), re-validate and rebuild card_rows."""
    md = md or master_data()
    values = shape_card(values)
    card.header = values["header"]
    card.total_hours = values["total_hours"]
    flags = validate(values, md)
    for f in flags:
        f["text"] = FLAG_TEXT.get(f["flag"], f["flag"])
    card.flags = flags
    card.card_date = _parse_date(values["header"]["date"])
    card.mc_no = _machine(values["header"]["mc_no"], md)
    first = next((r for r in values["rows"] if norm_int(r["emp_no"]) is not None), None)
    card.emp_no = str(norm_int(first["emp_no"])) if first else None
    sh = next((norm_letters(r["shift"]) for r in values["rows"] if norm_letters(r["shift"])), "")
    card.shift = sh[:2] or None
    card.rows.clear()
    card.rows.extend(build_card_rows(values["rows"], md))


# ------------------------------------------------------------------ JSON shapes

def card_json(card: JobCard) -> dict:
    header = {k: s((card.header or {}).get(k)) for k in HEADER_FIELDS}
    rows = []
    for r in sorted(card.rows, key=lambda x: x.row_no):
        raw = r.raw or {}
        row = {k: s(raw.get(k)) for k in ROW_FIELDS}
        row["unclear"] = list(raw.get("unclear") or [])
        rows.append(row)
    flags = []
    for f in card.flags or []:
        flags.append({"flag": f.get("flag"), "text": f.get("text") or FLAG_TEXT.get(f.get("flag"), ""),
                      "where": f.get("where") or "", "detail": f.get("detail") or "",
                      "suggestion": f.get("suggestion")})
    return {
        "id": card.id, "card_ref": card.card_ref, "source": card.source, "status": card.status,
        "image_url": f"/api/cards/{card.id}/image" if card.image_path else None,
        "read_seconds": card.read_seconds, "error": card.error,
        "header": header, "rows": rows, "total_hours": s(card.total_hours), "flags": flags,
    }


def card_list_item(card: JobCard) -> dict:
    return {
        "id": card.id, "card_ref": card.card_ref, "source": card.source,
        "card_date": card.card_date.isoformat() if card.card_date else None,
        "mc_no": card.mc_no, "emp_no": card.emp_no, "status": card.status,
        "flag_count": len(card.flags or []),
        "created_at": card.created_at.isoformat() if card.created_at else None,
    }


# ------------------------------------------------------------------ operations

def list_cards(db: Session, status: str | None, source: str | None, limit: int) -> list[dict]:
    q = select(JobCard)
    if status:
        q = q.where(JobCard.status == status)
    if source:
        q = q.where(JobCard.source == source)
    q = q.order_by(JobCard.created_at.desc(), JobCard.id.desc()).limit(max(1, min(limit, 500)))
    return [card_list_item(c) for c in db.scalars(q)]


def create_upload(db: Session, filename: str, content: bytes) -> JobCard:
    ext = Path(filename or "").suffix.lower()
    ref = card_ref_from_filename(filename)
    dest = config.upload_dir() / f"{datetime.now():%Y%m%d-%H%M%S}_{uuid.uuid4().hex[:6]}_{ref}{ext}"
    dest.write_bytes(content)
    try:
        stored = dest.relative_to(config.REPO_ROOT).as_posix()
    except ValueError:
        stored = str(dest)
    card = JobCard(card_ref=ref, source="photo", status="processing", image_path=stored,
                   header={}, flags=[])
    db.add(card)
    db.commit()
    return card


def process_card(card_id: int) -> None:
    """Background task: read -> validate -> write rows -> needs_review | approved (or failed)."""
    with SessionLocal() as db:
        card = db.get(JobCard, card_id)
        if card is None:
            return
        try:
            image = config.resolve_image(card.image_path)
            if image is None:
                raise FileNotFoundError("The uploaded image file is missing.")
            res = read_card(image, card.card_ref)
            card.extracted = res["extracted"]
            card.read_model = res["model"]
            card.read_seconds = res["seconds"]
            apply_card_values(card, res["card"])
            if card.flags:
                card.status = "needs_review"
            else:
                card.status = "approved"
                card.approved_at = datetime.now(timezone.utc)
                card.approved_by = "auto (no flags)"
            card.error = None
            db.commit()
        except Exception as e:  # noqa: BLE001 - the card must end in a final state
            log.exception("reading card %s failed", card_id)
            db.rollback()
            card = db.get(JobCard, card_id)
            card.status = "failed"
            card.error = f"The card could not be read: {e}"[:2000]
            db.commit()


def _diff(old: dict, new: dict) -> list[tuple[str, str, str]]:
    """(field path, old, new) for every changed value."""
    out = []
    for k in HEADER_FIELDS:
        a, b = s(old["header"].get(k)), s(new["header"].get(k))
        if a != b:
            out.append((f"header.{k}", a, b))
    n = max(len(old["rows"]), len(new["rows"]))
    for i in range(n):
        ro = old["rows"][i] if i < len(old["rows"]) else None
        rn = new["rows"][i] if i < len(new["rows"]) else None
        if rn is None:
            out.append((f"rows[{i}]", "row", "(deleted)"))
            continue
        for k in ROW_FIELDS:
            a, b = s((ro or {}).get(k)), s(rn.get(k))
            if a != b:
                out.append((f"rows[{i}].{k}", a, b))
    if s(old["total_hours"]) != s(new["total_hours"]):
        out.append(("total_hours", s(old["total_hours"]), s(new["total_hours"])))
    return out


def update_card(db: Session, card: JobCard, payload: dict, by: str = "supervisor") -> JobCard:
    old = card_json(card)
    new = shape_card(payload)
    changes = _diff(old, new)
    # A cell the supervisor has corrected is no longer "unclear".
    changed = {f for f, _, _ in changes}
    for i, r in enumerate(new["rows"]):
        r["unclear"] = [u for u in r["unclear"] if f"rows[{i}].{u}" not in changed and u not in changed]
    for f, a, b in changes:
        db.add(ReviewLog(card_id=card.id, action="edit", field=f[:60], old_value=a, new_value=b, by=by))
    apply_card_values(card, new)
    if card.status in ("failed", "processing"):
        card.status = "needs_review"
        card.error = None
    db.commit()
    db.refresh(card)
    return card


def approve_card(db: Session, card: JobCard, by: str = "supervisor") -> JobCard:
    card.status = "approved"
    card.approved_at = datetime.now(timezone.utc)
    card.approved_by = (by or "supervisor")[:60]
    remaining = ", ".join(sorted({f.get("flag", "") for f in card.flags or []}))
    db.add(ReviewLog(card_id=card.id, action="approve", field=None, old_value=None,
                     new_value=f"approved with flags: {remaining}" if remaining else "approved",
                     by=card.approved_by))
    db.commit()
    db.refresh(card)
    return card


def fail_stale_processing() -> int:
    """At startup: cards left 'processing' by a restart will never finish; mark them failed."""
    with SessionLocal() as db:
        cards = db.scalars(select(JobCard).where(JobCard.status == "processing")).all()
        for c in cards:
            c.status = "failed"
            c.error = "Reading was interrupted (server restarted). Please upload the card again."
        db.commit()
        return len(cards)
