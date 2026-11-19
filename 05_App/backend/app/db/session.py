"""Engines and sessions. Two connections: the app (read/write) and the chatbot (read-only role)."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _load_env() -> None:
    """Read 05_App/.env (or .env.example) into os.environ without overriding real env vars."""
    app_root = Path(__file__).resolve().parents[3]          # 05_App
    for name in (".env", ".env.example"):
        p = app_root / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break


_load_env()

DATABASE_URL = os.environ["DATABASE_URL"]
CHAT_DATABASE_URL = os.environ["CHAT_DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
chat_engine = create_engine(CHAT_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    """FastAPI dependency."""
    with SessionLocal() as s:
        yield s
