"""Generate 4 months of synthetic job cards with planted patterns, insert them, and write the demo answers.

    cd 05_App/backend
    .venv/Scripts/python.exe scripts/generate_synthetic.py --seed 42

Period 2026-07-20 .. 2026-11-14, Mon-Sat, shifts A and B, 40 operators per shift
(from master_data.json employee_details), one card per operator per shift-day.
Cards follow the real pattern: 10202 production rows with comp + qty, idle rows with an
idle code and no qty, 12-hour h.mm times, rows adding up to 8.00 paid hours (the 30-min
break sits inside one row, so that row's span is its total + 0.30, as on the photo cards).

Planted patterns (see CONTRACT.md):
1. CNC 604021.05 has clearly the most breakdown hours (10803 + 10804): ~1.5-2x the next CNC.
2. 280419, 280671, 280744 have 12-15 absent shifts each; everyone else 0-6 (median ~3).
3. 280512, 280903, 279871 have the lowest efficiency (~66-71%); everyone else 82-122%.
4. Noise: preventive maintenance, no tool, tool reconditioning, cleaning, TPM, training,
   no load, a utilities cut, and a few rejections and reworks.

The slots of the 10 photo cards (operator + date + shift) are left empty: those cards are the
real record for that shift (seeded by seed_photo_cards.py or uploaded live in the demo).

Every card must pass validate() with zero flags, and the planted patterns are checked
through the views; the script fails loudly otherwise. Then the true answers to the 3 demo
questions are computed through the views (as titan_chat_ro) into tests/expected_answers.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone

import _cardlib  # noqa: F401  (puts the backend on sys.path)
from _cardlib import BACKEND, card_columns, parse_card_date, row_columns
from sqlalchemy import insert, text

from app.core.reading.common import answer_key, master_data
from app.core.reading.validate import validate
from app.db.models import CardRow, JobCard
from app.db.session import chat_engine, engine

START, END = date(2026, 7, 20), date(2026, 11, 14)
TODAY = "2026-11-18"
IST = timezone(timedelta(hours=5, minutes=30))

# shift: (start, end, break start) in minutes after midnight
SHIFTS = {"A": (6 * 60, 14 * 60 + 30, 10 * 60), "B": (14 * 60 + 30, 23 * 60, 19 * 60)}
BREAK = 30

PLANTED_ABSENT = {"280419": 14, "280671": 13, "280744": 12}
PLANTED_LOW = {"280512": 0.66, "280903": 0.69, "279871": 0.71}
TOP_CNC = "604021.05"

# breakdown events per machine over the whole period (each event: all operators on that machine-shift log it)
BREAKDOWN_EVENTS = {"604021.05": 30, "604021.03": 17, "604021.01": 15, "604021.07": 14, "604021.09": 12}
PRESS_BREAKDOWN_EVENTS = 10

MACHINE_COMPONENTS = {
    "604020.08": ["6147", "1163"], "604020.11": ["1163", "6147"],
    "604020.02": ["4418", "6147"], "604020.04": ["5172", "1163"], "604020.06": ["6147", "4418"],
    "604020.13": ["1163", "5172"], "604020.15": ["4418", "5172"],
    "604021.01": ["7205", "2250"], "604021.03": ["2250", "7205"], "604021.05": ["3341", "8830"],
    "604021.07": ["8830", "3341"], "604021.09": ["2250", "8830"],
}

# operator-level idle noise: code -> (probability per card, possible minutes)
OPERATOR_IDLE = {
    "10836": (0.25, [30]),            # machine cleaning
    "10810": (0.04, [30, 60, 90]),    # no tool
    "10811": (0.03, [30, 60]),        # tool reconditioning
    "10825": (0.05, [30]),            # TPM by operator
    "10815": (0.015, [60, 120]),      # training
    "10806": (0.02, [60, 90, 120]),   # no load
    "10826": (0.01, [30, 60]),        # kanban full
}
MAX_IDLE = 330                        # keep at least 2.30 h of production on a working card


# ---------------------------------------------------------------- small helpers

def work_days() -> list[date]:
    d, out = START, []
    while d <= END:
        if d.weekday() < 6:          # Mon-Sat
            out.append(d)
        d += timedelta(days=1)
    return out


def clock(m: int) -> str:
    """Minutes after midnight -> 12-hour card time 'h.mm' (14:30 -> '2.30')."""
    h, mm = divmod(m, 60)
    if h > 12:
        h -= 12
    return f"{h}.{mm:02d}"


def hours_text(m: int) -> str:
    return f"{m // 60}.{m % 60:02d}"


def photo_slots() -> set[tuple[str, date, str]]:
    """(emp_no, date, shift) of the 10 photo cards; a missing date uses the fill sheet's date."""
    slots = set()
    for c in answer_key()["cards"]:
        d = parse_card_date(c["header"]["date"])
        if d is None:
            for corr in c.get("corrections", []):
                if corr["field"] == "header.date":
                    d = parse_card_date(corr["should_be"])
        r = c["rows"][0]
        slots.add((r["emp_no"], d, r["shift"]))
    return slots


