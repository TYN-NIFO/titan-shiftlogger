"""SQLAlchemy 2 models: the source of truth for the schema (see 05_App/CONTRACT.md).

Field values on a card are kept twice:
- `job_cards.header` and `card_rows.raw` (JSON) hold the values *as written or read*, as strings;
- the typed columns of `card_rows` (ints, minutes) are the normalised values the SQL views use.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------ masters

class Employee(Base):
    __tablename__ = "employees"
    emp_no: Mapped[str] = mapped_column(String(12), primary_key=True)
    shift_group: Mapped[str | None] = mapped_column(String(2))       # A | B
    home_mc_no: Mapped[str | None] = mapped_column(String(16))
    name: Mapped[str | None] = mapped_column(String(60))              # made-up display name, e.g. "Ravi K."


class Machine(Base):
    __tablename__ = "machines"
    mc_no: Mapped[str] = mapped_column(String(16), primary_key=True)   # e.g. 604021.05
    machine_type: Mapped[str] = mapped_column(String(16))             # Press | CNC
    is_cnc: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str | None] = mapped_column(String(60))              # display name, e.g. "CNC case milling 1"


class Component(Base):
    __tablename__ = "components"
    comp_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(120))
    std_rate_per_hour: Mapped[float] = mapped_column(Float)            # standard accepted qty per productive hour


class Code(Base):
    __tablename__ = "codes"
    code: Mapped[str] = mapped_column(String(12), primary_key=True)    # 10804 | RW-001 | RJ-008
    kind: Mapped[str] = mapped_column(String(12))                      # production | idle | rework | rejection
    description: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(20))           # idle only: breakdown|maintenance|tooling|material|utilities|people|other


# ------------------------------------------------------------------ cards

class JobCard(Base):
    __tablename__ = "job_cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_ref: Mapped[str] = mapped_column(String(40), index=True)      # C04 | SYN-000123
    source: Mapped[str] = mapped_column(String(12))                    # photo | synthetic
    status: Mapped[str] = mapped_column(String(16), index=True)        # processing | needs_review | approved | failed
    image_path: Mapped[str | None] = mapped_column(Text)
    card_date: Mapped[date | None] = mapped_column(Date, index=True)   # parsed from header.date
    mc_no: Mapped[str | None] = mapped_column(String(16), index=True)  # normalised, as matched
    emp_no: Mapped[str | None] = mapped_column(String(12), index=True) # first row's emp_no (one operator per card)
    shift: Mapped[str | None] = mapped_column(String(2))
    header: Mapped[dict] = mapped_column(JSONB, default=dict)          # as written: date, component_description, cc, operation_description, mc_no
    total_hours: Mapped[str | None] = mapped_column(String(10))        # as written
    flags: Mapped[list] = mapped_column(JSONB, default=list)           # validate() output
    extracted: Mapped[dict | None] = mapped_column(JSONB)              # raw model output (photo cards)
    read_model: Mapped[str | None] = mapped_column(String(80))
    read_seconds: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(60))

    rows: Mapped[list["CardRow"]] = relationship(
        back_populates="card", cascade="all, delete-orphan", order_by="CardRow.row_no")


class CardRow(Base):
    __tablename__ = "card_rows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("job_cards.id", ondelete="CASCADE"), index=True)
    row_no: Mapped[int] = mapped_column(Integer)                       # 1-based
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)             # the 14 fields as written + "unclear": [...]
    # normalised (NULL when blank or unreadable)
    emp_no: Mapped[str | None] = mapped_column(String(12), index=True)
    shift: Mapped[str | None] = mapped_column(String(2))
    opn_code: Mapped[str | None] = mapped_column(String(12), index=True)
    wo_no: Mapped[str | None] = mapped_column(String(30))
    comp_code: Mapped[str | None] = mapped_column(String(12))
    qty_prod: Mapped[int | None] = mapped_column(Integer)
    qty_accp: Mapped[int | None] = mapped_column(Integer)
    rej_code: Mapped[str | None] = mapped_column(String(6))
    rej_qty: Mapped[int | None] = mapped_column(Integer)
    rework_code: Mapped[str | None] = mapped_column(String(6))
    rework_qty: Mapped[int | None] = mapped_column(Integer)
    time_from: Mapped[str | None] = mapped_column(String(8))
    time_to: Mapped[str | None] = mapped_column(String(8))
    minutes: Mapped[int | None] = mapped_column(Integer)               # duration of the row (from/to; else total_hours)

    card: Mapped[JobCard] = relationship(back_populates="rows")


class ReviewLog(Base):
    __tablename__ = "review_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("job_cards.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(16))                    # edit | approve
    field: Mapped[str | None] = mapped_column(String(60))              # rows[0].opn_code | header.mc_no
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    by: Mapped[str] = mapped_column(String(60), default="supervisor")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatLog(Base):
    __tablename__ = "chat_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    route: Mapped[str | None] = mapped_column(String(10))
    sql: Mapped[str | None] = mapped_column(Text)
    sql_valid: Mapped[bool | None] = mapped_column(Boolean)
    row_count: Mapped[int | None] = mapped_column(Integer)
    answer: Mapped[str | None] = mapped_column(Text)
    view: Mapped[dict | None] = mapped_column(JSONB)
    numbers_match: Mapped[bool | None] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)
    ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
