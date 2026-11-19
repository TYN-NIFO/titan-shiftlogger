# Titan AI-Enabled Shift Logger: project overview

The Yellow Network (TYN) pre-sales and PoC work for **Titan Company Ltd, Watch Division**.
This file is the single place to understand the project: what Titan asked for, what we
proposed, how the job card works, how the system is designed, where the PoC stands and
what's still open.

> **Confidential.** Titan data stays private. No public LLMs: everything must run on
> open-source models on Titan's premises. Real Titan cards never leave Titan's server.

---

## 1. Status at a glance (19 Nov 2026)

| Area | Status |
|---|---|
| Technical approach (4-week PoC) | Done, 11 Nov 2026. Waiting for internal TYN review |
| Architecture diagram | Done (`03_Proposal/Diagrams/Titan_Technical_Diagram.png`) |
| Internal estimate for the full RFQ | Done, 16 Nov 2026, sent to Amit for the proposal |
| Commercials | Not started (GG's call) |
| Synthetic job cards | 10 cards filled and photographed (fronts only) |
| Answer key + validation rules | Done (`04_PoC/bakeoff/`) |
| Model bake-off | Done, 18 Nov 2026. Winner: Qwen3.8 27B (Q4), 99.6% fields, 0 missed reviews, 17 GB GPU (§7) |
| PoC app (`05_App/`) | Built 19 Nov 2026: Ask (chat with chart / ranking / query), Cards, Review queue; synthetic data loaded. Live-model run on the VM next |
| Demo video | Script final (`05_Demo_Video/`, 1:30). Recording on the GPU VM next |

---

## 2. People

| Who | Role |
|---|---|
| B T Sathishkumar, Harini, Praywin Henry (Titan) | Titan AI pilot team. Sathishkumar wrote the RFQ |
| Amit Durgaprasad (TYN) | Account lead; owns the proposal |
| Ganapathy Subramanian / GG (TYN) | Founder & CEO; pricing decisions |
| Cyril Freddy Wills, Karthik Das (Forge) | Partner |
| Sanjai R (TYN) | First architecture diagram |
| Lathiesh (TYN) | Solution / technical author |

---

## 3. What Titan asked for

### 3.1 The meeting (MoM, 5 Nov 2026), the original PoC ask
- Today about **80 operators across 2 shifts** hand-write a **job card** at the end of each shift.
  The supervisor copies it into a logbook (the green "Daily Production Register"),
  a data-entry person retypes it into Excel, and Excel feeds management reports.
- Titan wants AI to turn job cards into structured data, plus a **chatbot** for management. The example questions were:
  1. CNC downtime over the last 4 months
  2. The least productive operators
  3. The highest absenteeism
  4. First troubleshooting steps for a machine before calling the technician
- **Hard constraint:** the data is proprietary, so no public LLMs. Open-source models run on-prem.
- This is Titan's first, deliberately simple AI use case: prove value first.

### 3.2 The RFQ (27 Oct 2026, `01_Client_Inputs/RFQ_AI_Shift_Logger_27Oct2026.docx`)
Location: **DATE Function, Hosur, Machine Shop**. The RFQ is much bigger than the MoM. It asks for:
- **Dropdown digital logging** in 5 data areas (Employee, Machine, Tool, Production, Model-wise), replacing paper
- Shift handover reports and pending tasks
- A source-grounded AI assistant that escalates to an SME
- Dashboards: OEE, MTTR, MTBF, TPM losses
- Anomaly detection (5.3), high availability (5.1), offline buffering (5.5), web-based operator terminals (5.8)
- Machine integration (OPC-UA, Ethernet/IP, MT-Link, Modbus TCP) and MES/ERP/HR integration over REST/MQTT (5.7)
- Documentation (7), hardware (8), training (9), 12-month warranty (11)
- Not specified: which lines, how many terminals, where and when data is entered.
- The RFQ contradicts itself on who supplies the server: 4.2 says Titan, 8 and 11 suggest the supplier.

**Rule (user, 16 Nov 2026):** never move RFQ requirements into out-of-scope or add-ons on our own.
Estimate the full RFQ and offer phasing as an option.

### 3.3 MoM vs RFQ: the gap to resolve with Titan
| | MoM (meeting) | RFQ (document) |
|---|---|---|
| Shop | Case Centre, Press Shop (C.C. 1300) | DATE Function, Machine Shop |
| Input | Handwritten job cards, read by AI | Dropdown digital forms (paper replaced) |
| Size | Simple first AI use case | Full shop-floor system with integrations |

---

## 4. The job card

Samples: `01_Client_Inputs/Job_Card_Samples/` (local only, not in git). Synthetic copies: `04_PoC/Synthetic_Job_Cards/`.

### Front
- **Header:**
  - Date
  - Component Description
  - CC. (component codes)
  - Operation Description (e.g. "F, W, T")
  - M/C No. (e.g. 604020.08)
- **Printed:** "TCL Watch Division, **C.C. 1300 = Case Centre 1300**" (not cost centre), "Press Shop", form no. 56/19/1300.
- **Table, one row per activity:**
  - Sl. No, Emp. No, Shift Code, Opn/Idle Code, W.O. No, Comp. Code
  - Qty Prod, Qty Accp, Rej Code/Qty, Rework Code/Qty
  - Time From/To, Total Hours, Sign.
- **Handwriting habits from the real sample (05/11/26):**
  - Emp No is written once, diagonally across the rows.
  - Ditto marks are used for repeats.
  - Empty columns are crossed out with one X.
  - "3.30" means 3 h 30 m.
  - The total is written as "8 =" and underlined.

### Back (code sheet)
- **Non-productive hour (idle) codes:**
  - 10801 Preventive Maintenance
  - 10803 Electrical breakdown
  - 10804 Mechanical breakdown
  - 10806 No Load
  - 10808 No Utilities
  - 10810 No Tool
  - 10811 Tool Reconditioning
  - 10813 Absenteeism
  - 10815 Training
  - 10816 Welfare
  - 10817 Machine Modification
  - 10818 Tryout
  - 10819 Technical Problems
  - 10825 TPM by operator
  - 10826 Kanban Full
  - 10829 Adjustment to 3rd Shift
  - 10835 Shop Service / Furnace / Oiling / Durr
  - 10836 Machine Cleaning
  - 10910 Annealing
  - 11600 Inspection
- **Rework codes:** 001 Black Stains, 002 Burr, 004 Dent, 005 Damages, 006 Operation Miss, 007 Insufficient Material Flow, 010 Peel Off, 011 Mixup, 012 Scoring Mark, 013 Dial Opening.
- **Rejection codes (what the reason is):** 001 Damage, 004 Tool chipped off, 005 Wrong tool, 006 Mis location, 007 Billet melting, 008 Crack, 009 Bottom dent.
- **Blocks:** Route, SuplEng, Remarks, Signature & Date.

The full list is machine-readable in `04_PoC/bakeoff/data/master_data.json`.

### What the card tells management
| Question | Comes from |
|---|---|
| Downtime by machine and reason | Idle-code rows (10803/10804 …) × hours, by M/C No |
| Productivity per operator | Qty Prod / Qty Accp per Emp No per productive hour |
| Absenteeism | Rows with 10813, by Emp No |
| Quality losses | Rej / Rework codes and quantities |

### Open questions for Titan
- The full operation-code list. 10202 is not on the code sheet; we assume it means production.
- What "F, W, T" and the "S" prefix (S10202) mean.
- The shift codes and timings. 10829 "Adjustment to 3rd Shift" hints at 3 shifts.
- How an absent operator's card is recorded.
- Who signs the card.
- What Route / SuplEng mean.
- Standard output rates per component.
- The machine master list, including which machines are CNC.

---

## 5. Solution design (PoC)

### Two data paths, kept separate
```
Job card photo ─► AI extraction (open-source vision model)
              ─► Validation rules ─┬─ pass ─────────────► Job Card Database (SQL)
                                   └─ flag ─► Supervisor review ─► Job Card Database (SQL)

Manuals / SOPs ─► chunk ─► embed ─► Vector database

Chatbot ─┬─ data questions ("CNC downtime last 4 months") ─► read-only text-to-SQL ─► SQL DB
         └─ how-to questions ("first steps for M/C X")       ─► knowledge search (RAG) ─► vector DB
```
- Job-card data does **not** go into the vector DB: totals, counts and rankings need exact SQL.
- The Titan team scans the cards; image capture is not our step.
- No login or user roles in the PoC.

### Validation rules (`04_PoC/bakeoff/validate.py`)
| Flag | Rule |
|---|---|
| missing_date | Date blank or unreadable |
| unknown_employee / unknown_machine / unknown_component | Not in master data. The machine is fuzzy-matched (60402008 → 604020.08) |
| invalid_code / invalid_rej_code / invalid_rework_code | Not on the code sheet. Suggests the nearest valid code (10613 → 10813) |
| accp_gt_prod | Qty Accp > Qty Prod |
| qty_balance | Prod ≠ Accp + Rej + Rework |
| row_hours_mismatch | Total Hours ≠ From–To span (or span − 30-minute break) |
| time_overlap | Two rows overlap |
| shift_hours_not_8 / total_mismatch | Rows don't add up to 8.00 / the written total ≠ the sum of rows |

### Human in the loop
- Only cards with a flag go to the **supervisor review screen**, which shows the card crop, the problem and the suggested fix.
- Clean cards are saved automatically.
- Today the supervisor re-copies every card; with this they check only the flagged ones.
- Nothing reaches the reports without passing the rules or a person.

### Proposal writing rules
- Don't name models or frameworks in client documents. Say "open-source AI models", "vector database", "backend service".
- Keep to HLD level, with a 3–4 line purpose.
- Assumptions cover infrastructure and models only; timeline risks go inside the assumptions.
- No overview section and no deliverables section.
- Diagram style: white background, blue borders, coloured icons, dashed phase containers.

### Infrastructure assumption (indicative)
- 1 enterprise GPU with 24–48 GB, 16+ CPU cores, 64–128 GB RAM, 1–2 TB SSD, Linux.
- Internet access during setup only.
- Titan provides, before kickoff:
  - the server
  - 50–100 sample cards
  - the code, machine and employee lists
  - the manuals

---

## 6. Plans and effort

### 4-week PoC (technical approach, 11 Nov 2026)
- **Team:** 1 senior + 1 junior developer, about 40 person-days.
- **Week 1:** setup. **Week 2:** extraction. **Week 3:** chatbot. **Week 4:** accuracy tuning, testing and deployment.

### Full RFQ, internal estimate (16 Nov 2026, `03_Proposal/Titan_Shift_Logger_Internal_Estimate_16Nov2026.pdf`)
- **Effort:** build only, no warranty.
  - Industry-standard: **1,132–1,672 h**.
  - AI-assisted (our team): **832–1,208 h**.
  - Basis, same as the DCM Shriram estimate: AI roughly halves coding, while requirements, testing, UAT and PM don't shrink.
- **Team:**

  | Role | Hours |
  |---|---|
  | Senior AI Engineer | 230–350 h |
  | Full-stack developer | 250–390 h |
  | Junior developer | 170–260 h |
  | BA/PM at 40–50% | 182–208 h |

- **Timeline:** 7–10 weeks with 4 people; 5–7 weeks with 1 more full-stack developer; 4 weeks would need about 7 people.
- **Phasing option:** Phase 1 is 620–850 h AI-assisted; Phase 2 is 210–360 h.
- **No OT hire:** Titan's automation team enables the machine side. Ours is a standard OPC-UA client.
- **Watch out:** the colleague's deck (`03_Proposal/..._Deck_13Nov2026.pptx`) says 4 weeks / 6 people / about 100 person-days. That doesn't match this estimate; flag it to Amit.

---

## 7. PoC work: synthetic job cards and model bake-off

### Synthetic cards (`04_PoC/Synthetic_Job_Cards/`)
- `Synthetic_Job_Card_Fill_Sheets_C01-C10.pdf`: what each person wrote, front and back. Planned errors are in red.
- `Photos/C01–C10_front.jpeg`: fronts of the filled photocopied cards (18 Nov 2026). There are **no back photos and no re-shoots**.
- `Answer_Key_C01-C10.xlsx`: every field as written, the corrections, the unclear cells and the expected flags.
- Writers' slips are **kept as real-world test cases**:
  - C01: time overlap.
  - C03: no date; 180 or 130.
  - C04: 10613 or 10813.
  - C05: no date; machine number without its dot.
  - C06: misaligned rows.
  - C07: written clean instead of messy.
  - All cards: no Sign. initials.
- **Demo assumptions** to confirm with Titan:
  - F, W, T = Forming, Washing, Trimming.
  - S = setup/trial.
  - Shift A runs 6.00–2.30 and shift B 2.30–11.00, each with a 30-minute break.
  - Machine numbers, CNC vs press, and components 2250/3341 are made up.

### Bake-off (`04_PoC/bakeoff/`, see its README)
- **Ran on:** a shared internal GPU server (one H200 slice), Ollama 0.40.16 in Docker. Synthetic photos only.
- **Key metrics:** field and number accuracy, and **missed reviews (must be 0)**: any card with a wrong value that raises no flag and would be auto-saved.
- **Settings (final):** valid-value lists in the prompt, thinking off, output capped at 3,072 tokens, temperature 0.
  Without the lists, Qwen3.8 fell to 85% (the diagonal Emp No was misread); thinking gave the same accuracy at twice the time.

**Final results, 18 Nov 2026 (10 cards, `results/` is git-ignored):**

| Model | Field acc. | Perfect cards | Missed reviews | Sent to review | Sec/card | GPU (measured) |
|---|---|---|---|---|---|---|
| **Qwen3.8 27B Q4** | **99.6%** | **9/10** | **0** | 6/10 (the expected 6) | 15 | **17 GB** |
| Qwen3.8 27B Q8 | 99.6% | 9/10 | 0 | 7/10 | 16 | 27 GB |
| GLM-OCR → Qwen3.8 27B Q4 | 98.2% | 7/10 | 1 | 6/10 | 29 | 3 + 17 GB |
| Qwen3.6 35B-A3B Q8 / Q4 | 97.5% / 96.8% | 5/10 | 2 / 1 | 7–8/10 | 5–6 | 35 / 22 GB |
| Qwen3-VL 8B Q8 / Q4 | 96.4% / 92.6% | 5/10 / 3/10 | 1 | 7–8/10 | 5–6 | 11 / 7 GB |
| Qwen3-VL 30B-A3B Q8 / Q4 | 93.6% | 3/10 | 0 / 1 | 8–9/10 | 6 | 32 / 20 GB |
| Qwen3-VL 32B Q8 / Q4 | 93.4% / 75.4% | 3–4/10 | 0 / 1 | 8/10 | 19–38 | 36 / 23 GB |

- **Qwen3.8 27B's one mistake** (C04: 10613 read as 10013) raised `invalid_code`, so the card goes to review with the suggestion 10813.
- **Q4 = Q8** for Qwen3.8, so Q4 is enough: it **fits a 24 GB GPU**. A 48 GB GPU leaves room for a second reader, the chatbot and search.
- **GLM-OCR first makes it worse:** its misreads (10815, 160, 820) misled Qwen. Dropped.
- **Two-reader check** (`agreement.py`): Qwen3.8 27B + Qwen3-VL 30B-A3B (4–6 s/card) sends 9/10 cards and 12 cells to review, 0 silent errors.
  Qwen3.8 alone already had 0 missed reviews here, so the second reader is a safety net for real cards, at the cost of more cells to check.
- **Hard parts (where smaller models failed):** ditto marks, the diagonal Emp No, quantities copied into breakdown rows,
  C06's rows written half a line off, look-alike digits (3/5, 5/8, 2/8). C06 row 2 really is ambiguous (150 or 180).
- **Newer models found 18 Nov 2026:** Qwen3.8 (27B, vision) exists and replaces Qwen3.6 as the main candidate. Still no Qwen4.
- **Not tested:** BF16/FP32 (Qwen3.8 27B BF16 needs ~58 GB, more than the free slice; FP32 ~112 GB and no accuracy gain),
  Chandra OCR 2, dots.mocr, PaddleOCR-VL (not on Ollama).
- **Proposal wording:** still "open-source AI models", no model names (§5).

### Next steps
1. ~~Run the bake-off~~ Done: Qwen3.8 27B (Q4) reading, optional Qwen3-VL 30B-A3B second reader.
2. Test on real Titan cards on Titan's server (the synthetic set is 10 cards, fronts only).
3. Generate bulk synthetic data (about 4 weeks × 80 operators) for the chatbot and dashboard demo.
4. Build the PoC: extraction service, validation, supervisor review screen, SQL DB, text-to-SQL chatbot, RAG over manuals.
5. Hold the on-site workshop with Titan: get real cards, code lists and manuals; resolve the open questions in §4.

---

## 8. Repository layout

```
01_Client_Inputs/   MoM (5 Nov 2026). RFQ + real job card scans stay LOCAL (git-ignored)
02_Questionnaire/   (empty) CIEL format: Sl No | Question | Answers | Comments
03_Proposal/        Technical approach, internal estimate, colleague's deck, Diagrams/
04_PoC/
  Synthetic_Job_Cards/   fill sheets PDF, Photos/, Answer_Key xlsx
  bakeoff/               answer key + master data JSON, prompts, extract / validate / score / run scripts
05_App/             PoC app: backend (FastAPI + Postgres), frontend (Next.js), CONTRACT.md, README with VM run steps
05_Demo_Video/      Demo video script (1:30)
CLAUDE.md           Working notes for Claude Code sessions
PROJECT.md          This file
```

## 9. Data handling
- **Not in git:** the RFQ, real filled job cards and Titan's blank form/code-sheet scans (see `.gitignore`). The code sheet's contents are in `master_data.json`.
- **Synthetic photos:** fine on our laptop, the VM or a rented GPU. Not on free online demo pages.
- **Real Titan cards:** only ever on Titan's server.
- **Uploads to Drive:** ask before uploading client documents. The Titan folder on the TYN shared drive still needs creating (Velan / Amit).
