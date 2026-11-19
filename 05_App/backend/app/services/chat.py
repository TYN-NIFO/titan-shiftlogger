"""Chat pipeline: router -> SQL -> guard -> run read-only -> answer -> numbers check -> chat_log.

Numbers in an answer always come from SQL rows. The AI writes the SQL and the sentence; the
database produces the numbers, and numbers_check.py rejects any sentence with a number the rows
do not contain.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from app.core.reading.common import master_data
from app.db.models import ChatLog
from app.db.session import SessionLocal, chat_engine, engine
from app.services import config, llm, numbers_check
from app.services.sql_guard import ALLOWED_RELATIONS, SQLRejected, guard

log = logging.getLogger("titan.chat")

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
VIEW_TYPES = ("bar", "line", "table", "kpi")
SORRY = ("Sorry, I couldn't answer that just now. Please try again, or rephrase the question "
         "(for example: \"Which CNC machine lost the most hours to breakdowns?\").")

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {"route": {"type": "string", "enum": ["data", "chat"]}, "reply": {"type": "string"}},
    "required": ["route", "reply"],
}
SQL_SCHEMA = {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "view": {"type": "object", "properties": {
            "type": {"type": "string", "enum": [*VIEW_TYPES, "null"]},
            "x": {"type": "string"}, "y": {"type": "string"}, "title": {"type": "string"}},
            "required": ["type", "x", "y", "title"]},
    },
    "required": ["text", "view"],
}

# ------------------------------------------------------------------ the 3 demo questions
# Used as few-shot examples in the live SQL prompt, and as canned answers in stub mode (tests only).

DEMO = [
    {
        "key": "cnc_breakdown",
        "match": lambda q: "cnc" in q and ("breakdown" in q or "lost" in q or "downtime" in q),
        "question": "Which CNC machine lost the most hours to breakdowns in the last four months?",
        "sql": ("SELECT mc_no, machine_name, ROUND(SUM(hours)::numeric, 1) AS breakdown_hours FROM v_downtime "
                "WHERE is_cnc AND category = 'breakdown' "
                "AND card_date >= DATE '2026-11-18' - INTERVAL '4 months' "
                "GROUP BY mc_no, machine_name ORDER BY breakdown_hours DESC"),
        "view": {"type": "bar", "x": "mc_no", "y": "breakdown_hours", "title": "Breakdown hours by CNC machine"},
    },
    {
        "key": "absenteeism",
        "match": lambda q: "absent" in q,
        "question": "Who has the highest absenteeism?",
        "sql": ("SELECT emp_no, emp_name, COUNT(*) AS absent_shifts FROM v_absenteeism "
                "GROUP BY emp_no, emp_name ORDER BY absent_shifts DESC, emp_no LIMIT 10"),
        "view": {"type": "table", "x": "emp_no", "y": "absent_shifts", "title": "Absent shifts by operator"},
    },
    {
        "key": "least_productive",
        "match": lambda q: "productive" in q or "productivity" in q or "efficien" in q,
        "question": "Who's least productive?",
        "sql": ("SELECT emp_no, emp_name, shift, ROUND(productive_hours::numeric, 1) AS productive_hours, "
                "qty_accp, ROUND(efficiency_pct::numeric, 1) AS efficiency_pct "
                "FROM v_operator_productivity WHERE std_qty > 0 "
                "ORDER BY efficiency_pct ASC, emp_no LIMIT 10"),
        "view": {"type": "table", "x": "emp_no", "y": "efficiency_pct",
                 "title": "Least productive operators (efficiency vs standard)"},
    },
]
EXTRA_EXAMPLES = [
    ("Downtime by reason on Press machines last month",
     "SELECT reason, ROUND(SUM(hours)::numeric, 1) AS hours FROM v_downtime WHERE machine_type = 'Press' "
     "AND card_date >= DATE '2026-11-18' - INTERVAL '1 month' GROUP BY reason ORDER BY hours DESC LIMIT 10"),
    ("Accepted quantity per week",
     "SELECT date_trunc('week', card_date)::date AS week, SUM(qty_accp) AS qty_accp FROM v_production "
     "GROUP BY week ORDER BY week"),
]


def _machine(mc_no, name) -> str:
    """'604021.05 (CNC case milling 1)'; just the number when there is no name."""
    return f"{mc_no} ({name})" if name else str(mc_no)


def _person(emp_no, name) -> str:
    """'Ravi K. (280419)'; just the Emp No when there is no name."""
    return f"{name} ({emp_no})" if name else str(emp_no)


def _stub_text(key: str, cols: list, rows: list) -> str:
    # Rows are [id, name, ..., value]: the id first, its display name second, the number last.
    if not rows:
        return "No matching records were found."
    if key == "cnc_breakdown":
        t = f"{_machine(rows[0][0], rows[0][1])} lost the most time to breakdowns: {_fmt(rows[0][-1])} hours."
        if len(rows) > 1:
            t += f" Next is {_machine(rows[1][0], rows[1][1])} with {_fmt(rows[1][-1])} hours."
        return t
    if key == "absenteeism":
        top = ", ".join(f"{_person(r[0], r[1])}: {_fmt(r[-1])} shifts" for r in rows[:3])
        return f"Highest absenteeism: {top}."
    if key == "least_productive":
        low = ", ".join(f"{_person(r[0], r[1])}: {_fmt(r[-1])}%" for r in rows[:3])
        return f"Least productive against the standard rate: {low}."
    return fallback_text(cols, rows)


# ------------------------------------------------------------------ helpers

def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.1f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return str(v)


def _cell(v):
    if isinstance(v, Decimal):
        f = float(v)
        return int(f) if f == int(f) and v.as_tuple().exponent >= 0 else round(f, 2)
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if v is None or isinstance(v, (int, str, bool)):
        return v
    return str(v)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _history_text(history: list[dict] | None) -> str:
    lines = []
    for h in (history or [])[-6:]:
        role = "Manager" if str(h.get("role", "")).lower() == "user" else "Assistant"
        lines.append(f"{role}: {str(h.get('text', ''))[:400]}")
    return "\n".join(lines) or "(none)"


def default_view(cols: list, rows: list) -> dict:
    if not rows:
        return {"type": None, "x": "", "y": "", "title": ""}
    if len(rows) == 1 and len(cols) == 1 and _is_num(rows[0][0]):
        return {"type": "kpi", "x": "", "y": cols[0], "title": cols[0].replace("_", " ").capitalize()}
    # [label, number] or [id, name, number] (e.g. mc_no, machine_name, breakdown_hours)
    named = len(cols) == 3 and cols[1].endswith("_name")
    if (len(cols) == 2 or named) and all(_is_num(r[-1]) for r in rows) and len(rows) <= 15:
        return {"type": "bar", "x": cols[0], "y": cols[-1],
                "title": f"{cols[-1].replace('_', ' ').capitalize()} by {cols[0].replace('_', ' ')}"}
    num_i = next((i for i in range(1, len(cols)) if all(_is_num(r[i]) for r in rows)), None)
    y = cols[num_i] if num_i is not None else (cols[1] if len(cols) > 1 else "")
    return {"type": "table", "x": cols[0], "y": y, "title": ""}


def clean_view(v: dict | None, cols: list, rows: list) -> dict:
    if not isinstance(v, dict):
        return default_view(cols, rows)
    t = v.get("type")
    t = t if t in VIEW_TYPES else None
    x, y = str(v.get("x") or ""), str(v.get("y") or "")
    title = str(v.get("title") or "")[:120]
    if t in ("bar", "line") and (x not in cols or y not in cols):
        return default_view(cols, rows)
    if t == "kpi" and y not in cols:
        y = next((c for i, c in enumerate(cols) if rows and _is_num(rows[0][i])), "")
        if not y:
            return default_view(cols, rows)
    if t is None and rows:
        return default_view(cols, rows)
    return {"type": t, "x": x if x in cols else "", "y": y if y in cols else "", "title": title}


def fallback_text(cols: list, rows: list) -> str:
    """Deterministic answer from the top rows (used when the AI's sentence fails the numbers check)."""
    if not rows:
        return "No matching records were found."
    num_i = next((i for i in range(1, len(cols)) if all(_is_num(r[i]) for r in rows)), None)
    if len(cols) == 1:
        return f"{cols[0].replace('_', ' ').capitalize()}: {_fmt(rows[0][0])}."
    if num_i is None:
        return "Top results: " + "; ".join(", ".join(_fmt(c) for c in r) for r in rows[:3]) + "."
    label = cols[num_i].replace("_", " ")
    named = len(cols) > 1 and cols[1].endswith("_name") and num_i != 1

    def who(r) -> str:
        if not named or not r[1]:
            return _fmt(r[0])
        return _person(r[0], r[1]) if cols[0] == "emp_no" else _machine(r[0], r[1])
    items = ", ".join(f"{who(r)}: {_fmt(r[num_i])}" if named else f"{_fmt(r[0])} ({_fmt(r[num_i])})"
                      for r in rows[:3])
    return f"Top results by {label}: {items}."


_schema_cache: dict[str, str] = {}


def views_ddl() -> str:
    """Column lists of the allowed relations, read from the database."""
    if "ddl" in _schema_cache:
        return _schema_cache["ddl"]
    with engine.connect() as c:
        res = c.execute(text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ANY(:names) "
            "ORDER BY table_name, ordinal_position"), {"names": sorted(ALLOWED_RELATIONS)}).all()
    tables: dict[str, list[str]] = {}
    for t, col, typ in res:
        tables.setdefault(t, []).append(f"{col} {typ}")
    ddl = "\n".join(f"  {t}({', '.join(cols)})" for t, cols in tables.items())
    if tables:
        _schema_cache["ddl"] = ddl
    return ddl or "  (views not created yet)"