# ---------------------------------------------------------------- the plan

def make_plan(rng: random.Random, md: dict, days: list[date]):
    emps = md["employee_details"]
    machines = md["machines"]
    slots = photo_slots()

    # efficiency factor per operator
    eff = {}
    for e in md["employees"]:
        eff[e] = PLANTED_LOW.get(e) or min(1.22, max(0.82, rng.gauss(1.0, 0.08)))

    # absent days per operator
    absent: dict[str, set[date]] = {}
    for e, d in emps.items():
        n = PLANTED_ABSENT.get(e) or rng.choice([0, 1, 2, 2, 3, 3, 3, 3, 4, 4, 5, 6])
        free = [day for day in days if (e, day, d["shift_group"]) not in slots]
        absent[e] = set(rng.sample(free, n))

    # machine-level events: (mc, day, shift) -> [(code, minutes)]
    events: dict[tuple[str, date, str], list[tuple[str, int]]] = {}
    all_slots = [(day, sh) for day in days for sh in "AB"]
    for mc, kind in machines.items():
        n = BREAKDOWN_EVENTS.get(mc, PRESS_BREAKDOWN_EVENTS)
        for day, sh in rng.sample(all_slots, n):
            mins = rng.choice([60, 90, 120, 150, 180])
            events.setdefault((mc, day, sh), []).append((rng.choice(["10803", "10804"]), mins))
        for day, sh in all_slots:                       # preventive maintenance ~ every 2 weeks
            if rng.random() < 0.04 and len(events.get((mc, day, sh), [])) == 0:
                events.setdefault((mc, day, sh), []).append(("10801", rng.choice([60, 90])))
    for day, sh in rng.sample(all_slots, 4):           # plant-wide utilities cut
        mins = rng.choice([30, 60])
        for mc in machines:
            events.setdefault((mc, day, sh), []).append(("10808", mins))
    return eff, absent, events, slots


