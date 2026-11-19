"""Titan Shift Logger PoC backend. Run from 05_App/backend:  uvicorn app.main:app --port 8000"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import cards, chat, health, masters
from app.services import config
from app.services.cards import fail_stale_processing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("titan")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        n = fail_stale_processing()
        if n:
            log.info("marked %d interrupted card(s) as failed", n)
    except Exception as e:  # noqa: BLE001 - the DB may be down or not created yet
        log.warning("startup check skipped: %s", e)
    log.info("LLM mode: %s (Ollama %s)", config.llm_mode(), config.ollama_host())
    yield


app = FastAPI(title="Titan Shift Logger PoC", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception):
    log.exception("unhandled error", exc_info=exc)
    return JSONResponse(status_code=500,
                        content={"detail": "Something went wrong on the server. Please try again."})


for r in (health.router, masters.router, cards.router, chat.router):
    app.include_router(r)
