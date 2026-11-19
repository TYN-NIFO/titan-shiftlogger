"""Chat tests: SQL guard, numbers check, and the 3 demo questions in stub mode (rows from the DB)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.services.numbers_check import check
from app.services.sql_guard import SQLRejected, guard
from tests.conftest import HIGH_PRODUCER, LOW_PRODUCER, OTHER_CNC, TOP_ABSENT, TOP_CNC

ANSWER_KEYS = {"route", "text", "view", "columns", "rows", "sql", "checks", "ms"}


# ------------------------------------------------------------------ sql guard

@pytest.mark.parametrize("sql", [
    "UPDATE job_cards SET status = 'approved'",
    "DELETE FROM codes",
    "DROP TABLE codes",
    "INSERT INTO codes VALUES ('1', 'idle', 'x', NULL)",
    "SELECT 1; SELECT 2",
    "SELECT * FROM v_downtime; DELETE FROM codes",
    "SELECT pg_sleep(10)",
    "SELECT * FROM v_downtime WHERE pg_sleep(1) IS NULL",
    "SELECT * FROM job_cards",
    "SELECT * FROM card_rows",
    "SELECT * FROM review_log",
    "SELECT * FROM v_downtime d JOIN job_cards j ON j.mc_no = d.mc_no",
    "SELECT * FROM pg_catalog.pg_roles",
    "SELECT * FROM information_schema.tables",
    "WITH d AS (DELETE FROM codes RETURNING *) SELECT * FROM d",
    "SELECT * INTO new_t FROM codes",
    "SELECT * FROM codes FOR UPDATE",
    "SELECT current_setting('server_version')",
    "",
    "this is not sql",
])
def test_guard_rejects(sql):
    with pytest.raises(SQLRejected):
        guard(sql)


def test_guard_accepts_and_limits():
    out = guard("SELECT mc_no, SUM(hours) AS h FROM v_downtime WHERE is_cnc GROUP BY mc_no ORDER BY h DESC")
    assert out.endswith("LIMIT 200")
    assert guard("SELECT * FROM v_absenteeism LIMIT 5").endswith("LIMIT 5")
    assert guard("SELECT * FROM v_absenteeism LIMIT 5000").endswith("LIMIT 200")
    assert "LIMIT 200" in guard("WITH t AS (SELECT * FROM v_production) SELECT emp_no FROM t")
    assert guard("SELECT m.mc_no FROM machines m JOIN v_downtime d ON d.mc_no = m.mc_no;")


# ------------------------------------------------------------------ numbers check

def test_numbers_check_exact_and_rounding():
    rows = [["604021.05", 61.47], ["604021.03", 33.0]]
    assert check("604021.05 lost the most: 61.5 hours, then 604021.03 with 33 hours.", rows)[0]
    assert check("604021.05 lost 61.47 hours.", rows)[0]


def test_numbers_check_rejects_invented():
    rows = [["604021.05", 61.47], ["604021.03", 33.0]]
    ok, bad = check("604021.05 lost 72.4 hours, 28.5 more than the next machine.", rows)
    assert not ok and bad == ["72.4", "28.5"]


def test_numbers_check_question_and_counts():
    rows = [["280419", 14], ["280671", 13], ["280999", 12]]
    assert check("Over the last 4 months, the top 3 are 280419 (14), 280671 (13) and 280999 (12).",
                 rows, "Who has the highest absenteeism in the last 4 months?")[0]
    assert not check("The top 3 are 280419 with 15 shifts.", rows)[0]


def test_numbers_check_dates_and_thousands():
    rows = [["2026-11-14", 1234]]
    assert check("On 14 Nov 2026 the accepted quantity was 1,234.", rows)[0]
    assert check("No matching records were found.", [])[0]


# ------------------------------------------------------------------ chat (stub)

def _ask(client, q):
    r = client.post("/api/chat", json={"question": q, "history": []})
    assert r.status_code == 200, r.text
    a = r.json()
    assert set(a) >= ANSWER_KEYS
    return a


def test_chat_cnc_breakdowns(client):
    a = _ask(client, "Which CNC machine lost the most hours to breakdowns in the last four months?")
    assert a["route"] == "data"
    assert a["view"]["type"] == "bar" and a["view"]["x"] == "mc_no" and a["view"]["y"] == "breakdown_hours"
    assert a["columns"] == ["mc_no", "machine_name", "breakdown_hours"]
    assert a["rows"][0] == [TOP_CNC, "CNC case milling 1", 18.0]
    assert a["rows"][1][0] == OTHER_CNC and a["rows"][1][2] == 6.0 and a["rows"][1][1]
    assert len(a["rows"]) == 2                      # Press machines are not CNC
    assert a["checks"] == {"sql_valid": True, "numbers_match": True}
    assert f"{TOP_CNC} (CNC case milling 1)" in a["text"] and "18" in a["text"]
    assert a["sql"].startswith("SELECT") and "LIMIT 200" in a["sql"]


def test_chat_absenteeism(client):
    a = _ask(client, "Who has the highest absenteeism?")
    assert a["view"]["type"] == "table"
    assert a["columns"] == ["emp_no", "emp_name", "absent_shifts"]
    assert a["view"]["x"] == "emp_no" and a["view"]["y"] == "absent_shifts"
    # 4 seeded absences (+1 if the API tests approved the C04 photo card, which is also 280419 / 10813)
    name = a["rows"][0][1]
    assert a["rows"][0][0] == TOP_ABSENT and name and a["rows"][0][2] in (4, 5)
    assert a["rows"][1][0] == "280671" and a["rows"][1][2] == 2
    assert a["checks"]["numbers_match"] is True and f"{name} ({TOP_ABSENT})" in a["text"]


def test_chat_least_productive(client):
    a = _ask(client, "Who's least productive?")
    assert a["view"]["type"] == "table" and a["view"]["y"] == "efficiency_pct"
    assert a["rows"][0][0] == LOW_PRODUCER
    assert a["columns"][:2] == ["emp_no", "emp_name"] and a["columns"][-1] == "efficiency_pct"
    assert all(r[1] for r in a["rows"])
    eff = a["columns"].index("efficiency_pct")
    assert a["rows"][0][eff] < a["rows"][-1][eff]
    assert a["rows"][-1][0] == HIGH_PRODUCER
    assert a["checks"]["numbers_match"] is True


def test_chat_other_question_in_stub(client):
    a = _ask(client, "How do I reset the hydraulic press?")
    assert a["route"] == "chat" and "stub" in a["text"].lower()
    assert a["rows"] == [] and a["view"]["type"] is None


def test_chat_logged(client, database):
    from app.db.models import ChatLog
    from app.db.session import SessionLocal

    _ask(client, "Who has the highest absenteeism?")
    with SessionLocal() as db:
        last = db.scalars(select(ChatLog).order_by(ChatLog.id.desc()).limit(1)).one()
        assert last.route == "data" and last.sql_valid and last.row_count >= 3 and last.numbers_match
        assert last.ms is not None and last.view["type"] == "table"


def test_chat_role_is_read_only(database):
    from app.services.chat import run_sql
    with pytest.raises(Exception):
        run_sql("SELECT * FROM job_cards")           # base tables are not granted
    with pytest.raises(Exception):
        run_sql("DELETE FROM codes")                 # read-only transaction + role


def test_chat_sql_with_percent_signs(database):
    from app.services.chat import run_sql
    cols, rows = run_sql(guard("SELECT emp_no FROM employees WHERE emp_no LIKE '%2804%' ORDER BY emp_no"))
    assert cols == ["emp_no"] and ["280419"] in rows


def test_chat_fallback_text():
    from app.services.chat import fallback_text
    t = fallback_text(["mc_no", "breakdown_hours"], [["604021.05", 61.5], ["604021.03", 33.0]])
    assert check(t, [["604021.05", 61.5], ["604021.03", 33.0]])[0]
    assert "604021.05" in t


# ------------------------------------------------------------------ live pipeline with a fake LLM

class FakeLLM:
    """Replays canned JSON replies per step (router / sql / answer) and records the prompts."""

    def __init__(self, replies):
        self.replies = {k: list(v) for k, v in replies.items()}
        self.prompts = []

    def __call__(self, prompt, schema, system=None, model=None, num_predict=1024):
        self.prompts.append(prompt)
        step = "router" if "route" in schema["properties"] else "sql" if "sql" in schema["properties"] else "answer"
        return self.replies[step].pop(0)


def test_live_pipeline_with_fake_llm(client, monkeypatch):
    from app.services import chat, llm
    fake = FakeLLM({
        "router": [{"route": "data", "reply": ""}],
        "sql": [{"sql": "SELECT * FROM job_cards"},                         # rejected -> retried
                {"sql": "SELECT mc_no, ROUND(SUM(hours)::numeric, 1) AS breakdown_hours FROM v_downtime "
                        "WHERE is_cnc AND category = 'breakdown' GROUP BY mc_no ORDER BY 2 DESC"}],
        "answer": [{"text": f"{TOP_CNC} lost 99.9 hours.", "view": {"type": "bar", "x": "mc_no",
                                                                    "y": "breakdown_hours", "title": "t"}},
                   {"text": f"{TOP_CNC} lost 18 hours.", "view": {"type": "bar", "x": "mc_no",
                                                                  "y": "breakdown_hours", "title": "t"}}],
    })
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setattr(llm, "chat_json", fake)
    a = chat.answer("Which CNC machine had the most breakdown hours?", [])
    assert a["route"] == "data" and a["text"] == f"{TOP_CNC} lost 18 hours."
    assert a["checks"] == {"sql_valid": True, "numbers_match": True}
    assert a["rows"][0] == [TOP_CNC, 18.0] and a["view"]["type"] == "bar"
    assert "v_downtime(" in fake.prompts[1] and "2026-11-18" in fake.prompts[1]
    assert "rejected by the safety check" in fake.prompts[2]


def test_live_numbers_fallback_and_errors(client, monkeypatch):
    from app.services import chat, llm
    bad = {"text": "It lost 123.4 hours.", "view": {"type": "null", "x": "", "y": "", "title": ""}}
    fake = FakeLLM({"router": [{"route": "data", "reply": ""}],
                    "sql": [{"sql": "SELECT emp_no, COUNT(*) AS absent_shifts FROM v_absenteeism "
                                    "GROUP BY emp_no ORDER BY 2 DESC"}],
                    "answer": [bad, bad]})
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setattr(llm, "chat_json", fake)
    a = chat.answer("Who has the highest absenteeism?", [])
    assert a["checks"]["numbers_match"] is False and a["checks"]["fallback_text"] is True
    assert TOP_ABSENT in a["text"] and "123.4" not in a["text"]
    assert check(a["text"], a["rows"])[0]
    assert a["view"]["type"] == "bar"                 # "null" from the AI -> default view for 2 columns

    def down(*_a, **_k):
        raise llm.LLMError("ConnectError: refused")
    monkeypatch.setattr(llm, "chat_json", down)
    a = chat.answer("Who has the highest absenteeism?", [])
    assert "not reachable" in a["text"] and a["rows"] == []

    chat_fake = FakeLLM({"router": [{"route": "chat", "reply": "Hello! Ask me about 42 things."}]})
    monkeypatch.setattr(llm, "chat_json", chat_fake)
    a = chat.answer("hi", [])
    assert a["route"] == "chat" and "42" not in a["text"]


def test_numbers_check_ignores_digits_in_name_columns():
    from app.services.numbers_check import check
    cols = ["mc_no", "machine_name", "breakdown_hours"]
    rows = [["604020.08", "Hydraulic press 100T", 12.5]]
    # the name's "100" is not a figure: inventing 100 hours must fail
    assert check("604020.08 lost 100 hours.", rows, "", cols)[0] is False
    # the name itself in the text is fine
    assert check("604020.08 (Hydraulic press 100T) lost 12.5 hours.", rows, "", cols)[0] is True
