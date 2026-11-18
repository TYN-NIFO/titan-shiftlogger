"""Validation rules for one extracted job card.

These are the checks from the technical approach: hours add up, accepted <= produced,
codes valid against the code sheet, employee and machine exist in master data,
no overlapping times. A card with any flag goes to the supervisor review screen;
a card with none is saved straight to the database.

    python validate.py              # run the rules over the answer key and show the flags
"""
from __future__ import annotations

from common import (
    answer_key, clock_minutes, complete_card, duration_minutes, is_blank, master_data,
    norm_code, norm_int, norm_mc, norm_short_code, s,
)

FLAG_TEXT = {
    "missing_date": "Date is missing or unreadable",
    "unknown_employee": "Emp No is not in the employee list",
    "unknown_machine": "M/C No is not in the machine list",
    "unknown_component": "Comp Code is not in the component list",
    "invalid_code": "Opn/Idle code is not on the code sheet",
    "invalid_rej_code": "Rejection code is not on the code sheet",
    "invalid_rework_code": "Rework code is not on the code sheet",
    "accp_gt_prod": "Qty accepted is more than qty produced",
    "qty_balance": "Qty produced does not equal accepted + rejected + rework",
    "row_hours_mismatch": "Row Total Hours does not match its From-To time",
    "time_overlap": "Two rows overlap in time",
    "shift_hours_not_8": "Shift hours do not add up to 8.00",
    "total_mismatch": "Written total does not equal the sum of the rows",
    "idle_row_has_qty": "An idle/breakdown row has a component or quantity",
    "unclear_cell": "The reader marked this cell as unclear",
    "no_rows": "No rows were read",
}


def _valid_opn(code: str, md: dict) -> bool:
    c = norm_code(code)
    if c in md["idle_codes"] or c in md["production_codes"]:
        return True
    for p in md.get("production_code_prefixes", {}):
        if c.startswith(p) and c[len(p):] in md["production_codes"]:
            return True
    return False


def nearest_machine(mc: str, md: dict) -> str | None:
    """Suggest a machine whose digits match once the dot is ignored (60402008 -> 604020.08)."""
    digits = norm_mc(mc).replace(".", "")
    for m in md["machines"]:
        if m.replace(".", "") == digits:
            return m
    return None


def nearest_code(code: str, md: dict) -> str | None:
    """Suggest a valid idle code one digit away (10613 -> 10813)."""
    c = norm_code(code)
    for valid in list(md["idle_codes"]) + list(md["production_codes"]):
        if len(valid) == len(c) and sum(a != b for a, b in zip(valid, c)) == 1:
            return valid
    return None


