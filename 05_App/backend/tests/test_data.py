"""Data checks on the REAL demo database (titan_shiftlogger), after:

    .venv/Scripts/python.exe scripts/init_db.py
    .venv/Scripts/python.exe scripts/generate_synthetic.py --seed 42
    .venv/Scripts/python.exe scripts/seed_photo_cards.py
    .venv/Scripts/python.exe -m pytest tests/test_data.py

conftest.py points app.db.session at a separate test database, so these tests build their own
engines from 05_App/.env (or .env.example) instead.
"""
from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.core.reading.common import answer_key, master_data
from app.core.reading.validate import flag_names, validate
from app.db.models import Base

BACKEND = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND.parent
EXPECTED = json.loads((BACKEND / "tests" / "expected_answers.json").read_text(encoding="utf-8"))

PLANTED_ABSENT = {"280419", "280671", "280744"}
PLANTED_LOW = {"280512", "280903", "279871"}
ORIGINAL_EMPLOYEES = ["279842", "279915", "280133", "280207", "280356", "280419", "280588", "280671"]
ORIGINAL_MACHINES = {"604020.08": "Press", "604020.11": "Press", "604021.03": "CNC", "604021.05": "CNC"}


def _env_file() -> dict:
    for name in (".env", ".env.example"):
        p = APP_ROOT / name
        if p.exists():
            out = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
    return {}


ENV = _env_file()
DB_URL = os.environ.get("TITAN_DATA_DB_URL", ENV.get("DATABASE_URL"))
RO_URL = os.environ.get("TITAN_DATA_RO_URL", ENV.get("CHAT_DATABASE_URL"))


@pytest.fixture(scope="module")
def db():
    eng = create_engine(DB_URL)
    with eng.connect() as c:
        n = c.execute(text("SELECT count(*) FROM job_cards WHERE source = 'synthetic'")).scalar_one()
    if n == 0:
        pytest.fail("No synthetic cards: run scripts/init_db.py and scripts/generate_synthetic.py first")
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def ro():
    eng = create_engine(RO_URL)
    yield eng
    eng.dispose()


def rows(engine, sql: str) -> list[tuple]:
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text(sql))]


# ---------------------------------------------------------------- masters

def test_master_data_file():
    md = master_data()
    assert len(md["employees"]) == 80 and len(set(md["employees"])) == 80
    assert md["employees"][:8] == ORIGINAL_EMPLOYEES
    assert all(e.isdigit() and 279800 <= int(e) <= 280999 for e in md["employees"])
    assert "999999" not in md["employees"]
    assert set(md["employee_details"]) == set(md["employees"])
    for shift in "AB":
        assert sum(d["shift_group"] == shift for d in md["employee_details"].values()) == 40

    assert len(md["machines"]) == 12
    assert {m: t for m, t in md["machines"].items() if m in ORIGINAL_MACHINES} == ORIGINAL_MACHINES
    press = [m for m, t in md["machines"].items() if t == "Press"]
    cnc = [m for m, t in md["machines"].items() if t == "CNC"]
    assert len(press) == 7 and all(m.startswith("604020.") for m in press)
    assert len(cnc) == 5 and all(m.startswith("604021.") for m in cnc)
    assert [m for m in md["machines"] if m.replace(".", "") == "60402008"] == ["604020.08"]

    assert len(md["components"]) == 8 and md["components"][:4] == ["6147", "1163", "2250", "3341"]
    assert set(md["component_details"]) == set(md["components"])
    assert set(md["idle_code_categories"]) == set(md["idle_codes"])
    assert {md["idle_code_categories"][c] for c in ("10803", "10804")} == {"breakdown"}


