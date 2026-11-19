"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, ArrowUp, Loader2 } from "lucide-react";
import { ApiError, ask } from "@/lib/api";
import type { ChatAnswer, ChatTurn } from "@/lib/types";
import { useElapsed } from "@/lib/useElapsed";
import AnswerView from "./AnswerView";

export const DEMO_QUESTIONS = [
  "Which CNC machine lost the most hours to breakdowns in the last four months?",
  "Who has the highest absenteeism?",
  "Who's least productive?",
];

type Message =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; answer: ChatAnswer }
  | { id: number; role: "error"; text: string; question: string };

// Kept at module level so the thread survives moving between pages.
let savedThread: Message[] = [];
let seq = 1;

export default function ChatApp() {
  const [messages, setMessages] = useState<Message[]>(savedThread);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const elapsed = useElapsed(busy);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const lastQuestionRef = useRef<HTMLDivElement>(null);
  const lastUserId = [...messages].reverse().find((m) => m.role === "user")?.id;

  useEffect(() => {
    savedThread = messages;
    const last = messages[messages.length - 1];
    if (!busy && last?.role === "assistant") {
      // Show the question and the top of its answer, not the bottom of a long answer.
      lastQuestionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, busy]);

  useEffect(() => {
    inputRef.current?.focus();
    // /chat?q=... asks straight away (handy for links and recording).
    const q = new URLSearchParams(window.location.search).get("q");
    if (q && savedThread.length === 0) {
      window.history.replaceState(null, "", "/chat");
      send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    const history: ChatTurn[] = messages.flatMap((m): ChatTurn[] =>
      m.role === "user" ? [{ role: "user", text: m.text }] : m.role === "assistant" ? [{ role: "assistant", text: m.answer.text }] : [],
    );
    setMessages((ms) => [...ms, { id: seq++, role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const answer = await ask(q, history.slice(-6));
      setMessages((ms) => [...ms, { id: seq++, role: "assistant", answer }]);
    } catch (e) {
      const text = e instanceof ApiError ? e.message : "Sorry, something went wrong while answering. Please try again.";
      setMessages((ms) => [...ms, { id: seq++, role: "error", text, question: q }]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  const empty = messages.length === 0 && !busy;

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl px-10 py-10">
          {empty ? (
            <EmptyState onPick={send} />
          ) : (
            <div className="space-y-8">
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} ref={m.id === lastUserId ? lastQuestionRef : undefined} className="flex scroll-mt-6 justify-end">
                    <div className="max-w-[75%] rounded-2xl rounded-br-md bg-night px-5 py-3 text-[17px] text-white">{m.text}</div>
                  </div>
                ) : m.role === "assistant" ? (
                  <AnswerView key={m.id} answer={m.answer} />
                ) : (
                  <div key={m.id} className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-5 text-lg text-red-800">
                    <AlertCircle className="mt-0.5 size-6 shrink-0" aria-hidden />
                    <div className="flex-1">{m.text}</div>
                    <button
                      type="button"
                      onClick={() => send(m.question)}
                      className="rounded-lg border border-red-300 bg-white px-4 py-1.5 text-base font-medium hover:bg-red-100"
                    >
                      Try again
                    </button>
                  </div>
                ),
              )}
              {busy && (
                <div className="rise flex items-center gap-3 rounded-3xl border border-line bg-surface px-6 py-5 text-[17px] text-muted">
                  <Loader2 className="size-5 animate-spin text-brand-500" aria-hidden />
                  Querying the job-card database…
                  <span className="tabular-nums text-subtle">{elapsed} s</span>
                </div>
              )}
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 px-10">
        <form
          className="mx-auto mb-6 flex w-full max-w-4xl items-end gap-2 rounded-2xl border border-line-strong bg-surface p-2 shadow-[0_2px_12px_rgba(16,24,40,0.06)] focus-within:border-brand-500"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
            rows={1}
            placeholder="Ask about downtime, absenteeism or output…"
            aria-label="Your question"
            className="max-h-40 min-h-12 flex-1 resize-none bg-transparent px-4 py-3 text-[17px] outline-none placeholder:text-subtle focus-visible:outline-none"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            aria-label="Ask"
            className="grid size-12 shrink-0 place-items-center rounded-xl bg-night text-brand-400 transition-colors hover:bg-night-2 disabled:bg-panel disabled:text-subtle"
          >
            <ArrowUp className="size-5" aria-hidden />
          </button>
        </form>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center pt-20 text-center">
      <p className="eyebrow">Ask the data</p>
      <h1 className="mt-2 text-[34px] font-semibold tracking-tight text-ink">What do you want to know about the shop floor?</h1>
      <p className="mt-3 max-w-2xl text-[17px] text-muted">
        Answers come straight from the approved job cards in the database, with the query behind each one.
      </p>
      <div className="mt-10 flex w-full max-w-3xl flex-col gap-3">
        {DEMO_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="group flex items-center justify-between gap-4 rounded-2xl border border-line bg-surface px-5 py-4 text-left text-[17px] text-ink transition-colors hover:border-night hover:bg-night hover:text-white"
          >
            {q}
            <ArrowUp className="size-4 shrink-0 rotate-45 text-subtle group-hover:text-brand-400" aria-hidden />
          </button>
        ))}
      </div>
    </div>
  );
}
