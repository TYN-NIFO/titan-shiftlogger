# Titan Shift Logger PoC: backend

FastAPI service for the demo: job-card upload and AI reading, validation, supervisor review, and the chatbot
(text-to-SQL over read-only views). The API is specified in `05_App/CONTRACT.md`.

## Setup (Windows laptop)

```bash
cd 05_App/backend
uv venv .venv --python 3.10
uv pip install --python .venv/Scripts/python.exe -r pyproject.toml
```

Postgres 16 runs at `localhost:5432` (postgres/password). Build the demo database (DATA agent's scripts):

```bash
.venv/Scripts/python.exe scripts/init_db.py                 # tables, views, read-only role, masters
.venv/Scripts/python.exe scripts/generate_synthetic.py --seed 42
.venv/Scripts/python.exe scripts/seed_photo_cards.py         # optional demo state
```

## Environment

Read from `05_App/.env` (falls back to `05_App/.env.example`); real environment variables win.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | app connection (read/write) |
| `CHAT_DATABASE_URL` | chatbot connection as `titan_chat_ro` (SELECT on the views + machines/codes/employees only) |
| `OLLAMA_HOST` | Ollama base URL, normally the SSH tunnel `http://localhost:11434` |
| `READ_MODEL`, `CHAT_MODEL` | Ollama model tags (both `qwen3.8:27b-q4_K_M`) |
| `LLM_MODE` | `live` (default) or `stub` (automated tests only) |
| `UPLOAD_DIR` | where uploaded photos are saved; relative paths are relative to the repo root |
| `LLM_TIMEOUT` | optional, seconds per AI call (default 120) |

## Run

```bash
cd 05_App/backend
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
curl http://localhost:8000/api/health
```

CORS allows `http://localhost:3000` (the frontend). On startup, cards left in `processing` by a restart are
marked `failed` so the UI never spins forever.

## Reaching Ollama on the GPU server

The model is not on the laptop. Open an SSH tunnel so `localhost:11434` reaches the server's Ollama
(placeholders below; the real host and port are kept out of the repo):

```bash
ssh -N -L 11434:localhost:<server-ollama-port> <user>@<gpu-server>
curl http://localhost:11434/api/tags          # should list qwen3.8:27b-q4_K_M
```

Then `/api/health` shows `"ollama_reachable": true` and `"ok": true`. Check `nvidia-smi` on the server before
a recording: the GPU is shared. A card read takes about 15 s; a chat answer is 3 AI calls (route, SQL, answer).

## Live vs stub

- **live**: card reading calls `app/core/reading/extract.py` (bake-off prompt with the valid-value lists, forced
  JSON schema, think off, temperature 0, `num_ctx` 8192, output cap 3,072 tokens, one read at a time). Chat calls
  Ollama `/api/chat` with a JSON schema at each step.
- **stub** (`LLM_MODE=stub`, tests only): reading returns the answer-key reading for the file's card ref
  (`C04_front.jpeg` -> C04; only C01-C10 exist), and chat answers only the 3 demo questions with canned SQL that
  really runs against the views. Anything else gets "not available in stub mode". `/api/health` reports
  `llm_mode: "stub"` and the frontend shows a STUB badge.

## Pipelines

**Reading** (`POST /api/cards`): save file -> `processing` -> background task: read -> `validate()` ->
flags (with `FLAG_TEXT`) -> `card_rows` (normalised ints, codes, minutes) -> `needs_review` if flagged, else
`approved`; any error -> `failed` + `error`. `PUT /api/cards/{id}` writes one `review_log` row per changed
field, clears "unclear" on corrected cells, re-validates and rebuilds `card_rows`.
`POST /api/cards/{id}/approve` sets `approved` (remaining flags stay recorded) and logs it.

**Chat** (`POST /api/chat`), `app/services/chat.py`:
1. Router (data | chat). Chat replies may not contain numbers.
2. SQL from the AI. The prompt has the view columns (read from the database), code meanings, today =
   2026-11-18 and example question -> SQL pairs (`app/prompts/sql.txt`).
3. `sql_guard.py` (sqlglot): one SELECT only, allowed relations only, no `pg_*`/settings functions, no locks
   or `INTO`; adds `LIMIT 200` (or lowers a bigger one). A rejected or failing query is retried once with
   the error fed back.
4. Runs as `titan_chat_ro` in a read-only transaction with a 5 s timeout.
5. Answer `{text, view}` from the columns + rows.
6. `numbers_check.py`: every number in the text must be in the rows (rounding to 0-2 decimals allowed),
   in the question, or a small count (1..10). One retry; then a deterministic text from the top rows
   (`checks.fallback_text: true`).
7. Every question is written to `chat_log`. Errors never leak: the user gets a friendly sentence.

## Tests

```bash
cd 05_App/backend
.venv/Scripts/python.exe -m pytest tests/test_api.py tests/test_chat.py -q
```

`tests/conftest.py` forces `LLM_MODE=stub`, recreates the database `titan_shiftlogger_test` (`create_all` +
`app/db/sql/002_views.sql` + `003_readonly_role.sql` with the role renamed `titan_chat_ro_test`), loads the
masters and seeds a few synthetic cards with obvious patterns. Uploads go to a temp folder. The live chat
pipeline is also tested with a fake AI (retries, guard rejection, numbers fallback, AI unreachable).
`tests/test_data.py` (DATA agent) checks the real demo database with its own engines.