def test_master_tables(db):
    md = master_data()
    counts = dict(rows(db, "SELECT 'employees', count(*) FROM employees UNION ALL "
                           "SELECT 'machines', count(*) FROM machines UNION ALL "
                           "SELECT 'cnc', count(*) FROM machines WHERE is_cnc UNION ALL "
                           "SELECT 'components', count(*) FROM components"))
    assert counts == {"employees": 80, "machines": 12, "cnc": 5, "components": 8}
    kinds = dict(rows(db, "SELECT kind, count(*) FROM codes GROUP BY kind"))
    assert kinds == {"production": len(md["production_codes"]), "idle": len(md["idle_codes"]),
                     "rework": len(md["rework_codes"]), "rejection": len(md["rejection_codes"])}
    assert rows(db, "SELECT count(*) FROM codes WHERE kind = 'rework' AND code NOT LIKE 'RW-%'") == [(0,)]
    assert rows(db, "SELECT count(*) FROM codes WHERE kind = 'rejection' AND code NOT LIKE 'RJ-%'") == [(0,)]
    assert rows(db, "SELECT count(*) FROM codes WHERE kind = 'idle' AND category IS NULL") == [(0,)]


PG_TYPE = {"String": "character varying", "Integer": "integer", "Boolean": "boolean", "Date": "date",
           "DateTime": "timestamp with time zone", "Float": "double precision", "Text": "text", "JSONB": "jsonb"}


def test_schema_matches_models(db):
    """001_schema.sql == models.py: columns, types, lengths, nullability, indexes, foreign keys."""
    insp = inspect(db)
    for table in Base.metadata.sorted_tables:
        info = {r[0]: r[1:] for r in rows(db, (
            "SELECT column_name, data_type, character_maximum_length, is_nullable "
            f"FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{table.name}'"))}
        expected = {c.name: (PG_TYPE[type(c.type).__name__], getattr(c.type, "length", None),
                             "YES" if c.nullable else "NO") for c in table.columns}
        assert info == expected, table.name
        idx = {tuple(i["column_names"]) for i in insp.get_indexes(table.name)}
        assert idx == {tuple(col.name for col in i.columns) for i in table.indexes}, table.name
        fks = {(tuple(f["constrained_columns"]), f["referred_table"], (f.get("options") or {}).get("ondelete"))
               for f in insp.get_foreign_keys(table.name)}
        assert fks == {((fk.parent.name,), fk.column.table.name, fk.ondelete) for fk in table.foreign_keys}


# ---------------------------------------------------------------- photo cards

def test_photo_card_flags_unchanged_with_expanded_masters():
    md = master_data()
    for card in answer_key()["cards"]:
        assert flag_names(card, md) == set(card["expected_flags"]), card["card_id"]


def test_seeded_photo_cards(db):
    got = dict(rows(db, "SELECT card_ref, status FROM job_cards WHERE source = 'photo' AND card_ref IN "
                        "('C01','C02','C03','C04','C05','C06','C07','C08','C09','C10')"))
    if not got:
        pytest.skip("photo cards not seeded (scripts/seed_photo_cards.py is optional)")
    assert set(got) >= {"C01", "C03", "C05", "C06", "C07", "C09", "C10"}
    for ref in ("C01", "C03", "C05", "C09"):
        assert got[ref] == "needs_review"
    for ref in ("C06", "C07", "C10"):
        assert got[ref] == "approved"


# ---------------------------------------------------------------- synthetic cards

def test_every_synthetic_card_is_clean(db):
    md = master_data()
    cards: dict[int, dict] = {}
    with db.connect() as c:
        for cid, header, total, status, flags, ref in c.execute(text(
                "SELECT id, header, total_hours, status, flags, card_ref FROM job_cards WHERE source = 'synthetic'")):
            assert status == "approved" and flags == [] and ref == f"SYN-{cid:06d}"
            cards[cid] = {"header": header, "rows": [], "total_hours": total}
        for cid, raw, minutes in c.execute(text(
                "SELECT r.card_id, r.raw, r.minutes FROM card_rows r JOIN job_cards j ON j.id = r.card_id "
                "WHERE j.source = 'synthetic' ORDER BY r.card_id, r.row_no")):
            cards[cid]["rows"].append(raw)
            assert minutes is not None
    assert len(cards) > 7000
    bad = {cid: validate(card, md) for cid, card in cards.items()}
    bad = {cid: f for cid, f in bad.items() if f}
    assert not bad, f"{len(bad)} synthetic cards have flags, e.g. {next(iter(bad.items()))}"
    # one card per operator per shift-day; every card sums to 8 paid hours
    assert rows(db, "SELECT count(*) FROM (SELECT emp_no, card_date, shift FROM job_cards "
                    "WHERE status = 'approved' GROUP BY 1, 2, 3 HAVING count(*) > 1) d") == [(0,)]
    assert rows(db, "SELECT count(*) FROM (SELECT card_id FROM card_rows r JOIN job_cards j ON j.id = r.card_id "
                    "WHERE j.source = 'synthetic' GROUP BY card_id HAVING sum(minutes) <> 480) d") == [(0,)]


