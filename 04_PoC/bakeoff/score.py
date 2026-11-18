"""Compare a model's extracted card with the answer key, field by field.

Only fields that are filled in the answer key OR in the model output are scored, so
empty columns don't inflate accuracy. Hard-to-read cells marked in the answer key with
an "accept" list count as correct for any accepted reading.
"""
from __future__ import annotations

from common import HEADER_FIELDS, NUMERIC_FIELDS, ROW_FIELDS, complete_card, is_blank, same
from validate import flag_names


def _accept_map(key_card: dict) -> dict[str, list[str]]:
    return {c["field"]: c["accept"] for c in key_card.get("corrections", []) if c.get("accept")}


def score_card(key_card: dict, got_card: dict | None, md: dict) -> dict:
    key = complete_card(key_card)
    got = complete_card(got_card or {})
    accept = _accept_map(key_card)
    fields = []  # (path, field, expected, got, correct)

    def cmp(path, field, exp, val):
        if is_blank(field, exp) and is_blank(field, val):
            return
        ok = any(same(field, a, val) for a in accept.get(path, [exp]))
        fields.append({"path": path, "field": field, "expected": exp, "got": val, "correct": ok})

    for f in HEADER_FIELDS:
        cmp(f"header.{f}", f, key["header"][f], got["header"][f])
    for i in range(max(len(key["rows"]), len(got["rows"]))):
        kr = key["rows"][i] if i < len(key["rows"]) else {k: "" for k in ROW_FIELDS}
        gr = got["rows"][i] if i < len(got["rows"]) else {k: "" for k in ROW_FIELDS}
        for f in ROW_FIELDS:
            cmp(f"rows[{i}].{f}", f, kr[f], gr[f])
    cmp("total_hours", "total_hours", key["total_hours"], got["total_hours"])

    exp_flags = set(key_card.get("expected_flags", []))
    all_flags = flag_names(got_card, md) if got_card else {"no_rows"}
    # The reader's own "unclear" marks send a card to review but are not rule flags,
    # so they don't count against "flags exact".
    got_flags = all_flags - {"unclear_cell"}
    n = len(fields)
    correct = sum(f["correct"] for f in fields)
    num = [f for f in fields if f["field"] in NUMERIC_FIELDS]
    return {
        "card_id": key_card["card_id"],
        "fields": fields,
        "n_fields": n,
        "n_correct": correct,
        "accuracy": correct / n if n else 0.0,
        "numeric_accuracy": sum(f["correct"] for f in num) / len(num) if num else 0.0,
        "rows_expected": len(key["rows"]),
        "rows_got": len(got["rows"]),
        "perfect": n > 0 and correct == n,
        "expected_flags": sorted(exp_flags),
        "got_flags": sorted(got_flags),
        "flags_match": exp_flags == got_flags,
        "should_review": bool(exp_flags),
        "sent_to_review": bool(all_flags),
        "marked_unclear": "unclear_cell" in all_flags,
    }


def summarise(model: str, card_scores: list[dict], seconds: list[float], errors: int) -> dict:
    n = sum(c["n_fields"] for c in card_scores)
    ok = sum(c["n_correct"] for c in card_scores)
    num_f = [f for c in card_scores for f in c["fields"] if f["field"] in NUMERIC_FIELDS]
    # The dangerous miss: ANY card that is auto-saved (no flag at all) while a value is wrong.
    # This includes clean cards (no expected flags) - e.g. a plausible misread like 150 -> 180
    # that balances, so no rule fires. An earlier version only counted cards that were
    # expected to raise flags, which hid exactly these errors.
    # (Reading an unclear cell the 'intended' way, e.g. 10813 on C04, is correct, not a miss.)
    missed = sum(not c["sent_to_review"] and not c["perfect"] for c in card_scores)
    return {
        "model": model,
        "cards": len(card_scores),
        "errors": errors,
        "field_accuracy": ok / n if n else 0.0,
        "numeric_accuracy": sum(f["correct"] for f in num_f) / len(num_f) if num_f else 0.0,
        "perfect_cards": sum(c["perfect"] for c in card_scores),
        "row_count_ok": sum(c["rows_expected"] == c["rows_got"] for c in card_scores),
        "flags_exact": sum(c["flags_match"] for c in card_scores),
        "sent_to_review": sum(c["sent_to_review"] for c in card_scores),
        "marked_unclear": sum(c["marked_unclear"] for c in card_scores),
        "missed_reviews": missed,
        "avg_seconds": sum(seconds) / len(seconds) if seconds else 0.0,
    }