def validate(card: dict, md: dict | None = None) -> list[dict]:
    """Return a list of {flag, where, detail, suggestion} for one card."""
    md = md or master_data()
    raw_rows = card.get("rows") or []
    card = complete_card(card)
    out: list[dict] = []

    def add(flag, where="", detail="", suggestion=None):
        out.append({"flag": flag, "where": where, "detail": detail or FLAG_TEXT[flag],
                    "suggestion": suggestion})

    # Cells the reader itself was unsure about go to a person, even if every rule passes.
    for i, r in enumerate(raw_rows):
        for f in (r.get("unclear") or []) if isinstance(r, dict) else []:
            f = str(f).strip()
            if f:
                where = f if f.startswith("header.") else f"rows[{i}].{f}"
                add("unclear_cell", where, f"Reader marked {where} as unclear")

    h = card["header"]
    if is_blank("date", h["date"]):
        add("missing_date", "header.date")
    if h["mc_no"] and h["mc_no"] not in md["machines"] and norm_mc(h["mc_no"]) not in md["machines"]:
        add("unknown_machine", "header.mc_no", f"M/C No '{h['mc_no']}' not in machine list",
            nearest_machine(h["mc_no"], md))

    rows = card["rows"]
    if not rows:
        add("no_rows")
        return out

    for i, r in enumerate(rows):
        w = f"rows[{i}]"
        if r["emp_no"] and r["emp_no"] not in md["employees"]:
            add("unknown_employee", f"{w}.emp_no", f"Emp No '{r['emp_no']}' not in employee list")
        if r["opn_code"] and not _valid_opn(r["opn_code"], md):
            add("invalid_code", f"{w}.opn_code", f"Code '{r['opn_code']}' not on code sheet",
                nearest_code(r["opn_code"], md))
        if r["comp_code"] and str(norm_int(r["comp_code"])) not in md["components"]:
            add("unknown_component", f"{w}.comp_code", f"Comp Code '{r['comp_code']}' not in list")
        if r["rej_code"] and norm_short_code(r["rej_code"]) not in md["rejection_codes"]:
            add("invalid_rej_code", f"{w}.rej_code")
        if r["rework_code"] and norm_short_code(r["rework_code"]) not in md["rework_codes"]:
            add("invalid_rework_code", f"{w}.rework_code")
        if norm_code(r["opn_code"]) in md["idle_codes"] and (r["comp_code"] or r["qty_prod"] or r["qty_accp"]):
            add("idle_row_has_qty", f"{w}.qty_prod",
                f"Idle code {r['opn_code']} has comp {r['comp_code'] or '-'} / qty {r['qty_prod'] or '-'}")

        prod, accp = norm_int(r["qty_prod"]), norm_int(r["qty_accp"])
        rej, rew = norm_int(r["rej_qty"]) or 0, norm_int(r["rework_qty"]) or 0
        if prod is not None and accp is not None:
            if accp > prod:
                add("accp_gt_prod", f"{w}.qty_accp", f"Accepted {accp} > produced {prod}")
            if prod != accp + rej + rew:
                add("qty_balance", f"{w}.qty_prod",
                    f"Produced {prod} != accepted {accp} + rejected {rej} + rework {rew}")

        start, end = clock_minutes(r["time_from"], r["shift"]), clock_minutes(r["time_to"], r["shift"])
        total = duration_minutes(r["total_hours"])
        brk = md["shifts"].get(s(r["shift"]).upper(), {}).get("break_minutes", 30)
        if start is not None and end is not None and total is not None:
            span = end - start
            if total not in (span, span - brk):
                add("row_hours_mismatch", f"{w}.total_hours",
                    f"{r['time_from']}-{r['time_to']} is {span // 60}h{span % 60:02d}, "
                    f"written {r['total_hours']}")

    timed = []
    for i, r in enumerate(rows):
        a, b = clock_minutes(r["time_from"], r["shift"]), clock_minutes(r["time_to"], r["shift"])
        if a is not None and b is not None:
            timed.append((a, b, i))
    timed.sort()
    for (a1, b1, i1), (a2, b2, i2) in zip(timed, timed[1:]):
        if a2 < b1:
            add("time_overlap", f"rows[{i2}].time_from",
                f"Row {i2 + 1} starts at {rows[i2]['time_from']} before row {i1 + 1} ends at {rows[i1]['time_to']}")

    row_sum = sum(duration_minutes(r["total_hours"]) or 0 for r in rows)
    written = duration_minutes(card["total_hours"])
    paid = 8 * 60
    if row_sum != paid or (written is not None and written != paid):
        add("shift_hours_not_8", "total_hours",
            f"Rows add up to {row_sum // 60}h{row_sum % 60:02d}; written total {card['total_hours'] or '-'}")
    if written is not None and written != row_sum:
        add("total_mismatch", "total_hours")
    return out


def flag_names(card: dict, md: dict | None = None) -> set[str]:
    return {f["flag"] for f in validate(card, md)}


if __name__ == "__main__":
    md = master_data()
    ok = True
    for c in answer_key()["cards"]:
        got = flag_names(c, md)
        exp = set(c["expected_flags"])
        mark = "OK " if got == exp else "DIFF"
        ok &= got == exp
        print(f"{mark} {c['card_id']}: got {sorted(got) or '-'}  expected {sorted(exp) or '-'}")
        for f in validate(c, md):
            sug = f"  -> suggest {f['suggestion']}" if f["suggestion"] else ""
            print(f"       {f['where']}: {f['detail']}{sug}")
    print("\nAll cards match expected flags." if ok else "\nSome cards differ from expected flags.")
