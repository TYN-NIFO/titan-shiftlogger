"""Runtime settings, read from the environment (05_App/.env is loaded by app.db.session)."""
from __future__ import annotations

import os
from pathlib import Path

import app.db.session  # noqa: F401  - loads 05_App/.env into os.environ

BACKEND_DIR = Path(__file__).resolve().parents[2]      # 05_App/backend
REPO_ROOT = BACKEND_DIR.parents[1]                     # TITAN

TODAY = "2026-11-18"                                   # "today" in the demo


def _host(v: str) -> str:
    v = v.strip() or "http://localhost:11434"
    return v if v.startswith("http") else "http://" + v


def llm_mode() -> str:
    return "stub" if os.environ.get("LLM_MODE", "live").strip().lower() == "stub" else "live"


def ollama_host() -> str:
    return _host(os.environ.get("OLLAMA_HOST", "http://localhost:11434"))


def read_model() -> str:
    return os.environ.get("READ_MODEL", "qwen3.8:27b-q4_K_M")


def chat_model() -> str:
    return os.environ.get("CHAT_MODEL", "qwen3.8:27b-q4_K_M")


def llm_timeout() -> int:
    return int(os.environ.get("LLM_TIMEOUT", "120"))


def upload_dir() -> Path:
    """UPLOAD_DIR, resolved relative to the repo root when not absolute."""
    p = Path(os.environ.get("UPLOAD_DIR", "05_App/backend/storage/cards"))
    if not p.is_absolute():
        p = REPO_ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_image(image_path: str | None) -> Path | None:
    """Stored image paths may be absolute, repo-relative, backend-relative or a bare file name."""
    if not image_path:
        return None
    p = Path(image_path)
    candidates = [p] if p.is_absolute() else [REPO_ROOT / p, BACKEND_DIR / p, upload_dir() / p,
                                                 upload_dir() / p.name]
    for c in candidates:
        if c.is_file():
            return c
    return None