def code_meanings() -> str:
    if "codes" in _schema_cache:
        return _schema_cache["codes"]
    lines = []
    try:
        with engine.connect() as c:
            for code, kind, desc, cat in c.execute(text(
                    "SELECT code, kind, description, category FROM codes "
                    "WHERE kind IN ('production', 'idle') ORDER BY code")):
                lines.append(f"  {code} = {desc}" + (f" [{cat}]" if cat else f" [{kind}]"))
    except Exception:  # noqa: BLE001
        lines = []
    if not lines:
        md = master_data()
        lines = [f"  {k} = {v}" for k, v in {**md["production_codes"], **md["idle_codes"]}.items()]
    else:
        _schema_cache["codes"] = "\n".join(lines)
    return "\n".join(lines)


def _examples() -> str:
    pairs = [(d["question"], d["sql"]) for d in DEMO] + EXTRA_EXAMPLES
    return "\n".join(f"Q: {q}\nSQL: {s}" for q, s in pairs)


def run_sql(sql: str) -> tuple[list[str], list[list]]:
    """Run guarded SQL as the read-only role, in a read-only transaction with a 5 s timeout."""
    # Raw driver cursor with no parameters, so '%' in LIKE patterns is not read as a placeholder.
    with chat_engine.connect() as c:
        raw = c.connection.driver_connection
        try:
            with raw.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(sql)
                cols = [d.name for d in cur.description or []]
                rows = [[_cell(v) for v in r] for r in cur.fetchmany(200)]
        finally:
            raw.rollback()
    return cols, rows


