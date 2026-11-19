# 05_App: build contract (shared by every agent; change only via the lead)

PoC for the 1:30 demo video (`05_Demo_Video/Titan_demo_video_script.md`, FINAL section).

Screens the video needs:
1. Upload a photo card, then see it read: photo beside the fields.
2. Chat: 3 questions answered with text + bar chart / ranked table + "Show details" (SQL + rows).
3. Flags on C04 and C08.
4. Review: correct, then Approve.
5. Card list with statuses.

Not in scope: login, manual/RAG, pgvector (no manuals in this video).

## Ground rules
- **Synthetic data only.** Never real Titan cards, names or documents. Operators and machines carry made-up sample names (master_data.json `employee_names`, `machine_names`); answers show "name (id)". The real system takes names from Titan's HR and machine masters.
- **No numbers invented by the LLM.** Chat numbers come from SQL rows only, and the backend checks every number in the answer text against the rows.
- **The model is never named in the UI.** Say "AI".
- **Local dev (Windows laptop):**
  - Python 3.10 via `uv`, venv in `05_App/backend/.venv`; Node 22 + npm.
  - Postgres 16 is already running at `localhost:5432` (user `postgres`, password `password`), database `titan_shiftlogger`.
- **The LLM is not on the laptop.** Ollama runs on the GPU server and is reached through `OLLAMA_HOST` (an SSH tunnel at demo time).
  - Model tag: `qwen3.8:27b-q4_K_M` for both reading and chat. Settings from the bake-off: think off, temperature 0, `num_ctx` 8192, valid-value lists in the prompt.
  - `LLM_MODE=stub` exists **for automated tests only** (canned SQL/answers for the 3 demo questions; canned extraction = the answer-key reading). The UI must never say it's live when in stub mode: the `/api/health` response has `llm_mode`, and the frontend shows a small "STUB" badge if it isn't `live`.

## Ports and env (`05_App/.env.example`)
```
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/titan_shiftlogger
CHAT_DATABASE_URL=postgresql+psycopg://titan_chat_ro:titan_chat_ro@localhost:5432/titan_shiftlogger
OLLAMA_HOST=http://localhost:11434
READ_MODEL=qwen3.8:27b-q4_K_M
CHAT_MODEL=qwen3.8:27b-q4_K_M
LLM_MODE=live            # live | stub (tests only)
UPLOAD_DIR=05_App/backend/storage/cards
NEXT_PUBLIC_API_URL=http://localhost:8000
```
Backend: `uvicorn app.main:app --port 8000` from `05_App/backend`. Frontend: `npm run dev` on port 3000. CORS allows `http://localhost:3000`.

## Folder ownership (each agent writes only its own folders)
```
05_App/
  CONTRACT.md, .env.example                     lead
  backend/app/db/models.py                      lead (written; ask before changing)
  backend/app/db/session.py                     lead
  backend/app/db/sql/                           DATA agent: 001_schema.sql, 002_views.sql, 003_readonly_role.sql
  backend/app/core/reading/                     DATA agent: master_data.json (expanded), copied from 04_PoC/bakeoff
  backend/scripts/                              DATA agent: init_db.py, generate_synthetic.py, seed_photo_cards.py
  backend/tests/test_data.py, expected_answers.json   DATA agent
  backend/app/main.py, app/api/, app/services/  BACKEND agent
  backend/pyproject.toml, backend/tests/test_api.py, test_chat.py   BACKEND agent
  frontend/                                     FRONTEND agent
```

## Data (DATA agent)

### Master data
`backend/app/core/reading/master_data.json` is a copy of `04_PoC/bakeoff/data/master_data.json`, expanded as follows.
- **Keep** the 8 existing employees, 4 machines and 4 components exactly.
- **Add made-up employees** to reach **80**. 6-digit numbers between 279800 and 280999. **Never 999999**: C09 must stay unknown.
- **Add machines** to reach **12**: 7 Press (`604020.xx`) and 5 CNC (`604021.xx`).
  - No new machine may have digits equal to `60402008` once the dot is removed. C05 must still match 604020.08.
