"""Shared helpers: paths, loading, and value normalisation for job-card fields.

Job cards use a 12-hour clock written as h.mm ("2.30" = 2 h 30 m or 2:30 pm),
ditto marks, leading zeros on codes ("008") and mixed date formats
("10/11/26", "12/11/2026"). Everything is normalised here so the scorer and the
validation rules compare like with like.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PROMPTS = HERE / "prompts"
PHOTOS = HERE.parent / "Synthetic_Job_Cards" / "Photos"

ROW_FIELDS = [
    "emp_no", "shift", "opn_code", "wo_no", "comp_code", "qty_prod", "qty_accp",
    "rej_code", "rej_qty", "rework_code", "rework_qty", "time_from", "time_to", "total_hours",
]
HEADER_FIELDS = ["date", "component_description", "cc", "operation_description", "mc_no"]

# Fields that hold digits / codes / times (the ones the chatbot's numbers depend on).
NUMERIC_FIELDS = {
    "emp_no", "opn_code", "comp_code", "qty_prod", "qty_accp", "rej_code", "rej_qty",
    "rework_code", "rework_qty", "time_from", "time_to", "total_hours", "date", "mc_no", "cc",
}


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def master_data() -> dict:
    return load_json(DATA / "master_data.json")


def answer_key() -> dict:
    return load_json(DATA / "answer_key.json")


def s(v) -> str:
    """Any value -> stripped string ('' for None)."""
    if v is None:
        return ""
    return str(v).strip()


def blank_row() -> dict:
    return {k: "" for k in ROW_FIELDS}


def complete_card(card: dict) -> dict:
    """Fill missing header/row keys with '' so every card has the same shape."""
    header = {k: s(card.get("header", {}).get(k)) for k in HEADER_FIELDS}
    rows = []
    for r in card.get("rows", []) or []:
        row = blank_row()
        for k in ROW_FIELDS:
            row[k] = s(r.get(k))
        rows.append(row)
    return {"header": header, "rows": rows, "total_hours": s(card.get("total_hours"))}


# ---------------------------------------------------------------- normalisers

def norm_time(v) -> tuple[int, int] | None:
    """'6.00', '6:00', '06.00', '6', '2,30', '8 =' -> (h, m). None if blank/unreadable."""
    t = s(v).replace(",", ".").replace(":", ".").replace("-", ".").replace(" ", "")
    t = t.rstrip(".=")
    if not t:
        return None
    m = re.fullmatch(r"(\d{1,2})(?:\.(\d{1,2}))?", t)
    if not m:
        return None
    h = int(m.group(1))
    mm = m.group(2) or "0"
    mins = int(mm) * 10 if len(mm) == 1 else int(mm)  # "3.3" -> 3 h 30 m
    return h, mins


def norm_date(v) -> tuple[int, int, int] | None:
    t = re.sub(r"[^\d/.\-]", "", s(v))
    parts = [p for p in re.split(r"[/.\-]", t) if p]
    if len(parts) != 3:
        return None
    d, m, y = (int(p) for p in parts)
    return d, m, y % 100


def norm_int(v) -> int | None:
    t = re.sub(r"[^\d]", "", s(v))
    return int(t) if t else None


def norm_code(v) -> str:
    """Opn/idle codes keep a letter prefix (S10202); rej/rework codes compare as 3 digits."""
    return re.sub(r"[^0-9A-Za-z]", "", s(v)).upper()


def norm_short_code(v) -> str:
    t = re.sub(r"[^\d]", "", s(v))
    return t.zfill(3) if t else ""


def norm_text(v) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s(v).lower())).strip()


def norm_letters(v) -> str:
    return re.sub(r"[^A-Z]", "", s(v).upper())


def norm_cc(v) -> tuple[str, ...]:
    return tuple(sorted(re.findall(r"\d+", s(v))))


def norm_mc(v) -> str:
    return re.sub(r"[^\d.]", "", s(v)).strip(".")


NORMALISERS = {
    "date": norm_date,
    "component_description": norm_text,
    "cc": norm_cc,
    "operation_description": norm_letters,
    "mc_no": norm_mc,
    "emp_no": norm_int,
    "shift": norm_letters,
    "opn_code": norm_code,
    "wo_no": norm_code,
    "comp_code": norm_int,
    "qty_prod": norm_int,
    "qty_accp": norm_int,
    "rej_code": norm_short_code,
    "rej_qty": norm_int,
    "rework_code": norm_short_code,
    "rework_qty": norm_int,
    "time_from": norm_time,
    "time_to": norm_time,
    "total_hours": norm_time,
}


def same(field: str, a, b) -> bool:
    f = NORMALISERS.get(field, norm_text)
    return f(a) == f(b)


def is_blank(field: str, v) -> bool:
    f = NORMALISERS.get(field, norm_text)
    return f(v) in (None, "", ())


def duration_minutes(v) -> int | None:
    t = norm_time(v)
    return None if t is None else t[0] * 60 + t[1]


def clock_minutes(v, shift: str) -> int | None:
    """Card clock time -> minutes after midnight, using the shift to resolve am/pm.

    Shift A runs 6.00 am to 2.30 pm, so hours below 6 are pm.
    Shift B runs 2.30 pm to 11.00 pm, so every hour below 12 is pm.
    """
    t = norm_time(v)
    if t is None:
        return None
    h, m = t
    sh = norm_letters(shift)
    if sh == "A" and h < 6:
        h += 12
    elif sh == "B" and h < 12:
        h += 12
    return h * 60 + m
