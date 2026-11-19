"""Card reading: wraps core/reading/extract.py (live) or the answer key (stub, tests only)."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from app.core.reading import extract as ex
from app.core.reading.common import HEADER_FIELDS, ROW_FIELDS, answer_key, s
from app.services import config

# One read at a time on the GPU: parallel reads only slow each other down.
_gpu_lock = threading.Lock()


class ReadError(RuntimeError):
    pass


def shape_card(card: dict) -> dict:
    """Any reading -> {header, rows (14 fields + unclear), total_hours}, all strings."""
    hdr = card.get("header") or {}
    header = {k: s(hdr.get(k)) for k in HEADER_FIELDS}
    rows = []
    for r in card.get("rows") or []:
        if not isinstance(r, dict):
            continue
        row = {k: s(r.get(k)) for k in ROW_FIELDS}
        row["unclear"] = [s(u) for u in (r.get("unclear") or []) if s(u)]
        rows.append(row)
    return {"header": header, "rows": rows, "total_hours": s(card.get("total_hours"))}


def read_card(image: Path, card_ref: str) -> dict:
    """Returns {card, extracted, model, seconds}. Raises ReadError on failure."""
    if config.llm_mode() == "stub":
        t0 = time.perf_counter()
        for c in answer_key()["cards"]:
            if c["card_id"].upper() == card_ref.upper():
                card = {"header": c["header"], "rows": c["rows"], "total_hours": c["total_hours"]}
                return {"card": shape_card(card), "extracted": card, "model": "stub",
                        "seconds": round(time.perf_counter() - t0, 2)}
        raise ReadError(f"Stub mode has no canned reading for '{card_ref}' (only C01-C10).")

    model = config.read_model()
    with _gpu_lock:
        r = ex.extract(model, image, host=config.ollama_host(), timeout=config.llm_timeout())
    if r["error"] or not isinstance(r["card"], dict):
        raise ReadError(r["error"] or "The AI returned no readable card.")
    return {"card": shape_card(r["card"]), "extracted": r["card"], "model": model,
            "seconds": round(r["seconds"], 1)}
