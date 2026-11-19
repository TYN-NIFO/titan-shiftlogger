"""Create the database from scratch: drop + create tables, views and the read-only role, then load masters.

    cd 05_App/backend
    .venv/Scripts/python.exe scripts/init_db.py

Idempotent: every run drops everything (cards included) and rebuilds it.
Masters come from app/core/reading/master_data.json.
"""
from __future__ import annotations

import _cardlib  # noqa: F401  (puts the backend on sys.path)
from _cardlib import run_sql_file
from sqlalchemy import insert, text

from app.core.reading.common import master_data
from app.db.models import Code, Component, Employee, Machine
from app.db.session import engine


def master_rows(md: dict) -> dict[str, list[dict]]:
    details = md["employee_details"]
    emp_names, mc_names = md.get("employee_names", {}), md.get("machine_names", {})
    employees = [{"emp_no": e, "shift_group": details[e]["shift_group"],
                  "home_mc_no": details[e]["home_mc_no"], "name": emp_names.get(e)} for e in md["employees"]]
    machines = [{"mc_no": m, "machine_type": t, "is_cnc": t == "CNC", "name": mc_names.get(m)}
                for m, t in md["machines"].items()]
    comps = md["component_details"]
    components = [{"comp_code": c, "description": comps[c]["description"],
                   "std_rate_per_hour": float(comps[c]["std_rate_per_hour"])} for c in md["components"]]
    codes = []
    for c, d in md["production_codes"].items():
        codes.append({"code": c, "kind": "production", "description": d, "category": None})
    for c, d in md["idle_codes"].items():
        codes.append({"code": c, "kind": "idle", "description": d,
                      "category": md["idle_code_categories"].get(c, "other")})
    for c, d in md["rework_codes"].items():
        codes.append({"code": f"RW-{c}", "kind": "rework", "description": d, "category": None})
    for c, d in md["rejection_codes"].items():
        codes.append({"code": f"RJ-{c}", "kind": "rejection", "description": d, "category": None})
    return {"employees": employees, "machines": machines, "components": components, "codes": codes}


def init_db() -> dict[str, int]:
    md = master_data()
    rows = master_rows(md)
    with engine.begin() as conn:
        run_sql_file(conn, "001_schema.sql")
        run_sql_file(conn, "002_views.sql")
        run_sql_file(conn, "003_readonly_role.sql")
        conn.execute(insert(Employee), rows["employees"])
        conn.execute(insert(Machine), rows["machines"])
        conn.execute(insert(Component), rows["components"])
        conn.execute(insert(Code), rows["codes"])
        counts = {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
                  for t in ("employees", "machines", "components", "codes")}
    return counts


if __name__ == "__main__":
    counts = init_db()
    print("Database rebuilt (tables, views, read-only role titan_chat_ro).")
    for t, n in counts.items():
        print(f"  {t:11s} {n}")
