import type { Card, CardEdit, CardSummary, ChatAnswer, ChatTurn, Health, Masters } from "./types";
import * as mock from "./mock";

/** Base URL of the backend service. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

/** Dev-only fixtures. Off unless NEXT_PUBLIC_MOCK=1. Never used for the video. */
export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

/** An error whose message is safe to show to a user. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public offline = false,
  ) {
    super(message);
  }
}

const FRIENDLY: Record<number, string> = {
  400: "That request didn't look right. Please check and try again.",
  404: "We couldn't find that item.",
  413: "That file is too large.",
  415: "Please upload a JPEG or PNG photo of the job card.",
  422: "Some values couldn't be accepted. Please check and try again.",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("Can't reach the server right now. Please check it's running and try again.", 0, true);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      if (typeof body?.detail === "string" && body.detail.length < 200) detail = body.detail;
    } catch {
      /* not JSON */
    }
    const msg = res.status < 500 && detail ? detail : FRIENDLY[res.status] || "Something went wrong on the server. Please try again.";
    throw new ApiError(msg, res.status);
  }
  return (await res.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export function getHealth(): Promise<Health> {
  return MOCK ? mock.getHealth() : request<Health>("/api/health");
}

export function getMasters(): Promise<Masters> {
  return MOCK ? mock.getMasters() : request<Masters>("/api/masters");
}

export function listCards(q: { status?: string; source?: string; limit?: number } = {}): Promise<CardSummary[]> {
  if (MOCK) return mock.listCards(q);
  const p = new URLSearchParams();
  if (q.status) p.set("status", q.status);
  if (q.source) p.set("source", q.source);
  p.set("limit", String(q.limit ?? 50));
  return request<CardSummary[]>(`/api/cards?${p}`);
}

export interface CardsSummary {
  total: number;
  approved: number;
  needs_review: number;
  failed: number;
  processing: number;
  photo_total: number;
  photo_auto_approved: number;
  photo_supervisor_approved: number;
}

export function getCardsSummary(): Promise<CardsSummary> {
  if (MOCK)
    return Promise.resolve({ total: 8161, approved: 8154, needs_review: 4, failed: 0, processing: 0, photo_total: 7, photo_auto_approved: 3, photo_supervisor_approved: 0 });
  return request<CardsSummary>(`/api/cards/summary`);
}

export function uploadCard(file: File): Promise<{ id: number; status: string }> {
  if (MOCK) return mock.uploadCard(file);
  const fd = new FormData();
  fd.append("file", file);
  return request(`/api/cards`, { method: "POST", body: fd });
}

export function getCard(id: number | string): Promise<Card> {
  return MOCK ? mock.getCard(Number(id)) : request<Card>(`/api/cards/${id}`);
}

export function saveCard(id: number, edit: CardEdit): Promise<Card> {
  return MOCK ? mock.saveCard(id, edit) : request<Card>(`/api/cards/${id}`, json("PUT", edit));
}

export function approveCard(id: number): Promise<Card> {
  return MOCK ? mock.approveCard(id) : request<Card>(`/api/cards/${id}/approve`, json("POST", { by: "supervisor" }));
}

export function ask(question: string, history: ChatTurn[] = []): Promise<ChatAnswer> {
  return MOCK ? mock.ask(question) : request<ChatAnswer>(`/api/chat`, json("POST", { question, history }));
}

/** The card image's URL. The API returns a path relative to the backend. */
export function imageSrc(card: Pick<Card, "image_url">): string | null {
  const u = card.image_url;
  if (!u) return null;
  if (/^https?:\/\//.test(u) || MOCK) return u;
  return `${API_URL}${u.startsWith("/") ? "" : "/"}${u}`;
}

/** Tells the top bar (review count) that cards changed. */
export function notifyCardsChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("titan:cards-changed"));
}