- **Add 4 components**, giving 8 in total.
- **The 10-card self-test must still pass.** Run `python 04_PoC/bakeoff/run_bakeoff.py --self-test` and `python 04_PoC/bakeoff/validate.py` against the **expanded** file: copy, then point at it with a temporary edit or a param, and don't commit the bake-off change. The result must be 10/10 flags exact, 0 missed reviews.
- The tables `employees`, `machines`, `components` and `codes` are loaded from this file.

### Synthetic history (`scripts/generate_synthetic.py --seed 42`)
- **Period:** 2026-07-20 to 2026-11-14, Mon–Sat, shifts A and B.
- **Operators:** about 40 per shift. Each operator stays on one shift and one main machine, with an occasional move.
- **One card per operator per shift-day.**
  - Rows follow the real pattern: production rows with code `10202` plus `comp_code`/qty, and idle rows with an idle code and no qty. Times are 12-h `h.mm`.
  - Rows add up to **8.00 paid hours**: shift span minus the 30-min break, as in `validate.py`.
- **Absent operator:** a single row with `10813`, 8.00 h, no qty.
- **The generated cards are clean:** `validate()` must return no flags. They are inserted with `source='synthetic'`, `status='approved'` and `image_path=NULL`.
- **Planted patterns** (the demo answers must be obvious):
  1. CNC **604021.05** has clearly the most breakdown hours (10803 + 10804) over the whole period: about 1.5–2× the next CNC machine.
  2. Three operators have clearly the highest absenteeism: **280419**, **280671**, and one new ID. That's about 12–15 absent shifts each, against a median of about 3.
  3. Productivity (accepted qty per productive hour, per component standard) varies by about ±25%. 3 operators are clearly lowest. A component's standard rate is stored in `components.std_rate_per_hour`.
  4. Some realistic noise: preventive maintenance, no tool, cleaning, training, and a few rejections and reworks.
- **`backend/tests/expected_answers.json`:** the generator computes the true answers to the 3 demo questions from its own data, through the views. Questions and the "last 4 months" window are listed below.
- **`scripts/seed_photo_cards.py` (optional demo state):** inserts C01, C03, C05, C06, C07, C09 and C10 from `04_PoC/bakeoff/data/answer_key.json` (as written) with `source='photo'`, the image copied to `UPLOAD_DIR`, flags from `validate()`, and status `needs_review` if flagged, otherwise `approved`.
  - **C02, C04 and C08 are left out**, because they're uploaded live in the video.

### SQL (`app/db/sql/`, run by `scripts/init_db.py`, which is idempotent: drop and recreate)
- `001_schema.sql` must match `models.py`.
- `002_views.sql`: **approved cards only.** All hours are decimal hours, from `card_rows.minutes / 60.0`.
  - `v_production(card_date, shift, emp_no, mc_no, machine_type, is_cnc, comp_code, qty_prod, qty_accp, rej_qty, rework_qty, hours)`: rows with production codes only.
  - `v_downtime(card_date, shift, emp_no, mc_no, machine_type, is_cnc, code, reason, category, hours)`: idle rows except absenteeism. `category` is one of breakdown, maintenance, tooling, material, utilities, people, other.
  - `v_absenteeism(card_date, shift, emp_no, mc_no)`: one row per absent shift (code 10813).
  - `v_operator_productivity(emp_no, shift, days_worked, productive_hours, qty_accp, std_qty, efficiency_pct)`. `std_qty` = sum(hours × component std rate). `efficiency_pct` = 100 × qty_accp / std_qty, over the whole period. Also provide `v_operator_productivity_daily(card_date, emp_no, shift, productive_hours, qty_accp, std_qty)` so date filters work.
