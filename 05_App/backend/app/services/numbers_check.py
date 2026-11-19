"""Every number in the answer text must come from the SQL rows (no numbers invented by the AI).

Allowed:
- any number found in a row cell (numbers, or digits inside strings such as "604021.05" or a date),
  also rounded to 0, 1 or 2 decimals ("61.47" may be written "61.5" or "61");
- numbers that appear in the question itself ("last 4 months");
- small counting numbers 1..min(rows, 10) ("the top 3 operators").

Name columns ("*_name", e.g. machine "Hydraulic press 100T") are text, not figures: their digits are
NOT allowed numbers, and the names themselves are removed from the answer before checking, so
"604021.05 (CNC case milling 1)" neither passes nor fails because of the "1" in the name.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

_NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[str]:
    out = []
    for m in _NUM.finditer(text or ""):
        tok = m.group(0).rstrip(",")
        # "1,234" is a thousands separator; "3, 4" was split by the regex already
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", tok):
            tok = tok.replace(",", "")
        elif "," in tok:
            out.extend(p for p in tok.split(",") if p and p != "-")
            continue
        out.append(tok)
    return out


def _variants(v: float) -> set[float]:
    return {round(v, 6), round(v, 2), round(v, 1), float(round(v))}


def _name_cols(columns: list | None) -> set[int]:
    return {i for i, c in enumerate(columns or []) if str(c).endswith("_name")}


def allowed_numbers(rows: list, question: str = "", columns: list | None = None) -> set[float]:
    allowed: set[float] = set()
    skip = _name_cols(columns)
    for row in rows or []:
        for ci, cell in enumerate(row):
            if ci in skip or isinstance(cell, bool) or cell is None:
                continue
            if isinstance(cell, (int, float, Decimal)):
                allowed |= _variants(float(cell))
                continue
            if isinstance(cell, (date, datetime)):
                cell = cell.isoformat()
            for tok in numbers_in(str(cell)):
                allowed |= _variants(float(tok))
                # leading zeros: "07" in a date is also 7
    for tok in numbers_in(question):
        allowed.add(round(float(tok), 6))
    for i in range(1, min(len(rows or []), 10) + 1):
        allowed.add(float(i))
    return allowed


def check(text: str, rows: list, question: str = "", columns: list | None = None) -> tuple[bool, list[str]]:
    """(ok, numbers in text that are not backed by the rows). Pass `columns` so name columns are handled."""
    allowed = allowed_numbers(rows, question, columns)
    names = sorted({str(r[i]) for r in rows or [] for i in _name_cols(columns) if r[i]}, key=len, reverse=True)
    for name in names:
        text = (text or "").replace(name, " ")
    bad = []
    for tok in numbers_in(text):
        v = round(float(tok), 6)
        if v not in allowed and round(v, 2) not in allowed:
            bad.append(tok)
    return (not bad, bad)
