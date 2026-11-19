from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine
from app.services import config, llm

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    mode = config.llm_mode()
    reachable = llm.ollama_reachable(timeout=1.5)
    return {"ok": db_ok and (mode == "stub" or reachable), "db": db_ok, "llm_mode": mode,
            "ollama_reachable": reachable, "read_model": config.read_model(),
            "chat_model": config.chat_model()}
