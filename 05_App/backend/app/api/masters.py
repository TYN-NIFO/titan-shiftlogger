from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reading.common import master_data
from app.db.models import Code, Component, Employee, Machine
from app.db.session import get_session

router = APIRouter()


def _from_json() -> dict:
    """Fallback while the database is empty or being rebuilt."""
    md = master_data()
    comps = md["components"]
    if isinstance(comps, dict):
        components = [{"comp_code": k, "description": (v.get("description") if isinstance(v, dict) else v) or ""}
                      for k, v in comps.items()]
    else:
        components = [{"comp_code": c, "description": ""} for c in comps]
    emps = md["employees"]
    return {
        "employees": sorted(emps if isinstance(emps, list) else list(emps)),
        "machines": [{"mc_no": k, "machine_type": v if isinstance(v, str) else v.get("machine_type", "")}
                     for k, v in md["machines"].items()],
        "components": components,
        "idle_codes": dict(md["idle_codes"]),
        "production_codes": dict(md["production_codes"]),
        "rework_codes": dict(md["rework_codes"]),
        "rejection_codes": dict(md["rejection_codes"]),
    }


@router.get("/api/masters")
def masters(db: Session = Depends(get_session)) -> dict:
    try:
        employees = list(db.scalars(select(Employee.emp_no).order_by(Employee.emp_no)))
        machines = db.scalars(select(Machine).order_by(Machine.mc_no)).all()
        components = db.scalars(select(Component).order_by(Component.comp_code)).all()
        codes = db.scalars(select(Code).order_by(Code.code)).all()
    except Exception:  # noqa: BLE001
        db.rollback()
        return _from_json()
    if not employees or not machines or not codes:
        return _from_json()

    def by_kind(kind: str, prefix: str = "") -> dict:
        return {c.code[len(prefix):] if prefix and c.code.startswith(prefix) else c.code: c.description
                for c in codes if c.kind == kind}

    return {
        "employees": employees,
        "machines": [{"mc_no": m.mc_no, "machine_type": m.machine_type} for m in machines],
        "components": [{"comp_code": c.comp_code, "description": c.description or ""} for c in components],
        "idle_codes": by_kind("idle"),
        "production_codes": by_kind("production"),
        "rework_codes": by_kind("rework", "RW-"),
        "rejection_codes": by_kind("rejection", "RJ-"),
    }
