"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Inbox } from "lucide-react";
import { getCard, listCards } from "@/lib/api";
import type { Card } from "@/lib/types";
import CardReview from "./CardReview";

/**
 * The supervisor's work queue: cards held by the checks on the left, the selected card open on the right.
 * Approving a card removes it from the queue and opens the next one.
 */
export default function ReviewQueue() {
  const [queue, setQueue] = useState<Card[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [cleared, setCleared] = useState(0);

  const load = useCallback(async (keep?: number | null) => {
    try {
      const list = await listCards({ status: "needs_review", limit: 50 });
      const cards = await Promise.all(list.map((c) => getCard(c.id)));
      cards.sort((a, b) => a.card_ref.localeCompare(b.card_ref));
      setQueue(cards);
      setSelected((cur) => {
        const want = keep !== undefined ? keep : cur;
        return want && cards.some((c) => c.id === want) ? want : (cards[0]?.id ?? null);
      });
    } catch {
      setQueue([]);
    }
  }, []);

  useEffect(() => {
    load();
    const onChange = () => load();
    window.addEventListener("titan:cards-changed", onChange);
    return () => window.removeEventListener("titan:cards-changed", onChange);
  }, [load]);

  function approved() {
    setCleared((n) => n + 1);
    load(null);
  }

  const total = (queue?.length ?? 0) + cleared;

  return (
    <div className="grid h-full grid-cols-[300px_minmax(0,1fr)]">
      {/* Queue */}
      <aside className="flex min-h-0 flex-col border-r border-line bg-surface" aria-label="Review queue">
        <div className="border-b border-line px-5 pt-6 pb-5">
          <p className="eyebrow">Supervisor · review queue</p>
          <h1 className="mt-1 text-[24px] font-semibold tracking-tight text-ink">
            {queue === null ? "Loading…" : queue.length ? `${queue.length} cards need you` : "All clear"}
          </h1>
          <p className="mt-1 text-[14px] text-muted">Only cards that failed a check. The rest were saved automatically.</p>
          {total > 0 && (
            <div className="mt-4">
              <div className="flex justify-between font-mono text-[12px] text-muted">
                <span>{cleared} approved</span>
                <span>{queue?.length ?? 0} left</span>
              </div>
              <span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-panel">
                <span className="block h-full rounded-full bg-brand-500 transition-all" style={{ width: `${(100 * cleared) / total}%` }} />
              </span>
            </div>
          )}
        </div>

        <ul className="min-h-0 flex-1 overflow-y-auto p-3">
          {queue?.map((c) => {
            const on = c.id === selected;
            const first = c.flags[0];
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setSelected(c.id)}
                  aria-current={on ? "true" : undefined}
                  className={`mb-2 w-full rounded-2xl border p-4 text-left transition-colors ${
                    on ? "border-night bg-night text-white" : "border-line bg-surface hover:border-line-strong hover:bg-panel"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`font-mono text-[17px] font-semibold ${on ? "text-white" : "text-ink"}`}>{c.card_ref}</span>
                    <span className={`font-mono text-[13px] ${on ? "text-night-muted" : "text-muted"}`}>{c.header.mc_no || "M/C ?"}</span>
                    <span className="ml-auto rounded-full bg-signal px-2 py-0.5 font-mono text-[12px] font-semibold text-white">{c.flags.length}</span>
                  </div>
                  {first && (
                    <p className={`mt-2 line-clamp-2 text-[14px] leading-snug ${on ? "text-night-text" : "text-muted"}`}>
                      {first.text}
                      {c.flags.length > 1 ? ` · +${c.flags.length - 1} more` : ""}
                    </p>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      {/* Selected card */}
      <section className="min-h-0">
        {selected ? (
          <CardReview key={selected} id={String(selected)} onApproved={approved} />
        ) : queue === null ? (
          <div className="h-full animate-pulse bg-panel" />
        ) : (
          <div className="grid h-full place-items-center">
            <div className="rise text-center">
              <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-night text-brand-400">
                {cleared ? <CheckCircle2 className="size-8" aria-hidden /> : <Inbox className="size-8" aria-hidden />}
              </span>
              <h2 className="mt-5 text-[26px] font-semibold tracking-tight text-ink">Nothing waiting for review</h2>
              <p className="mt-1 text-[16px] text-muted">
                {cleared ? `${cleared} ${cleared === 1 ? "card" : "cards"} approved and saved to the database.` : "Every card passed its checks."}
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
