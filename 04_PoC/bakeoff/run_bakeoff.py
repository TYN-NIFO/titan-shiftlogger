"""Run every model over every job-card photo, score against the answer key, print a table.

    python run_bakeoff.py --self-test                       # no models: checks scorer + rules
    python run_bakeoff.py --models qwen3-vl:4b qwen3-vl:8b glm-ocr>qwen3-vl:8b
    python run_bakeoff.py --models-file models.txt --host http://VM_IP:11434
    python run_bakeoff.py --models qwen3-vl:8b --cards C01 C04

Output goes to results/<timestamp>/:
    raw/<model>/<card>.json   what the model returned (+ OCR text, timing, errors)
    fields.csv                every scored field: expected vs got
    cards.csv                 per card: accuracy, flags expected vs raised
    summary.md                the comparison table (also printed)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from common import HERE, PHOTOS, answer_key, master_data
from extract import DEFAULT_HOST, extract
from score import score_card, summarise


def safe(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name)


def table(summaries: list[dict]) -> str:
    head = ("| Model | Field acc. | Numbers acc. | Perfect cards | Row count OK | "
            "Flags exact | Marked unclear | Sent to review | Missed reviews | Sec/card | Errors |")
    sep = "|" + "---|" * 11
    lines = [head, sep]
    for s in sorted(summaries, key=lambda x: (x["missed_reviews"], -x["field_accuracy"])):
        n = s["cards"]
        lines.append(
            f"| {s['model']} | {s['field_accuracy']:.1%} | {s['numeric_accuracy']:.1%} | "
            f"{s['perfect_cards']}/{n} | {s['row_count_ok']}/{n} | {s['flags_exact']}/{n} | "
            f"{s['marked_unclear']}/{n} | {s['sent_to_review']}/{n} | {s['missed_reviews']} | "
            f"{s['avg_seconds']:.1f} | {s['errors']} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", default=[], help="Ollama model names; 'ocr>mapper' for a pipeline")
    ap.add_argument("--models-file", type=Path, help="one model spec per line (# comments allowed)")
    ap.add_argument("--cards", nargs="*", help="only these card ids, e.g. C01 C04")
    ap.add_argument("--photos", type=Path, default=PHOTOS)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--no-schema", action="store_true", help="don't force the JSON schema (for models that reject it)")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--think", action="store_true", help="let thinking models reason first (slower, bigger output budget)")
    ap.add_argument("--no-value-lists", dest="value_lists", action="store_false",
                    help="leave the valid employee/machine/code lists out of the prompt (for comparison)")
    ap.add_argument("--self-test", action="store_true", help="score the answer key against itself; no models needed")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up live when output goes to a log file

    models = list(a.models)
    if a.models_file:
        models += [l.split("#")[0].strip() for l in a.models_file.read_text().splitlines()
                   if l.split("#")[0].strip()]
    if a.self_test:
        models = ["answer-key (self-test)"]
    if not models:
        ap.error("give --models, --models-file or --self-test")

    md = master_data()
    cards = [c for c in answer_key()["cards"] if not a.cards or c["card_id"] in a.cards]
    run_dir = a.out / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    summaries, all_fields, all_cards = [], [], []
    for model in models:
        print(f"\n=== {model}")
        scores, secs, errors = [], [], 0
        raw_dir = run_dir / "raw" / safe(model)
        raw_dir.mkdir(parents=True, exist_ok=True)
        for kc in cards:
            if a.self_test:
                res = {"model": model, "card": kc, "seconds": 0.0, "error": ""}
            else:
                img = a.photos / kc["photo"]
                if not img.exists():
                    print(f"  {kc['card_id']}: photo missing ({img})")
                    continue
                res = extract(model, img, a.host, use_schema=not a.no_schema, timeout=a.timeout,
                              think=a.think, value_lists=a.value_lists)
                (raw_dir / f"{kc['card_id']}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
            if res["error"]:
                errors += 1
            sc = score_card(kc, res["card"], md)
            scores.append(sc)
            secs.append(res["seconds"])
            wrong = [f"{f['path']}: {f['expected'] or '-'} -> {f['got'] or '-'}" for f in sc["fields"] if not f["correct"]]
            print(f"  {kc['card_id']}: {sc['accuracy']:.0%} ({sc['n_correct']}/{sc['n_fields']})  "
                  f"rows {sc['rows_got']}/{sc['rows_expected']}  flags {sc['got_flags'] or '-'}  "
                  f"{res['seconds']:.1f}s{'  ERROR ' + res['error'] if res['error'] else ''}")
            for w in wrong[:6]:
                print(f"      x {w}")
            if len(wrong) > 6:
                print(f"      ... {len(wrong) - 6} more")
            for f in sc["fields"]:
                all_fields.append({"model": model, "card_id": kc["card_id"], **f})
            all_cards.append({"model": model, **{k: v for k, v in sc.items() if k != "fields"}})
        summaries.append(summarise(model, scores, secs, errors))

    with open(run_dir / "fields.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["model", "card_id", "path", "field", "expected", "got", "correct"])
        w.writeheader()
        w.writerows(all_fields)
    with open(run_dir / "cards.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(all_cards[0].keys()) if all_cards else ["model"])
        w.writeheader()
        for r in all_cards:
            w.writerow({k: ("; ".join(v) if isinstance(v, list) else v) for k, v in r.items()})

    md_table = table(summaries)
    (run_dir / "summary.md").write_text(
        f"# Bake-off {run_dir.name}\n\nCards: {', '.join(c['card_id'] for c in cards)}  \n"
        f"Host: {a.host}  \nThinking: {'on' if a.think else 'off'}  \n"
        f"Value lists in prompt: {'yes' if a.value_lists else 'no'}\n\n{md_table}\n\n"
        "- **Field acc.**: filled fields read correctly (unclear cells accept either reading).\n"
        "- **Numbers acc.**: same, only digits/codes/times/dates.\n"
        "- **Flags exact**: validation raised exactly the expected flags on the model's reading.\n"
        "- **Marked unclear**: cards where the reader itself marked at least one cell unclear (sends it to review).\n"
        "- **Missed reviews**: cards with a wrong value that raise no flag at all, so they would be auto-saved. "
        "Counts every card, including clean ones. Must be 0.\n",
        encoding="utf-8")
    print("\n" + md_table)
    print(f"\nSaved to {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