def blocks_to_rows(rng, emp, sh, idle, prod_minutes, comps, rate_of, eff) -> list[dict]:
    """Lay idle blocks and production chunks out in time from shift start; break inside one row."""
    units = prod_minutes // 30
    n_slots = len(idle) + 1
    sizes = [1] * n_slots
    if idle and rng.random() < 0.3:                    # sometimes the shift starts with an idle row
        sizes[0] = 0
    if not idle:                                       # a plain production shift: two rows, like C01
        sizes = [1, 1]
    while sum(sizes) > units:                          # many idle rows: two may sit side by side
        sizes[sizes.index(1)] = 0
    for _ in range(units - sum(sizes)):
        sizes[rng.randrange(len(sizes))] += 1
    rng.shuffle(idle)
    seq: list[tuple[str, int]] = []
    for i, size in enumerate(sizes):
        if size:
            seq.append(("10202", size * 30))
        if i < len(idle):
            seq.append(idle[i])

    prod_idx = [i for i, (c, _) in enumerate(seq) if c == "10202"]
    two = len(comps) > 1 and len(prod_idx) >= 2
    switch_at = prod_idx[len(prod_idx) // 2] if two else None

    start, end, brk = SHIFTS[sh]
    t, rows, comp = start, [], comps[0]
    for i, (code, mins) in enumerate(seq):
        a, b = t, t + mins
        if a <= brk < b:
            b += BREAK                                 # this row spans the break
        row = {"emp_no": emp, "shift": sh, "opn_code": code,
               "time_from": clock(a), "time_to": clock(b), "total_hours": hours_text(mins)}
        if code == "10202":
            if two and i == switch_at:
                comp = comps[1]
            accp = max(1, round(mins / 60 * rate_of[comp] * eff * rng.uniform(0.94, 1.06)))
            rej = rew = 0
            if rng.random() < 0.06:
                rej = max(1, round(accp * rng.uniform(0.005, 0.03)))
                row["rej_code"], row["rej_qty"] = rng.choice(REJ_CODES), str(rej)
            if rng.random() < 0.05:
                rew = max(1, round(accp * rng.uniform(0.005, 0.03)))
                row["rework_code"], row["rework_qty"] = rng.choice(RW_CODES), str(rew)
            row.update(comp_code=comp, qty_prod=str(accp + rej + rew), qty_accp=str(accp))
        rows.append(row)
        t = b
    assert t == end, (emp, sh, seq)
    return rows


REJ_CODES: list[str] = []
RW_CODES: list[str] = []


def make_cards(rng: random.Random, md: dict) -> list[dict]:
    global REJ_CODES, RW_CODES
    REJ_CODES, RW_CODES = list(md["rejection_codes"]), list(md["rework_codes"])
    days = work_days()
    eff, absent, events, slots = make_plan(rng, md, days)
    rate_of = {c: float(d["std_rate_per_hour"]) for c, d in md["component_details"].items()}
    desc_of = {c: d["description"] for c, d in md["component_details"].items()}
    by_type: dict[str, list[str]] = {}
    for mc, t in md["machines"].items():
        by_type.setdefault(t, []).append(mc)

    cards = []
    for day in days:
        for emp in md["employees"]:
            info = md["employee_details"][emp]
            sh, home = info["shift_group"], info["home_mc_no"]
            if (emp, day, sh) in slots:
                continue
            date_text = day.strftime("%d/%m/%y") if rng.random() < 0.8 else day.strftime("%d/%m/%Y")
            s0, s1, _ = SHIFTS[sh]
            if day in absent[emp]:
                cards.append({"header": {"date": date_text, "component_description": "", "cc": "",
                                         "operation_description": "", "mc_no": home},
                              "rows": [{"emp_no": emp, "shift": sh, "opn_code": "10813",
                                        "time_from": clock(s0), "time_to": clock(s1), "total_hours": "8.00"}],
                              "total_hours": "8.00"})
                continue
            mc = home
            if rng.random() < 0.03:                    # an occasional move to a sister machine
                mc = rng.choice([m for m in by_type[md["machines"][home]] if m != home])
            idle = list(events.get((mc, day, sh), []))
            for code, (p, choices) in OPERATOR_IDLE.items():
                if rng.random() < p:
                    idle.append((code, rng.choice(choices)))
            while sum(m for _, m in idle) > MAX_IDLE:   # drop operator noise first, never the machine events
                idle.pop()
            comps = MACHINE_COMPONENTS[mc][:]
            comps = comps if rng.random() < 0.15 else [comps[0] if rng.random() < 0.7 else comps[1]]
            rows = blocks_to_rows(rng, emp, sh, idle, 480 - sum(m for _, m in idle), comps, rate_of, eff[emp])
            used = list(dict.fromkeys(r["comp_code"] for r in rows if r.get("comp_code")))
            header = {"date": date_text,
                      "component_description": desc_of[used[0]] if len(used) == 1 and rng.random() < 0.4 else "",
                      "cc": ", ".join(used), "operation_description": "F, W, T", "mc_no": mc}
            cards.append({"header": header, "rows": rows, "total_hours": "8.00"})
    return cards


# ---------------------------------------------------------------- database

def insert_cards(cards: list[dict], md: dict) -> tuple[int, int]:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM job_cards WHERE source = 'synthetic'"))
        first_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM job_cards")).scalar_one()
        card_rows_out, row_rows_out = [], []
        for n, card in enumerate(cards):
            cid = first_id + n
            cols = card_columns(card, md)
            _, end, _ = SHIFTS[cols["shift"]]
            saved = datetime.combine(cols["card_date"], datetime.min.time(), IST) + timedelta(minutes=end + 20)
            card_rows_out.append({
                "id": cid, "card_ref": f"SYN-{cid:06d}", "source": "synthetic", "status": "approved",
                "image_path": None, "flags": [], "extracted": None, "read_model": None,
                "read_seconds": None, "error": None, "created_at": saved,
                "approved_at": saved, "approved_by": "supervisor", **cols})
            for i, r in enumerate(card["rows"], start=1):
                row_rows_out.append({"card_id": cid, **row_columns(r, i)})
        conn.execute(insert(JobCard), card_rows_out)
        conn.execute(insert(CardRow), row_rows_out)
        conn.execute(text("SELECT setval(pg_get_serial_sequence('job_cards', 'id'), "
                          "(SELECT MAX(id) FROM job_cards))"))
    return len(card_rows_out), len(row_rows_out)


# ---------------------------------------------------------------- demo answers (through the views)

QUESTIONS = {
    "q1_cnc_breakdown": {
        "question": "Which CNC machine lost the most hours to breakdowns in the last four months?",
        "sql": ("SELECT mc_no, ROUND(SUM(hours), 1) AS breakdown_hours FROM v_downtime "
                "WHERE is_cnc AND category = 'breakdown' "
                "AND card_date BETWEEN DATE '2026-07-20' AND DATE '2026-11-14' "
                "GROUP BY mc_no ORDER BY breakdown_hours DESC, mc_no"),
    },
    "q2_absenteeism": {
        "question": "Who has the highest absenteeism?",
        "sql": ("SELECT emp_no, COUNT(*) AS absent_shifts FROM v_absenteeism "
                "WHERE card_date BETWEEN DATE '2026-07-20' AND DATE '2026-11-14' "
                "GROUP BY emp_no ORDER BY absent_shifts DESC, emp_no"),
    },
    "q3_least_productive": {
        "question": "Who's least productive?",
        "sql": ("SELECT emp_no, shift, efficiency_pct FROM v_operator_productivity "
                "ORDER BY efficiency_pct ASC, emp_no"),
    },
}


def _plain(v):
    if v is None or isinstance(v, (str, int)):
        return v
    return float(v)


def demo_answers() -> dict:
    out = {"_note": ("True answers to the 3 demo questions, computed by generate_synthetic.py --seed 42 "
                     "through the views as titan_chat_ro, over synthetic cards only (before seed_photo_cards.py; "
                     "approved photo cards C06/C07/C10 add a little production but no breakdown or absence)."),
           "seed": 42, "window": {"from": START.isoformat(), "to": END.isoformat()}, "today": TODAY}
    with chat_engine.connect() as conn:
        for key, q in QUESTIONS.items():
            res = conn.execute(text(q["sql"]))
            rows = [[_plain(v) for v in r] for r in res]
            out[key] = {**q, "columns": list(res.keys()), "rows": rows}
    out["q1_cnc_breakdown"]["top"] = out["q1_cnc_breakdown"]["rows"][0][0]
    out["q2_absenteeism"]["top3"] = [r[0] for r in out["q2_absenteeism"]["rows"][:3]]
    out["q3_least_productive"]["bottom3"] = [r[0] for r in out["q3_least_productive"]["rows"][:3]]
    return out


def check_patterns(ans: dict) -> list[str]:
    """The planted patterns must be obvious; returns a list of problems (empty = fine)."""
    problems = []
    q1 = ans["q1_cnc_breakdown"]["rows"]
    ratio = q1[0][1] / q1[1][1]
    if q1[0][0] != TOP_CNC or not 1.5 <= ratio <= 2.1:
        problems.append(f"CNC breakdown: top {q1[0]}, next {q1[1]}, ratio {ratio:.2f}")
    q2 = ans["q2_absenteeism"]["rows"]
    if set(r[0] for r in q2[:3]) != set(PLANTED_ABSENT) or q2[3][1] > 7:
        problems.append(f"Absenteeism top 4: {q2[:4]}")
    q3 = ans["q3_least_productive"]["rows"]
    if set(r[0] for r in q3[:3]) != set(PLANTED_LOW) or q3[3][2] - q3[2][2] < 5:
        problems.append(f"Productivity bottom 4: {q3[:4]}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    t0 = time.time()
    md = master_data()
    rng = random.Random(args.seed)

    cards = make_cards(rng, md)
    bad = [(i, validate(c, md)) for i, c in enumerate(cards)]
    bad = [(i, f) for i, f in bad if f]
    if bad:
        i, f = bad[0]
        print(f"ERROR: {len(bad)} generated cards have flags. First one:\n"
              f"{json.dumps(cards[i], indent=1)}\n{json.dumps(f, indent=1)}", file=sys.stderr)
        return 1
    print(f"Generated {len(cards)} cards; validate() -> 0 flags on every card.")

    n_cards, n_rows = insert_cards(cards, md)
    print(f"Inserted {n_cards} job_cards and {n_rows} card_rows (source='synthetic', status='approved').")

    ans = demo_answers()
    problems = check_patterns(ans)
    if problems:
        print("ERROR: planted patterns are not obvious:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    path = BACKEND / "tests" / "expected_answers.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(ans, indent=2) + "\n", encoding="utf-8")

    q1, q2, q3 = ans["q1_cnc_breakdown"]["rows"], ans["q2_absenteeism"]["rows"], ans["q3_least_productive"]["rows"]
    print("CNC breakdown hours:", ", ".join(f"{m} {h}" for m, h in q1))
    print("Top absentees:      ", ", ".join(f"{e} {n}" for e, n in q2[:5]))
    print("Lowest efficiency:  ", ", ".join(f"{e} ({s}) {p}%" for e, s, p in q3[:5]))
    print(f"Wrote {path.relative_to(BACKEND)} in {time.time() - t0:.1f} s total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
