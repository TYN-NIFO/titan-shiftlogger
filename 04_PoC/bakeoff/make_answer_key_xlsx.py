"""Build the human-readable answer key (Excel) from data/answer_key.json.

    python make_answer_key_xlsx.py   ->  ../Synthetic_Job_Cards/Answer_Key_C01-C10.xlsx
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from common import HEADER_FIELDS, HERE, ROW_FIELDS, answer_key, complete_card, master_data
from validate import validate

OUT = HERE.parent / "Synthetic_Job_Cards" / "Answer_Key_C01-C10.xlsx"
NAVY = PatternFill("solid", fgColor="0B2A4A")
AMBER = PatternFill("solid", fgColor="FFF2CC")
RED = PatternFill("solid", fgColor="F8D7DA")
WHITE_BOLD = Font(bold=True, color="FFFFFF")


def header_row(ws, cols):
    ws.append(cols)
    for c in ws[ws.max_row]:
        c.fill, c.font = NAVY, WHITE_BOLD
        c.alignment = Alignment(wrap_text=True, vertical="center")


def autosize(ws, max_w=45):
    for i, col in enumerate(ws.columns, 1):
        w = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, w + 2), max_w)
    ws.freeze_panes = "A2"


def main():
    key, md = answer_key(), master_data()
    wb = Workbook()

    ws = wb.active
    ws.title = "Rows"
    header_row(ws, ["Card", "Row"] + ROW_FIELDS)
    for c in key["cards"]:
        corr = {x["field"]: x for x in c["corrections"]}
        for i, r in enumerate(complete_card(c)["rows"]):
            ws.append([c["card_id"], i + 1] + [r[f] for f in ROW_FIELDS])
            for j, f in enumerate(ROW_FIELDS):
                x = corr.get(f"rows[{i}].{f}")
                if x:
                    ws.cell(ws.max_row, j + 3).fill = AMBER if x["unclear"] else RED
        ws.append([c["card_id"], "TOTAL"] + [""] * (len(ROW_FIELDS) - 1) + [c["total_hours"]])
        ws[ws.max_row][0].font = Font(bold=True)
    autosize(ws, 14)

    ws = wb.create_sheet("Headers")
    header_row(ws, ["Card", "Scenario", "Photo"] + HEADER_FIELDS + ["Handwriting notes"])
    for c in key["cards"]:
        corr = {x["field"]: x for x in c["corrections"]}
        ws.append([c["card_id"], c["scenario"], c["photo"]] + [c["header"][f] for f in HEADER_FIELDS]
                  + ["; ".join(c["handwriting_notes"])])
        for j, f in enumerate(HEADER_FIELDS):
            x = corr.get(f"header.{f}")
            if x:
                ws.cell(ws.max_row, j + 4).fill = AMBER if x["unclear"] else RED
    autosize(ws)

    ws = wb.create_sheet("Corrections")
    header_row(ws, ["Card", "Field", "As written (model should read)", "Should be (fill sheet)",
                    "Unclear?", "Also accept"])
    for c in key["cards"]:
        for x in c["corrections"]:
            ws.append([c["card_id"], x["field"], x["as_written"] or "(blank)", x["should_be"],
                       "Yes" if x["unclear"] else "", ", ".join(x.get("accept", []))])
            ws[ws.max_row][2].fill = AMBER if x["unclear"] else RED
    autosize(ws)

    ws = wb.create_sheet("Expected flags")
    header_row(ws, ["Card", "Goes to supervisor?", "Flag", "Where", "Detail", "Suggested fix"])
    for c in key["cards"]:
        flags = validate(c, md)
        if not flags:
            ws.append([c["card_id"], "No - auto-saved", "", "", "", ""])
        for f in flags:
            ws.append([c["card_id"], "Yes", f["flag"], f["where"], f["detail"], f["suggestion"] or ""])
    autosize(ws, 60)

    ws = wb.create_sheet("Legend")
    for line in [
        "Answer key for the 10 synthetic job cards (Titan AI Shift Logger PoC). Synthetic data, not real Titan data.",
        "Values are AS WRITTEN on the photos: ditto marks resolved, a diagonal Emp No copied to every row.",
        "Red cell = differs from the fill sheet (writer's slip, kept as a real-world test case).",
        "Amber cell = hard to read; either reading in 'Also accept' counts as correct.",
        "Expected flags = what the validation rules raise on a perfect reading. Flagged cards go to supervisor review.",
        "Source of truth: 04_PoC/bakeoff/data/answer_key.json (regenerate this file with make_answer_key_xlsx.py).",
    ]:
        ws.append([line])
    ws.column_dimensions["A"].width = 120

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