# ---------------------------------------------------------------- planted patterns (through the views)

def test_cnc_breakdown_pattern(ro):
    got = rows(ro, EXPECTED["q1_cnc_breakdown"]["sql"])
    assert [r[0] for r in got] == [r[0] for r in EXPECTED["q1_cnc_breakdown"]["rows"]]
    assert [float(r[1]) for r in got] == [r[1] for r in EXPECTED["q1_cnc_breakdown"]["rows"]]
    assert got[0][0] == "604021.05"
    assert 1.5 <= float(got[0][1]) / float(got[1][1]) <= 2.1
    assert len(got) == 5


def test_absenteeism_pattern(ro):
    got = rows(ro, EXPECTED["q2_absenteeism"]["sql"])
    assert {r[0] for r in got[:3]} == PLANTED_ABSENT
    assert all(12 <= r[1] <= 15 for r in got[:3])
    assert got[3][1] <= 7
    all_counts = dict(got)
    median = statistics.median(all_counts.get(e, 0) for e in master_data()["employees"])
    assert 2 <= median <= 4
    assert [list(r) for r in got[:3]] == EXPECTED["q2_absenteeism"]["rows"][:3]


def test_least_productive_pattern(ro):
    got = rows(ro, EXPECTED["q3_least_productive"]["sql"])
    assert {r[0] for r in got[:3]} == PLANTED_LOW
    assert float(got[3][2]) - float(got[2][2]) >= 5            # a clear gap above the bottom 3
    effs = [float(r[2]) for r in got[3:]]
    assert 75 <= min(effs) and max(effs) <= 130                 # the rest within about +-25 %
    assert [r[0] for r in got[:3]] == EXPECTED["q3_least_productive"]["bottom3"]


def test_views_approved_only(db):
    n_view = rows(db, "SELECT count(*) FROM v_absenteeism")[0][0]
    n_all = rows(db, "SELECT count(DISTINCT r.card_id) FROM card_rows r JOIN job_cards j ON j.id = r.card_id "
                     "WHERE r.opn_code = '10813' AND j.status = 'approved'")[0][0]
    assert n_view == n_all
    # C09 (needs_review, unknown employee 999999) never reaches the views
    assert rows(db, "SELECT count(*) FROM v_production WHERE emp_no = '999999'") == [(0,)]


# ---------------------------------------------------------------- read-only role

@pytest.mark.parametrize("view", ["v_production", "v_downtime", "v_absenteeism", "v_operator_productivity",
                                  "v_operator_productivity_daily", "machines", "codes", "employees"])
def test_readonly_role_can_select(ro, view):
    assert rows(ro, f"SELECT count(*) FROM {view}")[0][0] > 0


@pytest.mark.parametrize("sql", [
    "SELECT * FROM job_cards LIMIT 1",
    "SELECT * FROM card_rows LIMIT 1",
    "SELECT * FROM review_log LIMIT 1",
    "SELECT * FROM chat_log LIMIT 1",
    "INSERT INTO machines (mc_no, machine_type, is_cnc) VALUES ('X1', 'CNC', true)",
    "DELETE FROM employees",
    "UPDATE codes SET description = 'x'",
    "DELETE FROM job_cards",
    "CREATE TABLE ro_probe (id int)",
])
def test_readonly_role_cannot(ro, sql):
    with ro.connect() as c:
        with pytest.raises(DBAPIError):
            c.execute(text(sql))
        c.rollback()


def test_readonly_role_settings(ro):
    with ro.connect() as c:
        assert c.execute(text("SHOW default_transaction_read_only")).scalar_one() == "on"
        assert c.execute(text("SHOW statement_timeout")).scalar_one() == "5s"
        assert c.execute(text("SELECT current_user")).scalar_one() == "titan_chat_ro"