- `003_readonly_role.sql`: role `titan_chat_ro` (password `titan_chat_ro`), `SELECT` on the 5 views + `machines` + `codes` + `employees` only. No access to base card tables. `default_transaction_read_only = on`, `statement_timeout = 5s`.

### Demo questions (answers must be correct, checked in tests)
The "last 4 months" window is 2026-07-20 to 2026-11-14, i.e. the whole period. "Today" in the demo is **2026-11-18**.
1. "Which CNC machine lost the most hours to breakdowns in the last four months?" → bar chart of breakdown hours by CNC machine. Top: 604021.05.
2. "Who has the highest absenteeism?" → ranked table: emp_no, absent shifts. Top 3 = the planted operators.
3. "Who's least productive?" → ranked table, ascending efficiency_pct. Bottom 3 = the planted operators.

## Database models (lead; `backend/app/db/models.py` is the source of truth)
- `employees(emp_no PK, shift_group, home_mc_no)`
- `machines(mc_no PK, machine_type 'Press'|'CNC', is_cnc)`
- `components(comp_code PK, description, std_rate_per_hour)`
- `codes(code PK, kind 'production'|'idle'|'rework'|'rejection', description, category)`. Rework and rejection codes are stored with prefixes `RW-001` and `RJ-001` as the PK; the `code` column of rows keeps the raw value.
- `job_cards`, `card_rows`, `review_log`, `chat_log`: see `models.py`.

## API (BACKEND agent; FRONTEND codes against this)
All JSON. Errors: `{"detail": "..."}`.

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health` | | `{ok, db, llm_mode, ollama_reachable, read_model, chat_model}` |
| GET | `/api/masters` | | `{employees:[...], machines:[{mc_no,machine_type}], components:[...], idle_codes:{code:desc}, production_codes:{...}, rework_codes:{...}, rejection_codes:{...}}` |
| GET | `/api/cards` | `?status=&source=&limit=50` | `[{id, card_ref, source, card_date, mc_no, emp_no, status, flag_count, created_at}]` newest first |
| POST | `/api/cards` | multipart `file` (jpeg/png) | `{id, status:"processing"}`. Reading runs in a background task |
| GET | `/api/cards/{id}` | | `Card` (below) |
| GET | `/api/cards/{id}/image` | | the image file |
| PUT | `/api/cards/{id}` | `{header, rows, total_hours}` | `Card`. Saves the supervisor's edits, writes `review_log` per changed field, re-runs validation |
| POST | `/api/cards/{id}/approve` | `{by?: "supervisor"}` | `Card` with status `approved` (allowed with remaining flags; they stay recorded) |
| POST | `/api/chat` | `{question, history?: [{role, text}]}` | `ChatAnswer` |

`Card`:
```json
{"id": 12, "card_ref": "C04", "source": "photo", "status": "processing|needs_review|approved|failed",
 "image_url": "/api/cards/12/image", "read_seconds": 14.8, "error": null,
 "header": {"date":"", "component_description":"", "cc":"", "operation_description":"", "mc_no":""},
 "rows": [{"emp_no":"", "shift":"", "opn_code":"", "wo_no":"", "comp_code":"", "qty_prod":"", "qty_accp":"",
           "rej_code":"", "rej_qty":"", "rework_code":"", "rework_qty":"", "time_from":"", "time_to":"",
           "total_hours":"", "unclear":[]}],
 "total_hours": "8.00",
 "flags": [{"flag":"invalid_code", "text":"Code not on the code sheet", "where":"rows[0].opn_code",
            "detail":"Code '10613' not on code sheet", "suggestion":"10813"}]}
