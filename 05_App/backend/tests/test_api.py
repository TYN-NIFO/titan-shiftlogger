"""API tests (LLM_MODE=stub): health, masters, upload -> read -> validate, review edits, approve."""
from __future__ import annotations

from sqlalchemy import select

ROW_KEYS = {"emp_no", "shift", "opn_code", "wo_no", "comp_code", "qty_prod", "qty_accp", "rej_code", "rej_qty",
            "rework_code", "rework_qty", "time_from", "time_to", "total_hours", "unclear"}
CARD_KEYS = {"id", "card_ref", "source", "status", "image_url", "read_seconds", "error", "header", "rows",
             "total_hours", "flags"}


def _upload(client, photo, ref: str) -> dict:
    r = client.post("/api/cards", files=photo(ref))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "processing" and isinstance(body["id"], int)
    # TestClient runs the background task before returning, so the card is read by now.
    card = client.get(f"/api/cards/{body['id']}").json()
    assert set(card) == CARD_KEYS
    return card


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    h = r.json()
    assert set(h) == {"ok", "db", "llm_mode", "ollama_reachable", "read_model", "chat_model"}
    assert h["db"] is True and h["llm_mode"] == "stub" and h["ollama_reachable"] is False
    assert h["ok"] is True


def test_masters(client):
    m = client.get("/api/masters").json()
    assert set(m) == {"employees", "machines", "components", "idle_codes", "production_codes",
                      "rework_codes", "rejection_codes"}
    assert "280419" in m["employees"] and "999999" not in m["employees"]
    assert {"mc_no": "604021.05", "machine_type": "CNC"} in m["machines"]
    assert m["idle_codes"]["10813"] == "Absenteeism"
    assert "10202" in m["production_codes"]
    assert "001" in m["rework_codes"] and "008" in m["rejection_codes"]
    assert all("comp_code" in c for c in m["components"])


def test_upload_c04_needs_review_with_suggestion(client, photo):
    card = _upload(client, photo, "C04")
    assert card["card_ref"] == "C04" and card["source"] == "photo"
    assert card["status"] == "needs_review"
    assert card["image_url"] == f"/api/cards/{card['id']}/image"
    assert set(card["rows"][0]) == ROW_KEYS
    assert card["rows"][0]["opn_code"] == "10613"
    flag = next(f for f in card["flags"] if f["flag"] == "invalid_code")
    assert flag["where"] == "rows[0].opn_code"
    assert flag["suggestion"] == "10813"
    assert flag["text"] == "Opn/Idle code is not on the code sheet"

    img = client.get(card["image_url"])
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"


def test_upload_c02_saved(client, photo):
    card = _upload(client, photo, "C02")
    assert card["status"] == "approved"
    assert card["flags"] == []
    assert card["total_hours"] == "8.00"


def test_upload_rejects_non_image(client):
    r = client.post("/api/cards", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and "detail" in r.json()


def test_unknown_card_404(client):
    r = client.get("/api/cards/999999")
    assert r.status_code == 404 and r.json() == {"detail": "Job card not found"}


def test_review_fix_and_approve(client, photo, database):
    from app.db.models import CardRow, ReviewLog
    from app.db.session import SessionLocal

    card = _upload(client, photo, "C04")
    cid = card["id"]
    rows = card["rows"]
    rows[0]["opn_code"] = "10813"                     # the supervisor clicks "Use 10813"
    r = client.put(f"/api/cards/{cid}", json={"header": card["header"], "rows": rows,
                                              "total_hours": card["total_hours"]})
    assert r.status_code == 200, r.text
    fixed = r.json()
    assert fixed["rows"][0]["opn_code"] == "10813"
    assert not [f for f in fixed["flags"] if f["flag"] == "invalid_code"]
    assert fixed["status"] == "needs_review"          # still waits for Approve

    with SessionLocal() as db:
        logs = db.scalars(select(ReviewLog).where(ReviewLog.card_id == cid)).all()
        assert [(l.action, l.field, l.old_value, l.new_value) for l in logs] == \
            [("edit", "rows[0].opn_code", "10613", "10813")]
        crow = db.scalars(select(CardRow).where(CardRow.card_id == cid)).one()
        assert crow.opn_code == "10813" and crow.minutes == 480 and crow.emp_no == "280419"

    r = client.post(f"/api/cards/{cid}/approve", json={"by": "supervisor"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    with SessionLocal() as db:
        actions = [l.action for l in db.scalars(select(ReviewLog).where(ReviewLog.card_id == cid))]
        assert actions == ["edit", "approve"]

    listed = client.get("/api/cards", params={"source": "photo"}).json()
    item = next(c for c in listed if c["id"] == cid)
    assert set(item) == {"id", "card_ref", "source", "card_date", "mc_no", "emp_no", "status",
                         "flag_count", "created_at"}
    assert item["status"] == "approved" and item["card_date"] == "2026-11-11" and item["mc_no"] == "604020.08"
    assert item["flag_count"] == 0


def test_list_filters_and_order(client, photo):
    _upload(client, photo, "C08")
    review = client.get("/api/cards", params={"status": "needs_review"}).json()
    assert review and all(c["status"] == "needs_review" for c in review)
    newest = client.get("/api/cards", params={"limit": 1}).json()
    assert len(newest) == 1 and newest[0]["card_ref"] == "C08"
    c08 = client.get(f"/api/cards/{newest[0]['id']}").json()
    assert {f["flag"] for f in c08["flags"]} == {"accp_gt_prod", "qty_balance", "row_hours_mismatch",
                                                   "shift_hours_not_8"}


def test_stub_unknown_card_fails_cleanly(client):
    from tests.conftest import PHOTOS
    r = client.post("/api/cards", files={"file": ("X99_front.jpeg", (PHOTOS / "C01_front.jpeg").read_bytes(),
                                                  "image/jpeg")})
    card = client.get(f"/api/cards/{r.json()['id']}").json()
    assert card["status"] == "failed" and card["error"]


def test_live_read_with_ollama_down_fails_cleanly(client, photo, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")          # OLLAMA_HOST points at a closed port in tests
    monkeypatch.setenv("LLM_TIMEOUT", "3")
    r = client.post("/api/cards", files=photo("C10"))
    card = client.get(f"/api/cards/{r.json()['id']}").json()
    assert card["status"] == "failed" and card["error"].startswith("The card could not be read")
    assert client.get("/api/health").json()["llm_mode"] == "live"
