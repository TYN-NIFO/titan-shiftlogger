# Titan — AI-Enabled Shift Logger (POC)

Pre-sales / proposal workspace for The Yellow Network (TYN). The client is Titan Company Ltd (Watch Division, Case Centre – Press Shop; "C.C. 1300" on the card means Case Centre 1300, not cost centre (user, 18 Nov 2026)). There's no code yet: we are writing the technical approach for a 4-week POC.

## People

| Who | Role |
|---|---|
| B T Sathishkumar, Harini, Praywin Henry (Titan) | Titan AI pilot team; attended the 5 Nov 2026 meeting |
| Amit Durgaprasad (TYN) | Account lead; wrote the MoM and forwarded it on 10 Nov 2026 |
| Ganapathy Subramanian / GG (TYN) | Founder & CEO; cc on the MoM |
| Cyril Freddy Wills, Karthik Das (Forge) | Partner (Forge); in the meeting |
| Sanjai R (TYN) | Drew the first architecture diagram (`TYN_POC.drawio`, shared on Drive 11 Nov 2026) |
| Lathiesh (TYN) | Solution / proposal author (the user); a developer, new to the manufacturing domain |

## What Titan asked for (MoM 5 Nov 2026, `01_Client_Inputs/MoM_Titan_TYN_05Nov2026.md`)

- Today about 80 operators across 2 shifts hand-write a **job card** at the end of each shift. The supervisor copies it into a logbook (the green "Daily Production Register"). A data-entry person retypes that into Excel, and Excel feeds the management reports.
- Titan wants AI to turn job cards into structured data, with a **chatbot** that answers management's questions.
- The 4 example questions are:
  1. CNC downtime over the last 4 months.
  2. The least productive operators.
  3. The highest absenteeism.
  4. First troubleshooting steps for a machine before calling the technician.
- **Hard constraint: the data is Titan proprietary, so no public LLMs.** Everything must use open-source models on Titan's premises (on-prem, asset-light).
- This is Titan's first, deliberately simple AI use case: prove value before anything complex.

## The job card (samples in `01_Client_Inputs/Job_Card_Samples/`)

- **Front fields:**
  - Date, Component Description, Operation Description, M/C No.
  - Per row: Emp No, Shift Code, Opn/Idle Code, W.O. No, Comp Code, Qty Prod, Qty Accp, Rej Code/Qty, Rework Code/Qty, Time From/To, Total Hours, Sign.
- **Back (code sheet):**
  - Non-productive hour codes 108xx/109xx/116xx, for example 10803 electrical breakdown, 10804 mechanical breakdown, 10813 absenteeism, 10801 preventive maintenance.
  - Rework codes 001–013 and rejection codes 001–009.
  - A Route Supl/Eng and Signature & Date block.
