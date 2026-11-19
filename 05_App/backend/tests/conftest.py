"""Test setup: a separate database (titan_shiftlogger_test), LLM_MODE=stub, a temp upload folder.

The schema comes from models.py (Base.metadata.create_all). Views and the read-only role come from
app/db/sql/002_views.sql and 003_readonly_role.sql (the DATA agent's files); the role name is changed
to titan_chat_ro_test so tests never touch the real role. If 002_views.sql is missing, minimal
equivalent views are created here instead.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = "titan_shiftlogger_test"
TEST_ROLE = "titan_chat_ro_test"
PG = "postgresql+psycopg://postgres:password@localhost:5432"

# Must be set before anything imports app.db.session (env vars win over 05_App/.env).
os.environ["DATABASE_URL"] = f"{PG}/{TEST_DB}"
os.environ["CHAT_DATABASE_URL"] = f"postgresql+psycopg://{TEST_ROLE}:{TEST_ROLE}@localhost:5432/{TEST_DB}"
os.environ["LLM_MODE"] = "stub"
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"          # nothing listens: reachable = false, fast
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="titan_uploads_")

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
SQL_DIR = BACKEND / "app" / "db" / "sql"
REPO = BACKEND.parents[1]
PHOTOS = REPO / "04_PoC" / "Synthetic_Job_Cards" / "Photos"

import pytest  # noqa: E402
from sqlalchemy import create_engine, insert, text  # noqa: E402

FALLBACK_VIEWS = """
CREATE VIEW v_production AS
SELECT jc.card_date, COALESCE(r.shift, jc.shift) AS shift, COALESCE(r.emp_no, jc.emp_no) AS emp_no,
       jc.mc_no, m.machine_type, COALESCE(m.is_cnc, false) AS is_cnc, r.comp_code,
       COALESCE(r.qty_prod, 0) AS qty_prod, COALESCE(r.qty_accp, 0) AS qty_accp,
       COALESCE(r.rej_qty, 0) AS rej_qty, COALESCE(r.rework_qty, 0) AS rework_qty, r.minutes / 60.0 AS hours
FROM card_rows r JOIN job_cards jc ON jc.id = r.card_id LEFT JOIN machines m ON m.mc_no = jc.mc_no
WHERE jc.status = 'approved'
  AND regexp_replace(r.opn_code, '^[A-Z]+', '') IN (SELECT code FROM codes WHERE kind = 'production');
CREATE VIEW v_downtime AS
SELECT jc.card_date, COALESCE(r.shift, jc.shift) AS shift, COALESCE(r.emp_no, jc.emp_no) AS emp_no,
       jc.mc_no, m.machine_type, COALESCE(m.is_cnc, false) AS is_cnc, r.opn_code AS code,
       c.description AS reason, COALESCE(c.category, 'other') AS category, r.minutes / 60.0 AS hours
FROM card_rows r JOIN job_cards jc ON jc.id = r.card_id
JOIN codes c ON c.code = r.opn_code AND c.kind = 'idle' LEFT JOIN machines m ON m.mc_no = jc.mc_no
WHERE jc.status = 'approved' AND r.opn_code <> '10813';
CREATE VIEW v_absenteeism AS
SELECT DISTINCT jc.card_date, COALESCE(r.shift, jc.shift) AS shift, COALESCE(r.emp_no, jc.emp_no) AS emp_no, jc.mc_no
FROM card_rows r JOIN job_cards jc ON jc.id = r.card_id
WHERE jc.status = 'approved' AND r.opn_code = '10813';
CREATE VIEW v_operator_productivity_daily AS
SELECT p.card_date, p.emp_no, p.shift, ROUND(SUM(p.hours), 2) AS productive_hours, SUM(p.qty_accp) AS qty_accp,
       ROUND(SUM(p.hours * c.std_rate_per_hour::numeric), 1) AS std_qty
FROM v_production p LEFT JOIN components c ON c.comp_code = p.comp_code GROUP BY p.card_date, p.emp_no, p.shift;
CREATE VIEW v_operator_productivity AS
SELECT p.emp_no, p.shift, COUNT(DISTINCT p.card_date) AS days_worked, ROUND(SUM(p.hours), 1) AS productive_hours,
       SUM(p.qty_accp) AS qty_accp, ROUND(SUM(p.hours * c.std_rate_per_hour::numeric), 0) AS std_qty,
       ROUND(100.0 * SUM(p.qty_accp) / NULLIF(SUM(p.hours * c.std_rate_per_hour::numeric), 0), 1) AS efficiency_pct
FROM v_production p LEFT JOIN components c ON c.comp_code = p.comp_code GROUP BY p.emp_no, p.shift;
"""

FALLBACK_ROLE = f"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{TEST_ROLE}') THEN
    CREATE ROLE {TEST_ROLE} LOGIN PASSWORD '{TEST_ROLE}';
  END IF;
END $$;
ALTER ROLE {TEST_ROLE} SET default_transaction_read_only = on;
ALTER ROLE {TEST_ROLE} SET statement_timeout = '5s';
GRANT CONNECT ON DATABASE {TEST_DB} TO {TEST_ROLE};
GRANT USAGE ON SCHEMA public TO {TEST_ROLE};
GRANT SELECT ON v_production, v_downtime, v_absenteeism, v_operator_productivity,
  v_operator_productivity_daily, machines, codes, employees TO {TEST_ROLE};
"""

