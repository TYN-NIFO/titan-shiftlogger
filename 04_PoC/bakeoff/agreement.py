"""Two-reader agreement check: catch misreads that pass every validation rule.

A wrong value that still looks valid (150 read as 180, and 180 = 180 balances) raises no
flag, so the card would be saved without review. A second, different model reads the same
card; every cell where the two readings disagree goes to the supervisor. Only the
disagreeing cells are shown, not the whole card.

Works on the raw output of a finished bake-off run (no models needed):

    python agreement.py results/20261118_090744 qwen3.8:27b-q4_K_M qwen3-vl:30b-a3b-instruct-q4_K_M
    python agreement.py results/<run> --all          # every pair in the run, best first

The PRIMARY model's reading is what gets saved; the CHECKER only decides what to review.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

from common import HEADER_FIELDS, ROW_FIELDS, answer_key, complete_card, is_blank, master_data, same
from score import score_card
from validate import validate


def safe(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name)


def load(run: Path, model: str) -> dict[str, dict | None]:
    d = run / "raw" / safe(model)
    if not d.is_dir():
        sys.exit(f"no raw output for {model} in {run}")
    return {f.stem: json.loads(f.read_text(encoding="utf-8")).get("card") for f in sorted(d.glob("C*.json"))}


def disagreements(a: dict | None, b: dict | None) -> list[str]:
    """Field paths where two readings of the same card differ."""
    if not a or not b:
        return ["whole card"]
    ca, cb = complete_card(a), complete_card(b)
    out = [f"header.{f}" for f in HEADER_FIELDS
           if not (is_blank(f, ca["header"][f]) and is_blank(f, cb["header"][f]))
           and not same(f, ca["header"][f], cb["header"][f])]
    if len(ca["rows"]) != len(cb["rows"]):
        out.append(f"row count {len(ca['rows'])} vs {len(cb['rows'])}")
    for i, (ra, rb) in enumerate(zip(ca["rows"], cb["rows"])):
        out += [f"rows[{i}].{f}" for f in ROW_FIELDS
                if not (is_blank(f, ra[f]) and is_blank(f, rb[f])) and not same(f, ra[f], rb[f])]
    if not same("total_hours", ca["total_hours"], cb["total_hours"]):
        out.append("total_hours")
    return out


def evaluate(run: Path, primary: str, checker: str, verbose: bool = True) -> dict:
    md = master_data()
    key = {c["card_id"]: c for c in answer_key()["cards"]}
    pa, pb = load(run, primary), load(run, checker)
    res = {"primary": primary, "checker": checker, "cards": 0, "reviewed": 0,
           "cells_to_check": 0, "silent_errors": [], "caught_by_checker": []}
    for cid in sorted(set(pa) & set(pb) & set(key)):
        a, b = pa[cid], pb[cid]
        flags = validate(a, md) if a else [{"flag": "no_rows"}]
        diff = disagreements(a, b)
        sc = score_card(key[cid], a, md)
        reviewed = bool(flags) or bool(diff)
        res["cards"] += 1
        res["reviewed"] += reviewed
        res["cells_to_check"] += len(diff)
        if not reviewed and not sc["perfect"]:
            res["silent_errors"].append(cid)
        if not flags and diff and not sc["perfect"]:
            res["caught_by_checker"].append(cid)
        if verbose:
            wrong = [f["path"] for f in sc["fields"] if not f["correct"]]
            print(f"  {cid}: rule flags {len(flags):>2}  disagree {len(diff):>2} {diff[:4]}"
                  f"{'  ...' if len(diff) > 4 else ''}  primary wrong {wrong or '-'}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="a results/<timestamp> folder from run_bakeoff.py")
    ap.add_argument("primary", nargs="?", help="model whose reading is saved")
    ap.add_argument("checker", nargs="?", help="second model used only to decide what to review")
    ap.add_argument("--all", action="store_true", help="score every primary/checker pair in the run")
    a = ap.parse_args()

    if a.all:
        models = [p.name for p in sorted((a.run / "raw").iterdir()) if p.is_dir()]
        # folder names are safe() versions; map back via the raw files
        names = {}
        for m in models:
            f = next((a.run / "raw" / m).glob("C*.json"), None)
            if f:
                names[m] = json.loads(f.read_text(encoding="utf-8"))["model"]
        rows = [evaluate(a.run, names[p], names[c], verbose=False)
                for p, c in itertools.permutations(names, 2)]
        rows.sort(key=lambda r: (len(r["silent_errors"]), r["cells_to_check"]))
        print("| Primary | Checker | Silent errors | Cards reviewed | Cells to check |")
        print("|---|---|---|---|---|")
        for r in rows[:25]:
            print(f"| {r['primary']} | {r['checker']} | {len(r['silent_errors'])} {r['silent_errors'] or ''} | "
                  f"{r['reviewed']}/{r['cards']} | {r['cells_to_check']} |")
        return 0

    if not (a.primary and a.checker):
        ap.error("give PRIMARY and CHECKER, or --all")
    print(f"Primary {a.primary}  +  checker {a.checker}")
    r = evaluate(a.run, a.primary, a.checker)
    print(f"\nCards reviewed: {r['reviewed']}/{r['cards']}   cells to check: {r['cells_to_check']}   "
          f"silent errors: {len(r['silent_errors'])} {r['silent_errors'] or ''}   "
          f"caught only by the checker: {r['caught_by_checker'] or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
