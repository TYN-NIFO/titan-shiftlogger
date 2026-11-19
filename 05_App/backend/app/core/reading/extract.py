"""Send a job-card photo to a local Ollama model and get structured JSON back.

Two modes:
  - single model      "qwen3-vl:8b"            image -> JSON in one call
  - OCR + mapper      "glm-ocr>qwen3-vl:8b"    OCR model reads the text first, then a
                                                vision model maps it into the JSON fields
                                                (it sees both the image and the OCR text)

Uses only the Python standard library to talk to Ollama (http://localhost:11434 by default,
or set OLLAMA_HOST / pass --host).

    python extract.py qwen3-vl:8b ../Synthetic_Job_Cards/Photos/C10_front.jpeg
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from .common import HEADER_FIELDS, PROMPTS, ROW_FIELDS, master_data

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
if not DEFAULT_HOST.startswith("http"):
    DEFAULT_HOST = "http://" + DEFAULT_HOST

ROW_SCHEMA = {
    "type": "object",
    "properties": {**{k: {"type": "string"} for k in ROW_FIELDS},
                   "unclear": {"type": "array", "items": {"type": "string"}}},
    "required": ROW_FIELDS,
}
CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "header": {"type": "object",
                   "properties": {k: {"type": "string"} for k in HEADER_FIELDS},
                   "required": HEADER_FIELDS},
        "rows": {"type": "array", "items": ROW_SCHEMA},
        "total_hours": {"type": "string"},
    },
    "required": ["header", "rows", "total_hours"],
}


# Output cap: a full card is ~1,500 tokens of JSON. Without a cap a model can get stuck
# repeating rows (seen with qwen3-vl:32b: ~1,000 lines, broken JSON, 3 minutes).
MAX_OUTPUT_TOKENS = 3072


def build_prompt(value_lists: bool = True) -> str:
    """The extraction prompt.

    value_lists=True (default) appends the valid employees, machines and codes. Tested on
    18 Nov 2026 with qwen3.8:27b-q4_K_M: with the lists 99.6% field accuracy, without them 85.1%
    (the diagonal Emp No was misread, e.g. 280133 -> 13). Risk: smaller models sometimes "correct"
    a reading into another valid value (604020.11 -> 604020.08), which no rule can catch; the
    two-reader check in agreement.py covers that. value_lists=False is kept for comparison.
    """
    p = (PROMPTS / "extract_prompt.txt").read_text(encoding="utf-8").format()
    if value_lists:
        md = master_data()
        opn = sorted(md["production_codes"]) + [f"{x}{c}" for x in md.get("production_code_prefixes", {})
                                                 for c in md["production_codes"]] + sorted(md["idle_codes"])
        p += ("\n\nValid values (use them to resolve unclear digits, but still copy what is written):\n"
              f"- Employees: {', '.join(md['employees'])}\n"
              f"- Machines: {', '.join(md['machines'])}\n"
              f"- Component codes: {', '.join(md['components'])}\n"
              f"- Opn/Idle codes: {', '.join(opn)}\n"
              f"- Rejection codes: {', '.join(sorted(md['rejection_codes']))}\n"
              f"- Rework codes: {', '.join(sorted(md['rework_codes']))}\n")
    return p


def _post(host: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        host.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _image_b64(path: Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def parse_json(text: str) -> dict:
    """Model text -> dict. Tolerates ```json fences and text around the JSON."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def chat(model: str, prompt: str, image: Path, host: str = DEFAULT_HOST, schema: dict | None = None,
         timeout: int = 600, think: bool = False) -> tuple[str, float]:
    # think=False (default): with a small output budget, thinking models (qwen3.6) spent it all on
    # reasoning and returned an empty answer. think=True gives a much larger budget; on qwen3.8 it
    # gave the same accuracy at twice the time (18 Nov 2026), so it stays off.
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [_image_b64(image)]}],
        "stream": False,
        "think": think,
        "options": {"temperature": 0,
                    "num_ctx": 16384 if think else 8192,
                    "num_predict": 12288 if think else MAX_OUTPUT_TOKENS},
    }
    if schema:
        payload["format"] = schema
    t0 = time.perf_counter()
    data = _post(host, payload, timeout)
    return data.get("message", {}).get("content", ""), time.perf_counter() - t0


def extract(model_spec: str, image: Path, host: str = DEFAULT_HOST, use_schema: bool = True,
            timeout: int = 600, think: bool = False, value_lists: bool = True) -> dict:
    """Run one model spec on one image. Returns {card, raw, ocr_text, seconds, error}."""
    prompt = build_prompt(value_lists)
    schema = CARD_SCHEMA if use_schema else None
    result = {"model": model_spec, "image": str(image), "card": None, "raw": "", "ocr_text": "",
              "seconds": 0.0, "error": ""}
    try:
        if ">" in model_spec:
            ocr_model, mapper = (p.strip() for p in model_spec.split(">", 1))
            ocr_text, t1 = chat(ocr_model, (PROMPTS / "ocr_prompt.txt").read_text(encoding="utf-8"),
                                image, host, None, timeout)
            result["ocr_text"] = ocr_text
            prompt = (prompt + "\n\nAn OCR model has already read the card. Its output is below. "
                      "Use it as a hint, but trust the image where they disagree.\n\n" + ocr_text)
            raw, t2 = chat(mapper, prompt, image, host, schema, timeout, think)
            result["seconds"] = t1 + t2
        else:
            raw, result["seconds"] = chat(model_spec, prompt, image, host, schema, timeout, think)
        result["raw"] = raw
        result["card"] = parse_json(raw)
    except Exception as e:  # noqa: BLE001 - one bad card must not stop the bake-off
        result["error"] = f"{type(e).__name__}: {e}"
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    r = extract(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps(r["card"], indent=2) if r["card"] else r["error"] or r["raw"])
    print(f"\n{r['seconds']:.1f}s")
