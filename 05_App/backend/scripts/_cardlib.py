"""Shared helpers for the data scripts: paths, engine, and card -> database rows.

A card here is the reading shape used everywhere (answer key, extractor, review screen):
    {"header": {date, component_description, cc, operation_description, mc_no},
     "rows": [{14 fields as written}], "total_hours": "8.00"}
All values are strings as written. `card_columns()` / `row_columns()` give the
normalised typed columns for `job_cards` / `card_rows`.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]          # 05_App/backend
REPO = BACKEND.parents[1]                              # TITAN (repo root)
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.reading.common import (  # noqa: E402
    ROW_FIELDS, clock_minutes, complete_card, duration_minutes, norm_code, norm_date,
    norm_int, norm_letters, norm_mc, norm_short_code, s,
)

SQL_DIR = BACKEND / "app" / "db" / "sql"


def upload_dir() -> Path:
    """UPLOAD_DIR from the env (session.py loads 05_App/.env), relative to the repo root."""
    import app.db.session  # noqa: F401  (loads .env into os.environ)
    p = Path(os.environ.get("UPLOAD_DIR", "05_App/backend/storage/cards"))
    return p if p.is_absolute() else REPO / p


def repo_relative(p: Path) -> str:
    """Stored image paths are repo-relative (posix), like the backend's uploads."""
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(p)


def parse_card_date(v) -> date | None:
    d = norm_date(v)
    if d is None:
        return None
    try:
        return date(2000 + d[2], d[1], d[0])
    except ValueError:
        return None


def match_machine(mc: str, md: dict) -> str | None:
    """Machine as matched against the master list (60402008 -> 604020.08); else the normalised text."""
    if not s(mc):
        return None
    n = norm_mc(mc)
    if n in md["machines"]:
        return n
    digits = n.replace(".", "")
    for m in md["machines"]:
        if m.replace(".", "") == digits:
            return m
    return n or None


def _str_or_none(v) -> str | None:
    v = s(v)
    return v or None


def row_minutes(r: dict) -> int | None:
    """Paid minutes of a row: the written Total Hours; else the From-To span (minus the 30-min
    break when the span is longer than a shift's 8 paid hours). Same rule as app/services/cards.py."""
    m = duration_minutes(r.get("total_hours"))
    if m is not None:
        return m
    a, b = clock_minutes(r.get("time_from"), r.get("shift")), clock_minutes(r.get("time_to"), r.get("shift"))
    if a is None or b is None or b <= a:
        return None
    return (b - a) - 30 if b - a > 8 * 60 else b - a


def row_columns(r: dict, row_no: int, unclear: list | None = None) -> dict:
    """One row as written -> card_rows columns (raw JSON + normalised values)."""
    raw = {k: s(r.get(k)) for k in ROW_FIELDS}
    raw["unclear"] = list(unclear or r.get("unclear") or [])
    emp = norm_int(raw["emp_no"])
    comp = norm_int(raw["comp_code"])
    return {
        "row_no": row_no,
        "raw": raw,
        "emp_no": str(emp) if emp is not None else None,
        "shift": norm_letters(raw["shift"]) or None,
        "opn_code": norm_code(raw["opn_code"]) or None,
        "wo_no": _str_or_none(raw["wo_no"]),
        "comp_code": str(comp) if comp is not None else None,
        "qty_prod": norm_int(raw["qty_prod"]),
        "qty_accp": norm_int(raw["qty_accp"]),
        "rej_code": norm_short_code(raw["rej_code"]) or None,
        "rej_qty": norm_int(raw["rej_qty"]),
        "rework_code": norm_short_code(raw["rework_code"]) or None,
        "rework_qty": norm_int(raw["rework_qty"]),
        "time_from": _str_or_none(raw["time_from"]),
        "time_to": _str_or_none(raw["time_to"]),
        "minutes": row_minutes(raw),
    }


def card_columns(card: dict, md: dict) -> dict:
    """Card-level job_cards columns derived from the reading."""
    c = complete_card(card)
    first = c["rows"][0] if c["rows"] else {}
    emp = norm_int(first.get("emp_no"))
    return {
        "header": c["header"],
        "total_hours": c["total_hours"] or None,
        "card_date": parse_card_date(c["header"]["date"]),
        "mc_no": match_machine(c["header"]["mc_no"], md),
        "emp_no": str(emp) if emp is not None else None,
        "shift": norm_letters(first.get("shift")) or None,
    }


def run_sql_file(conn, name: str) -> None:
    """Run one .sql file (several statements) on a SQLAlchemy connection, no parameter parsing."""
    conn.exec_driver_sql((SQL_DIR / name).read_text(encoding="utf-8"))
