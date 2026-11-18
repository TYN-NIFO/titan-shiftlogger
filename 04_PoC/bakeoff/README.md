# Extraction bake-off: which open-source model reads Titan job cards best?

Runs local open-source vision models (through Ollama) over the 10 synthetic job-card photos,
scores each field against the answer key, runs the validation rules on what the model read,
and prints one comparison table.

Everything runs locally. Nothing is sent to a public AI service.

## Files

| Path | What it is |
|---|---|
| `data/answer_key.json` | Source of truth: every field on C01–C10 **as written**, plus corrections, unclear cells and expected flags |
| `data/master_data.json` | Code sheet (idle / rework / rejection codes from the real card) + demo employees, machines, components, shifts |
| `prompts/extract_prompt.txt` | The extraction prompt (reading rules for ditto marks, diagonal Emp No, crossed-out cells, h.mm times) |
| `prompts/ocr_prompt.txt` | Prompt for the OCR model in `ocr>mapper` pipelines |
| `extract.py` | Calls Ollama with the photo, forces JSON output; supports `ocr>mapper` pipelines |
| `validate.py` | The validation rules (also used by the real PoC later). `python validate.py` shows the flags per card |
| `score.py` | Field-by-field comparison against the answer key |
| `run_bakeoff.py` | Runs everything and writes `results/<timestamp>/` |
| `agreement.py` | Two-reader check on a finished run: which cells two different models disagree on, and whether any wrong card would still be auto-saved |
| `make_answer_key_xlsx.py` | Rebuilds `../Synthetic_Job_Cards/Answer_Key_C01-C10.xlsx` from the JSON |
| `models.txt` | Model list, grouped by GPU size |

## Run it on the VM

```bash
# 1. Ollama, in Docker (what the 18 Nov 2026 run used; port 11435 avoids clashing with
#    another Ollama on the same server - use any free port). Pin it to one GPU / MIG slice,
#    keep it on localhost, cap the context (the default can reserve the whole GPU),
#    unload idle models, and block Ollama's cloud models so nothing leaves the server.
docker run -d --name ollama --restart unless-stopped --runtime=nvidia \
  -e NVIDIA_VISIBLE_DEVICES=<GPU or MIG UUID from nvidia-smi -L> \
  -e OLLAMA_CONTEXT_LENGTH=16384 -e OLLAMA_KEEP_ALIVE=2m \
  -e OLLAMA_MAX_LOADED_MODELS=1 -e OLLAMA_NUM_PARALLEL=1 -e OLLAMA_NO_CLOUD=1 \
  -p 127.0.0.1:11435:11434 -v ollama:/root/.ollama ollama/ollama:latest
# pull every model in models.txt (skip "ocr>mapper" lines; pull both halves of those)
for m in $(grep -v '^#' models.txt | cut -d'#' -f1 | tr '>' '\n' | xargs -n1 | sort -u); do
  docker exec ollama ollama pull "$m"; done

# 2. Code
git clone https://github.com/TYN-NIFO/titan-shiftlogger.git
cd titan-shiftlogger/04_PoC/bakeoff

# 3. Check the scorer and rules (no model needed) - must show 100% and 0 missed reviews
python3 run_bakeoff.py --self-test

# 4. One model on one card first
python3 run_bakeoff.py --host http://localhost:11435 --models qwen3.8:27b-q4_K_M --cards C10

# 5. Full bake-off
python3 run_bakeoff.py --host http://localhost:11435 --models-file models.txt
# or: --models qwen3.8:27b-q4_K_M "glm-ocr:bf16>qwen3.8:27b-q4_K_M" --cards C01 C04

# 6. Two-reader agreement on that run
python3 agreement.py results/<run> qwen3.8:27b-q4_K_M qwen3-vl:30b-a3b-instruct-q4_K_M
```

`extract.py` on its own reads the host from `OLLAMA_HOST` (default `http://localhost:11434`).

If a model rejects the forced JSON schema, add `--no-schema`.

## Reading the results