# Planted chat-test patterns (small, so the expected answers are obvious).
TOP_CNC, OTHER_CNC, PRESS = "604021.05", "604021.03", "604020.08"
TOP_ABSENT = "280419"
LOW_PRODUCER, HIGH_PRODUCER = "280588", "280133"


def _master_rows(md: dict) -> dict:
    emp_d = md.get("employee_details", {})
    comp_d = md.get("component_details", {})
    cats = md.get("idle_code_categories", {})
    comps = md["components"] if isinstance(md["components"], list) else list(md["components"])
    codes = [{"code": c, "kind": "production", "description": d, "category": None}
             for c, d in md["production_codes"].items()]
    codes += [{"code": c, "kind": "idle", "description": d,
               "category": cats.get(c, "breakdown" if c in ("10803", "10804") else "other")}
              for c, d in md["idle_codes"].items()]
    codes += [{"code": f"RW-{c}", "kind": "rework", "description": d, "category": None}
              for c, d in md["rework_codes"].items()]
    codes += [{"code": f"RJ-{c}", "kind": "rejection", "description": d, "category": None}
              for c, d in md["rejection_codes"].items()]
    return {
        "employees": [{"emp_no": e, "shift_group": emp_d.get(e, {}).get("shift_group"),
                       "home_mc_no": emp_d.get(e, {}).get("home_mc_no"),
                       "name": md.get("employee_names", {}).get(e)} for e in md["employees"]],
        "machines": [{"mc_no": m, "machine_type": t, "is_cnc": t == "CNC",
                      "name": md.get("machine_names", {}).get(m)} for m, t in md["machines"].items()],
        "components": [{"comp_code": c, "description": comp_d.get(c, {}).get("description", ""),
                        "std_rate_per_hour": float(comp_d.get(c, {}).get("std_rate_per_hour", 100))}
                       for c in comps],
        "codes": codes,
    }


def _hm(minutes: int) -> str:
    return f"{minutes // 60}.{minutes % 60:02d}"


def _seed_history(md: dict) -> None:
    """A few approved synthetic cards with the planted patterns, written through the app's own code."""
    from app.db.models import JobCard
    from app.db.session import SessionLocal
    from app.services.cards import apply_card_values

    comp = md["components"][0] if isinstance(md["components"], list) else next(iter(md["components"]))
    rate = float(md.get("component_details", {}).get(comp, {}).get("std_rate_per_hour", 100))

    def card(day: int, emp: str, mc: str, rows: list[tuple]) -> dict:
        out = []
        for code, minutes, qty in rows:
            out.append({"emp_no": emp, "shift": "A", "opn_code": code, "comp_code": comp if qty else "",
                        "qty_prod": str(qty) if qty else "", "qty_accp": str(qty) if qty else "",
                        "total_hours": _hm(minutes)})
        return {"header": {"date": f"{day:02d}/10/26", "mc_no": mc}, "rows": out, "total_hours": "8.00"}

    cards = []
    for day in range(1, 7):
        cards.append(card(day, HIGH_PRODUCER, TOP_CNC, [("10202", 300, int(rate * 5)), ("10804", 180, 0)]))
        cards.append(card(day, LOW_PRODUCER, OTHER_CNC, [("10202", 420, int(rate * 7 * 0.5)), ("10803", 60, 0)]))
        cards.append(card(day, "279915", PRESS, [("10202", 240, int(rate * 4 * 0.9)), ("10803", 240, 0)]))
    for day in range(1, 5):
        cards.append(card(day + 10, TOP_ABSENT, PRESS, [("10813", 480, 0)]))
    for day in range(1, 3):
        cards.append(card(day + 10, "280671", PRESS, [("10813", 480, 0)]))
    cards.append(card(20, "279842", PRESS, [("10813", 480, 0)]))

    with SessionLocal() as db:
        for i, values in enumerate(cards, start=1):
            jc = JobCard(card_ref=f"SYN-T{i:03d}", source="synthetic", status="approved", header={}, flags=[])
            apply_card_values(jc, values, md)
            jc.status = "approved"
            db.add(jc)
        db.commit()


@pytest.fixture(scope="session", autouse=True)
def database():
    admin = create_engine(f"{PG}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {TEST_DB}"))
    admin.dispose()

    from app.core.reading.common import master_data
    from app.db.models import Base, Code, Component, Employee, Machine
    from app.db.session import engine

    Base.metadata.create_all(engine)
    views = SQL_DIR / "002_views.sql"
    role = SQL_DIR / "003_readonly_role.sql"
    with engine.begin() as c:
        c.exec_driver_sql(views.read_text(encoding="utf-8") if views.exists() else FALLBACK_VIEWS)
        if role.exists():
            c.exec_driver_sql(role.read_text(encoding="utf-8").replace("titan_chat_ro", TEST_ROLE))
        else:
            c.exec_driver_sql(FALLBACK_ROLE)
        md = master_data()
        rows = _master_rows(md)
        c.execute(insert(Employee), rows["employees"])
        c.execute(insert(Machine), rows["machines"])
        c.execute(insert(Component), rows["components"])
        c.execute(insert(Code), rows["codes"])
    _seed_history(md)
    yield engine


@pytest.fixture(scope="session")
def client(database):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def photo():
    def _open(ref: str):
        p = PHOTOS / f"{ref}_front.jpeg"
        return {"file": (p.name, p.read_bytes(), "image/jpeg")}
    return _open