```
- **Field values are strings, as written.** Normalisation happens in validation and when writing `card_rows` numeric columns.
- **`flags[].text`** comes from `FLAG_TEXT` in validate.py.
- **`card_ref`** = the uploaded file name stem (`C04_front.jpeg` → `C04`), or `SYN-<id>` for synthetic cards.

`ChatAnswer`:
```json
{"route": "data|chat", "text": "604021.05 lost the most: 61.5 hours ...",
 "view": {"type": "bar|line|table|kpi|null", "x": "mc_no", "y": "breakdown_hours", "title": "Breakdown hours by CNC machine"},
 "columns": ["mc_no", "breakdown_hours"], "rows": [["604021.05", 61.5], ["604021.03", 33.0]],
 "sql": "SELECT ...", "checks": {"sql_valid": true, "numbers_match": true}, "ms": 8200}
```

**Chat pipeline:**
1. Router (LLM, JSON schema): data or chat.
2. SQL (LLM, JSON schema `{sql}`), written against the views. The prompt includes the view DDL, the code meanings and today's date (2026-11-18).
3. **sqlglot** check: a single SELECT, only the allowed views/tables, LIMIT ≤ 200 added if missing.
4. Run it as `titan_chat_ro`.
5. Answer (LLM, JSON schema `{text, view}`) from columns + rows.
6. Number check: every number in `text` must appear in the rows (allow rounding to 1 decimal). If it fails, retry once; if it fails again, return a deterministic text built from the top rows.

`chat_log` stores each step.

**Reading pipeline (`POST /api/cards`):**
1. Save the file.
2. Status `processing`.
3. Call Ollama `/api/chat` with the bake-off prompt + schema: copy `extract.py`, `common.py`, `validate.py` and `prompts/` into `app/core/reading/`, unchanged apart from paths and master data.
4. `validate()`.
5. Status `needs_review` if there are flags, otherwise `approved`.
6. Write `card_rows` with normalised numbers and minutes.
7. On error: status `failed` + `error`.

## Frontend (FRONTEND agent)
**Stack:** Next.js 15 App Router + TypeScript + Tailwind 4 + Recharts + lucide-react.

**Colours: Titan Company brand** (sampled 19 Nov 2026 from the titancompany.in logo and CSS):
- teal `#00B2AD` (primary)
- deep teal `#115E6E` (top bar, headings)
- grey `#616363`
- light teal background `#ECF7F6`
- font Raleway

Status colours stay semantic: Saved green, Needs review amber, Failed red. **No Titan logo** (needs Titan's approval).

**Video-friendly:** 1920x1080, base font 16–18 px, nothing tiny.

**Pages:**
- `/` → redirect to `/chat`.
- **Top bar:** "Shift Logger" + nav (Ask · Job cards · Review (count of needs_review)), a "Proof of concept" tag, and a STUB badge if `llm_mode != live`.
- **`/chat`:**
  - Chat thread. Each answer shows the text, then the view (Recharts bar/line; ranked table with rank numbers; kpi big number).
  - "Show details" toggle with the SQL (monospace) and the raw rows table.
  - Loading state: "Reading the data…" with elapsed seconds.
  - Empty-state suggestion chips with the 3 demo questions.
- **`/cards`:**
  - List with status pills (Saved = approved green, Needs review = amber, Reading… = blue spinner, Failed = red), flag count, machine, date, source icon (photo/synthetic).
  - Filter tabs: All / Needs review / Photo cards.
  - "Upload job card" button with drag-and-drop. After upload, go to `/cards/{id}` and poll every 1.5 s while `processing`.
- **`/cards/[id]`:**
  - **Split view.** Left: card image, zoomable/pannable, fit to height. Right: header fields + rows as an editable grid with all 14 fields + Total.
  - **Flags** as an amber list at the top. Each flag highlights its cell (via `where`). A suggestion shows a "Use 10813" button that fills the cell.
  - Buttons: Save changes (PUT), Approve (POST approve) → toast "Saved to the database", then back to the list.
  - While processing: skeleton plus "AI is reading the card…" and elapsed seconds.
  - Unclear cells (`rows[].unclear`) get a dotted amber underline.
- **Errors:** friendly messages, never a stack trace.