- The filled sample (05/11/26, emp 279842) uses handwriting, ditto marks, crossed-out empty columns, and "3.30" meaning 3 h 30 m.
- **Open questions for Titan:**
  - The full operation-code list (10202 isn't on the code sheet).
  - What "F, W, T" and the "S" prefix mean.
  - How an absent operator's card is recorded.
  - Who signs the card.
  - Standard output rates per component.
  - The machine master list (which machines are CNC).

## Agreed scope decisions (user, 11 Nov 2026)

- **4-week POC, 1 senior + 1 junior developer, about 40 person-days.**
  - Week 1: setup. Week 2: extraction. Week 3: chatbot. Week 4: accuracy tuning, testing and deployment.
- **No login / user roles in the POC.**
- **The Titan team scans the job cards.** Image capture is not our step; don't show it.
- **Two data paths, kept separate:**
  - Job cards → AI extraction → validation rules → supervisor review (unclear cards only) → **Job Card Database (SQL)**. The chatbot answers data questions with **read-only text-to-SQL**.
  - Machine manuals / SOPs → chunking → embedding → **vector database**. The chatbot answers how-to / troubleshooting questions with knowledge search (RAG).
  - Job-card data does **not** go into the vector DB. Totals, counts and rankings need exact SQL. Remarks free text could be indexed later; it's not in the POC.
- Validation rules: hours add up, qty accepted ≤ produced, codes valid against the code sheet, employee and machine exist in master data, no overlapping times. Supervisor review exists because handwriting reading will misread some digits.
- **Proposal content rules:**
  - Don't name models or frameworks (no Qwen, vLLM, Paddle, FastAPI, Next.js, pgvector…). Use generic terms: "open-source AI models", "vector database", "backend service".
  - Keep to HLD level, with a short purpose (3–4 lines).
  - Assumptions are infrastructure + models only, plus timeline assumptions (the risks go in here).
  - No overview section and no deliverables section.
- **Infra assumption (indicative, confirm after testing real cards):**
  - 1 enterprise GPU with 24–48 GB, 16+ CPU cores, 64–128 GB RAM, 1–2 TB SSD, Linux.
  - Internet only during setup.
  - Titan provides the server before kickoff, plus 50–100 sample cards, the code/machine/employee lists and the manuals in week 1.
- Diagram style the user approved: white background, blue borders on every box, coloured Material Symbols icons, dashed phase containers (Phase 1A Job Card Ingestion, Phase 1B Knowledge Base, Phase 2 Chatbot). "Simple and clean"; colourful borders looked "childish".

## Documents

- `03_Proposal/Titan_Shift_Logger_Technical_Approach_11Nov2026.docx`: the technical approach in the TYN template. It's built from `DCM-Shriram/03_Proposal/AIRA_Scope_and_Price_Changes_05Nov2026.docx`: cover page, Google Sans, navy (0b2a4a) table headers, "Confidential | Page X of Y" footer.
  - The cover has no Titan logo (text only); add the logo by hand if needed.
- Claude Doc (living copy): https://claude.ai/artifact/RiKhkjkzdEBFGbU6hdx77w
- `03_Proposal/Diagrams/Titan_Technical_Diagram.drawio` + `.png`: the final diagram. `Diagrams/archive/` holds the earlier versions (HLD, medium, v2, first draft).
- No commercials yet; pricing is GG's call.

## Google Drive

- The shared drive is **TYN** (`0AF9FMF9l44dfUk9PVA`). Pursuits live in `02_Sales_Marketing/02_Pursuits/01_Sales_Pursuits/<Client>/` (for example DCM Shriram, Voltas, Southwire).
- **No Titan folder exists yet (11 Nov 2026), and the user has no add permission there.** Ask Velan / Amit to create `01_Sales_Pursuits/Titan`, then upload the docx + diagram.

## RFQ and internal estimate (13–16 Nov 2026)

- **Titan's RFQ** (`01_Client_Inputs/RFQ_AI_Shift_Logger_27Oct2026.docx`, 27 Oct 2026, by B T Sathishkumar) is bigger than the MoM. It covers dropdown digital logging (replacing paper), handover, dashboards (OEE, MTTR, MTBF), machine and MES/ERP integration, high availability, security, training, a 12-month warranty, and hardware. The location is DATE Function, Hosur – Machine Shop.
- **Colleague's deck** (`03_Proposal/Titan_Shift_Logger_1Month_YellowNetwork_Deck_13Nov2026.pptx`, business/sales) answers the RFQ: 4 weeks, 6 people, ~100 person-days, with Full/Lite/Add-on labels.
- **Internal estimate for Amit:** `03_Proposal/Titan_Shift_Logger_Internal_Estimate_16Nov2026.docx` / `.pdf`. It covers the full RFQ; only Titan's own work is out of scope.
  - Build only (no warranty): industry 1,132–1,672 h; AI-assisted 832–1,208 h. Same basis as the DCM estimate: AI halves coding, while requirements, testing and PM don't shrink. There's no POC code to reuse.
  - Team: senior AI engineer, full-stack developer, junior developer, BA/PM at 40–50%. About 7–10 weeks; adding 1 full-stack developer gives 5–7 weeks.
  - No OT hire: Titan's automation team enables the machine side.
- **User rule:** don't move RFQ requirements into out-of-scope or add-ons. Estimate the full RFQ and show phasing as an option.

## Status / next steps

1. Technical approach doc done (11 Nov 2026). Waiting for the user's review and internal TYN review.
2. Commercials and a questionnaire (`02_Questionnaire/`, CIEL format: Sl No | Question | Answers | Comments) can follow if requested. Use the open questions above.
3. The on-site workshop comes next (per the MoM). Get the real cards, the code lists and the manuals there.
4. `04_PoC/Synthetic_Job_Cards/`: 10 filled synthetic cards photographed (18 Nov 2026), fronts only, no re-shoots possible. Deviations from the fill sheet are kept as real-world test cases: C01 time overlap, C03 missing date + qty 180/130 (unclear), C04 10813 written like 10613 (unclear), C05 missing date + M/C written 60402008, C06 times half a row above codes, C07 clean (not messy) + no Op Description, no Sign initials anywhere. `Answer_Key_C01-C10.xlsx` records what's written on the photos.
5. **Bake-off code** (`04_PoC/bakeoff/`, 18 Nov 2026): `data/answer_key.json` (source of truth) + `data/master_data.json` (real code sheet + demo masters), `validate.py` (the validation rules; reused by the PoC), `extract.py` (Ollama, forced JSON, `ocr>mapper` pipelines), `score.py`, `run_bakeoff.py` (`--self-test` must show 100% / 0 missed reviews). The user runs it on a separate VM with Ollama. Tested: Qwen3-VL 8B/30B-A3B/32B, Qwen3.8 27B (newest, vision), Qwen3.6 35B-A3B, GLM-OCR→Qwen. No Qwen4 exists (checked 18 Nov 2026). Human-in-the-loop = supervisor review of flagged cards only.
6. **Bake-off done (18 Nov 2026)** on a shared internal GPU server (one H200 slice, Ollama in Docker; other workloads share it, so check `nvidia-smi` before big runs). Server access details are kept out of the repo. Winner **Qwen3.8 27B Q4**: 99.6% fields, 9/10 perfect, 0 missed reviews, 17 GB GPU, ~15 s/card; Q8 scored the same. GLM-OCR→Qwen made it worse (dropped). Final settings: value lists in prompt (without them 85%), thinking off (same accuracy, 2× slower), output cap 3,072. `score.py` "missed reviews" was fixed to count every auto-saved wrong card (it used to skip clean cards). `agreement.py` = two-reader check (use a different model as checker, e.g. Qwen3-VL 30B-A3B). Full table in PROJECT.md §7.
7. Next: real cards on Titan's server; bulk synthetic data (4 weeks × 80 operators) for chatbot/dashboards; then build the PoC.

## Git repo

- `https://github.com/TYN-NIFO/titan-shiftlogger` (private, TYN-NIFO org). **This TITAN folder is the repo root** (same structure). Branch `main`.
- `PROJECT.md` is the full project overview for the team; keep it in sync when scope, estimate or PoC status changes.
- `.gitignore` keeps `01_Client_Inputs/` local (RFQ, real job card scans) except the MoM. Don't commit client documents or real Titan card images. Synthetic photos are fine.

## Folder layout

```
01_Client_Inputs/   MoM (5 Nov 2026), RFQ, Job_Card_Samples/ (filled front, blank front, code sheet back) — local only, git-ignored except MoM
02_Questionnaire/   (empty)
03_Proposal/        technical approach .docx, internal estimate .docx/.pdf, colleague's deck, Diagrams/ (final .drawio + .png, archive/)
04_PoC/
  Synthetic_Job_Cards/  fill sheets PDF (C01–C10), Photos/C01–C10_front.jpeg, Answer_Key_C01-C10.xlsx
  bakeoff/              answer key + master data JSON, prompts, extract/validate/score/run_bakeoff scripts, README
PROJECT.md          full project overview (team-facing)
```

Titan data is confidential. Don't upload client documents to external services without asking.