# ------------------------------------------------------------------ pipeline

def _empty(route: str, text_: str, sql=None, sql_valid=False, numbers_match=True) -> dict:
    return {"route": route, "text": text_, "view": {"type": None, "x": "", "y": "", "title": ""},
            "columns": [], "rows": [], "sql": sql,
            "checks": {"sql_valid": sql_valid, "numbers_match": numbers_match}, "ms": 0}


def _route(question: str, history) -> tuple[str, str]:
    prompt = (PROMPTS / "router.txt").read_text(encoding="utf-8").format(
        question=question, history=_history_text(history))
    r = llm.chat_json(prompt, ROUTER_SCHEMA, num_predict=256)
    route = r.get("route") if r.get("route") in ("data", "chat") else "data"
    reply = str(r.get("reply") or "").strip()
    if route == "chat" and (not reply or re.search(r"\d", reply)):
        reply = ("I answer questions about the job-card data: downtime, breakdowns, production, "
                 "rejections, absenteeism and operator productivity.")
    return route, reply


def _write_sql(question: str, history, error: str | None = None) -> str:
    prompt = (PROMPTS / "sql.txt").read_text(encoding="utf-8").format(
        ddl=views_ddl(), today=config.TODAY, codes=code_meanings(), examples=_examples(),
        history=_history_text(history), question=question)
    if error:
        prompt += f"\n\nYour previous query failed: {error}\nWrite a corrected query."
    return str(llm.chat_json(prompt, SQL_SCHEMA, num_predict=768).get("sql") or "")


def _write_answer(question: str, sql: str, cols: list, rows: list, feedback: str = "") -> dict:
    prompt = (PROMPTS / "answer.txt").read_text(encoding="utf-8").format(
        question=question, sql=sql, row_count=len(rows), columns=", ".join(cols),
        rows="\n".join(json.dumps(r, ensure_ascii=False) for r in rows[:40]) or "(no rows)",
        feedback=feedback)
    return llm.chat_json(prompt, ANSWER_SCHEMA, num_predict=512)


