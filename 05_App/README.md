# Shift Logger PoC app (05_App)

The app shown in the demo video. Job cards are uploaded, read by an open-source AI model, checked by the
validation rules, held for the supervisor when a check fails, and queried in plain English.
Spec: `CONTRACT.md`. Video script: `../05_Demo_Video/Titan_demo_video_script.md` (FINAL section).

| Part | Folder | Stack |
|---|---|---|
| Backend | `backend/` | Python 3.10+, FastAPI, SQLAlchemy, Postgres 16; Ollama for the AI |
| Frontend | `frontend/` | Next.js 15, Tailwind 4, Recharts |
| Data | `backend/scripts/` | 4 months of synthetic job cards + 7 photo cards (synthetic only) |

Screens: **Ask** (chat with chart / ranking / query), **Cards** (every card, with the card flow), **Review**
(the supervisor's queue: fix and approve the cards that failed a check).

## Run on the GPU VM (Linux), where the video is recorded

Ollama already runs there (see `04_PoC/bakeoff/README.md`). Check `nvidia-smi` first: the GPU is shared.

```bash
git clone https://github.com/TYN-NIFO/titan-shiftlogger.git && cd titan-shiftlogger/05_App

# 1. Postgres 16 in Docker, local only
docker run -d --name titan-pg --restart unless-stopped -e POSTGRES_PASSWORD=password \
  -p 127.0.0.1:5432:5432 postgres:16

# 2. Settings: copy and point OLLAMA_HOST at the VM's Ollama (the bake-off used port 11435)
cp .env.example .env
sed -i 's#^OLLAMA_HOST=.*#OLLAMA_HOST=http://localhost:11435#' .env
docker exec "$(docker ps -qf name=ollama | head -1)" ollama list      # qwen3.8:27b-q4_K_M must be there

# 3. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -q fastapi "uvicorn[standard]" "sqlalchemy>=2" "psycopg[binary]" python-multipart sqlglot httpx pytest
PGPASSWORD=password psql -h localhost -U postgres -c "create database titan_shiftlogger" 2>/dev/null \
  || docker exec titan-pg psql -U postgres -c "create database titan_shiftlogger"
.venv/bin/python scripts/reset_demo.py                       # tables, views, data, 7 photo cards
.venv/bin/python -m pytest -q                                 # 74 tests, uses LLM_MODE=stub
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &

# 4. Frontend (Node 22)
cd ../frontend && npm ci && npm run build && npm start &      # http://localhost:3000
```

Open http://localhost:3000 (or tunnel it: `ssh -L 3000:localhost:3000 -L 8000:localhost:8000 <vm>`).
The top bar must say **"AI live · on-premises"**. "Test mode" means `LLM_MODE=stub` is set; never record in test mode.

## Before every recording take

```bash
cd 05_App/backend && .venv/bin/python scripts/reset_demo.py
```

State after reset: 7 photo cards (C01, C03, C05, C09 waiting for review; C06, C07, C10 saved) and
8,151 synthetic cards. Photos to upload live: `04_PoC/Synthetic_Job_Cards/Photos/C02_front.jpeg`,
`C04_front.jpeg`, `C08_front.jpeg`.

Expected during the take:
- **C02** saves automatically.
- **C04** goes to Review with "Code not on the code sheet", suggestion **10813**.
- **C08** goes to Review with 4 checks (accepted > produced, quantity balance, row hours, shift hours).
- **Ask** answers:
  - "Which CNC machine lost the most hours to breakdowns…" → **604021.05 (CNC case milling 1)**, 163.5 h.
  - "Who has the highest absenteeism?" → **Divya D. (280419)**, Priya B., Vidya S. Ask this *before* approving
    C04: C04 is 280419's absence card, so it adds one.
  - "Who's least productive?" → **Uma D. (280512)**, Siva G., Murali L.

All names are made-up sample data.

Notes from take 3:
- Open the Cards screen and let it finish loading (counts filled in, top bar "AI live") before "Here's what we built".
- Upload C08 straight after C04, so its 4 checks are on screen for "Here, accepted is more than produced".
- After approving C04 the Review queue moves to the next card; hold on C04 for a beat, then cut to Cards.
  C04 then shows "Fixed by supervisor", and the flow strip shows "+ 1 fixed by supervisor".

## Run locally (Windows laptop)

See `backend/README.md` and `frontend/README.md`. Without the GPU, start the backend with `LLM_MODE=stub`
(canned answers for the 3 demo questions; the top bar then shows "Test mode").
