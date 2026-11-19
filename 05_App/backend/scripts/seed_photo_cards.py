"""Seed the demo state: 7 of the 10 synthetic photo cards, as written on the photos (answer key).

    cd 05_App/backend
    .venv/Scripts/python.exe scripts/seed_photo_cards.py

Seeds C01, C03, C05, C06, C07, C09, C10 with source='photo', flags from validate(), status
'needs_review' if flagged else 'approved', and the photo copied into UPLOAD_DIR.
C02, C04 and C08 are NOT seeded: they are uploaded live in the demo video.
Re-runnable: earlier seeded copies of these cards are replaced.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone

import _cardlib  # noqa: F401  (puts the backend on sys.path)
from _cardlib import card_columns, repo_relative, row_columns, upload_dir
from sqlalchemy import delete, select

from app.core.reading.common import PHOTOS, answer_key, complete_card, master_data
from app.core.reading.validate import FLAG_TEXT, validate
from app.db.models import CardRow, JobCard
from app.db.session import SessionLocal

SEED = ["C01", "C03", "C05", "C06", "C07", "C09", "C10"]


def seed() -> list[tuple[str, str, list[str]]]:
    md = master_data()
    cards = {c["card_id"]: c for c in answer_key()["cards"]}
    dest_dir = upload_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    with SessionLocal() as s, s.begin():
        s.execute(delete(JobCard).where(JobCard.source == "photo", JobCard.card_ref.in_(SEED)))
        for ref in SEED:
            c = cards[ref]
            reading = complete_card(c)
            flags = [{**f, "text": FLAG_TEXT[f["flag"]]} for f in validate(c, md)]
            status = "needs_review" if flags else "approved"
            dest = dest_dir / c["photo"]
            shutil.copyfile(PHOTOS / c["photo"], dest)
            card = JobCard(
                card_ref=ref, source="photo", status=status, image_path=repo_relative(dest),
                flags=flags, extracted=reading, read_model="answer key (seeded)", read_seconds=None,
                approved_at=datetime.now(timezone.utc) if status == "approved" else None,
                approved_by="auto" if status == "approved" else None,
                **card_columns(c, md))
            card.rows = [CardRow(**row_columns(r, i)) for i, r in enumerate(reading["rows"], start=1)]
            s.add(card)
            out.append((ref, status, [f["flag"] for f in flags]))
    return out


if __name__ == "__main__":
    for ref, status, flags in seed():
        print(f"  {ref}: {status:12s} {', '.join(flags) or '-'}")
    with SessionLocal() as s:
        n = len(s.execute(select(JobCard.id).where(JobCard.source == "photo")).all())
    print(f"Seeded photo cards ({n} in the database); images in {upload_dir()}")