def _stub(question: str, rec: dict) -> dict:
    q = question.lower()
    demo = next((d for d in DEMO if d["match"](q)), None)
    if demo is None:
        rec["route"] = "chat"
        return _empty("chat", "This question isn't available in stub mode: the AI is not connected. "
                              "Try one of the three demo questions.")
    rec["route"] = "data"
    safe = guard(demo["sql"])
    rec["sql"], rec["sql_valid"] = safe, True
    cols, rows = run_sql(safe)
    rec["row_count"] = len(rows)
    txt = _stub_text(demo["key"], cols, rows)
    ok, _ = numbers_check.check(txt, rows, question, cols)
    if not ok:
        txt = fallback_text(cols, rows)
    rec["numbers_match"] = ok
    view = clean_view(demo["view"], cols, rows)
    return {"route": "data", "text": txt, "view": view, "columns": cols, "rows": rows, "sql": safe,
            "checks": {"sql_valid": True, "numbers_match": ok}, "ms": 0}


def _live(question: str, history, rec: dict) -> dict:
    route, reply = _route(question, history)
    rec["route"] = route
    if route == "chat":
        return _empty("chat", reply)

    # SQL: write, guard, run; one retry with the error fed back.
    error, safe, cols, rows = None, None, [], []
    for _ in range(2):
        sql = _write_sql(question, history, error)
        rec["sql"] = sql
        try:
            safe = guard(sql)
            rec["sql"], rec["sql_valid"] = safe, True
            cols, rows = run_sql(safe)
            error = None
            break
        except SQLRejected as e:
            error, safe = f"rejected by the safety check: {e}", None
            rec["sql_valid"] = False
        except Exception as e:  # noqa: BLE001 - database error: let the model correct it once
            error = f"database error: {str(e).splitlines()[0][:300]}"
    if error:
        rec["error"] = error
        return _empty("data", "I couldn't turn that question into a safe query on the job-card data. "
                              "Please try rephrasing it.", sql=rec.get("sql"),
                      sql_valid=bool(rec.get("sql_valid")))
    rec["row_count"] = len(rows)

    # Answer + numbers check, one retry, then a deterministic text from the rows.
    ans, ok, fallback = {}, False, False
    feedback = ""
    for _ in range(2):
        try:
            ans = _write_answer(question, safe, cols, rows, feedback)
        except llm.LLMError as e:
            rec["error"] = f"answer: {e}"
            break
        ok, bad = numbers_check.check(str(ans.get("text") or ""), rows, question, cols)
        if ok and str(ans.get("text") or "").strip():
            break
        feedback = (f"\nYour previous text used numbers that are not in the result: {', '.join(bad)}. "
                    "Use only numbers copied from the result.")
        ok = False
    txt = str(ans.get("text") or "").strip()
    if not ok or not txt:
        txt, fallback = fallback_text(cols, rows), True
    rec["numbers_match"] = ok
    view = clean_view(ans.get("view"), cols, rows)
    checks = {"sql_valid": True, "numbers_match": ok}
    if fallback:
        checks["fallback_text"] = True
    return {"route": "data", "text": txt, "view": view, "columns": cols, "rows": rows, "sql": safe,
            "checks": checks, "ms": 0}


def answer(question: str, history: list[dict] | None = None) -> dict:
    t0 = time.perf_counter()
    question = (question or "").strip()[:1000]
    rec: dict = {"route": None, "sql": None, "sql_valid": None, "row_count": None,
                 "numbers_match": None, "error": None}
    if not question:
        out = _empty("chat", "Please type a question.")
    else:
        try:
            out = _stub(question, rec) if config.llm_mode() == "stub" else _live(question, history, rec)
        except llm.LLMError as e:
            log.warning("chat LLM error: %s", e)
            rec["error"] = str(e)
            out = _empty(rec.get("route") or "data",
                         "The AI service is not reachable right now. Please try again in a moment.",
                         sql=rec.get("sql"), sql_valid=bool(rec.get("sql_valid")))
        except Exception as e:  # noqa: BLE001 - never leak an exception to the user
            log.exception("chat failed")
            rec["error"] = f"{type(e).__name__}: {e}"
            out = _empty(rec.get("route") or "data", SORRY, sql=rec.get("sql"),
                         sql_valid=bool(rec.get("sql_valid")))
    out["ms"] = int((time.perf_counter() - t0) * 1000)
    try:
        with SessionLocal() as db:
            db.add(ChatLog(question=question, route=out["route"], sql=rec.get("sql"),
                           sql_valid=rec.get("sql_valid"), row_count=rec.get("row_count"),
                           answer=out["text"], view=out["view"], numbers_match=rec.get("numbers_match"),
                           error=(rec.get("error") or None) and str(rec["error"])[:4000], ms=out["ms"]))
            db.commit()
    except Exception:  # noqa: BLE001
        log.exception("could not write chat_log")
    return out
