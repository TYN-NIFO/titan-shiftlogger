"""Thin Ollama client for the chat pipeline (card reading goes through core/reading/extract.py)."""
from __future__ import annotations

import json

import httpx

from app.core.reading.extract import parse_json
from app.services import config


class LLMError(RuntimeError):
    pass


def chat_json(prompt: str, schema: dict, system: str | None = None, model: str | None = None,
              num_predict: int = 1024) -> dict:
    """One Ollama /api/chat call with a forced JSON schema. Returns the parsed object."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model or config.chat_model(),
        "messages": messages,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": num_predict},
    }
    try:
        r = httpx.post(config.ollama_host().rstrip("/") + "/api/chat", json=payload,
                       timeout=config.llm_timeout())
        r.raise_for_status()
        content = r.json().get("message", {}).get("content", "")
        return parse_json(content)
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e


def ollama_reachable(timeout: float = 2.0) -> bool:
    try:
        r = httpx.get(config.ollama_host().rstrip("/") + "/api/tags", timeout=timeout)
        return r.status_code == 200
    except httpx.HTTPError:
        return False