| Column | Meaning | Good |
|---|---|---|
| Field acc. | Filled fields read correctly (blank-vs-blank not counted) | as high as possible |
| Numbers acc. | Same, only digits / codes / times / dates (what the chatbot's numbers depend on) | 90%+ |
| Perfect cards | Cards with every field right | |
| Row count OK | Read the right number of rows (catches merged / split rows, e.g. C06) | 10/10 |
| Flags exact | Validation raised exactly the expected flags on the model's reading | |
| Marked unclear | Cards where the model itself marked a cell unclear (this alone sends the card to review) | |
| Sent to review | Cards the supervisor would see | close to 6/10 |
| **Missed reviews** | Any card with a wrong value that raises **no flag at all**, so it would be **auto-saved**. Counts clean cards too | **must be 0** |
| Sec/card | Speed on this machine | |

Per-field detail is in `results/<timestamp>/fields.csv`; raw model output in `raw/<model>/<card>.json`.

### Two-reader agreement check

A misread that still looks valid (C06: 150 read as 180, and 180 = 180 balances) passes every rule.
A second model reads the same card; the cells where the two disagree go to the supervisor:

```bash
python3 agreement.py results/<run> qwen3.8:27b-q4_K_M qwen3-vl:30b-a3b-instruct-q4_K_M
python3 agreement.py results/<run> --all     # every pair in the run
```

The checker must be a **different** model. The Q4 and Q8 builds of the same model make the same
mistakes, so they agree with each other and catch nothing (they look perfect in `--all`; ignore those pairs).

## How the extraction is set up (and why)

Tested on qwen3.8:27b-q4_K_M, 10 cards, 18 Nov 2026:

| Valid-value lists in prompt | Thinking | Field acc. | Perfect cards | Missed reviews | Sec/card |
|---|---|---|---|---|---|
| **yes (default)** | **off (default)** | **99.6%** | **9/10** | **0** | **14.3** |
| yes | on | 99.6% | 9/10 | 0 | 33.4 |
| no | on | 90.4% | 3/10 | 0 | 29.5 |
| no | off | 85.1% | 4/10 | 0 | 13.9 |

- **Valid-value lists stay in the prompt** (`--no-value-lists` to compare). Without the employee list the
  diagonal Emp No is misread (280133 -> 13). The risk: smaller models sometimes "correct" a reading into
  another valid value (C02 604020.11 -> 604020.08), which no rule catches; the two-reader check covers that.
- **Thinking off** (`--think` to compare): same accuracy, twice the time. With a small output budget,
  qwen3.6 spent it all on thinking and returned empty answers; `--think` raises the budget to 12k tokens.
- **`unclear` marks go to review** (`unclear_cell` flag), and idle/breakdown rows with a quantity raise
  `idle_row_has_qty`. The prompt tells the model to copy what it sees and never "fix" values.
- **Output capped at 3,072 tokens**: qwen3-vl:32b once looped for 3 minutes and ~1,000 lines.
- If Ollama runs in Docker on another port, pass `--host http://localhost:<port>`.

## The 10 cards

| Card | Scenario | What's hard on the photo | Expected flags |
|---|---|---|---|
| C01 | Normal shift | Diagonal Emp No; ditto; row 1 written 6.30–10.00 (writer's slip) | time_overlap |
| C02 | Mechanical breakdown | Diagonal Emp No; overwritten 10804 | – |
| C03 | Electrical breakdown + rejection | No date; row 3 Qty Prod **180 or 130** (unclear) | missing_date, qty_balance |
| C04 | Absent | 10813 written like **10613** (unclear) | invalid_code (suggests 10813) |
| C05 | Rejection + rework | No date; M/C No **60402008** (no dot); overwritten 880 | missing_date, unknown_machine (suggests 604020.08) |
| C06 | No tool + cleaning | Times written half a row above the codes | – |
| C07 | S prefix + ditto | Ditto of S10202; no Operation Description | – |
| C08 | Planned errors | Accp > Prod; wrong row hours; total 7.30 | accp_gt_prod, qty_balance, row_hours_mismatch, shift_hours_not_8 |
| C09 | Planned errors | Unknown Emp 999999; code 10899; overlap; total 8.30 | unknown_employee, invalid_code, time_overlap, shift_hours_not_8 |
| C10 | PM + TPM + rework + rejection | "F, W" instead of F, W, T | – |

Backs were not photographed, so Remarks and Signature & Date are out of the bake-off.

## Rules

- Synthetic photos only. **Real Titan cards never go on this VM or any public service**, only Titan's own server.
- Proposal documents say "open-source AI models", not model names.
