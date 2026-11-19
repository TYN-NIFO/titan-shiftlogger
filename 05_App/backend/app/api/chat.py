from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.services import chat as svc

router = APIRouter()


class Turn(BaseModel):
    role: str = "user"
    text: str = ""


class ChatRequest(BaseModel):
    question: str
    history: list[Turn] | None = None


@router.post("/api/chat")
async def chat(body: ChatRequest) -> dict:
    history = [t.model_dump() for t in body.history or []]
    return await run_in_threadpool(svc.answer, body.question, history)
