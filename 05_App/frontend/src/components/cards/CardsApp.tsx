"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, AlertTriangle, Camera, Database, ImageUp, Loader2, Upload, X } from "lucide-react";
import { ApiError, getCardsSummary, listCards, notifyCardsChanged, uploadCard } from "@/lib/api";
import type { CardsSummary } from "@/lib/api";
import type { CardSummary } from "@/lib/types";
import { timeAgo } from "@/lib/format";
import StatusPill from "./StatusPill";
import Pipeline from "./Pipeline";

type Filter = "all" | "review" | "photo";

const TABS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "photo", label: "Photo cards" },
];

const POLL_MS = 3000;

export default function CardsApp({ initialFilter }: { initialFilter: Filter }) {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>(initialFilter);
  const [cards, setCards] = useState<CardSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [summary, setSummary] = useState<CardsSummary | null>(null);

  const load = useCallback(async () => {
    try {
      const q = filter === "review" ? { status: "needs_review" } : filter === "photo" ? { source: "photo" } : {};
      setCards(await listCards({ ...q, limit: 50 }));
      getCardsSummary().then(setSummary).catch(() => {});
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load the job cards. Please try again.");
    }
  }, [filter]);

  useEffect(() => {
    setCards(null);
    load();
  }, [load]);

  // Keep "Reading…" rows fresh.
  useEffect(() => {
    if (!cards?.some((c) => c.status === "processing")) return;
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [cards, load]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[1560px] px-8 py-7">
        <div className="flex items-end justify-between gap-6">
          <div>
            <p className="eyebrow">{initialFilter === "review" ? "Supervisor" : "Job cards"}</p>
            <h1 className="mt-1 text-[30px] font-semibold tracking-tight text-ink">
              {initialFilter === "review" ? "Cards waiting for a person" : "Every card, read and checked"}
            </h1>
            <p className="mt-1 text-[16px] text-muted">
              Clean cards save automatically. Cards with a doubt wait here for the supervisor.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowUpload(true)}
            className="flex items-center gap-2 rounded-xl bg-ink px-5 py-3 text-[15px] font-medium text-white transition-colors hover:bg-night-2"
          >
            <Upload className="size-[18px]" aria-hidden />
            Upload job card
          </button>
        </div>

        <Pipeline s={summary} />

        <div className="mt-7 inline-flex gap-1 rounded-xl border border-line bg-surface p-1" role="tablist" aria-label="Filter cards">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={filter === t.key}
              onClick={() => setFilter(t.key)}
              className={`rounded-lg px-4 py-2 text-[15px] font-medium transition-colors ${
                filter === t.key ? "bg-night text-white" : "text-muted hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="mt-4 overflow-hidden rounded-3xl border border-line bg-surface">
          {error ? (
            <div className="flex items-center gap-3 p-8 text-lg text-bad">
              <AlertCircle className="size-6" aria-hidden />
              {error}
              <button type="button" onClick={load} className="ml-auto rounded-lg px-4 py-2 font-medium ring-1 ring-bad/30 hover:bg-bad-bg">
                Try again
              </button>
            </div>
          ) : cards === null ? (
            <SkeletonRows />
          ) : cards.length === 0 ? (
            <div className="p-12 text-center text-[16px] text-muted">
              {filter === "review" ? "Nothing waiting for review." : "No job cards yet. Upload one to start."}
            </div>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line bg-panel font-mono text-[12px] tracking-[0.06em] text-muted uppercase">
                  <th className="px-6 py-4">Card</th>
                  <th className="px-6 py-4">Date</th>
                  <th className="px-6 py-4">M/C No</th>
                  <th className="px-6 py-4">Emp No</th>
                  <th className="px-6 py-4">Checks</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Added</th>
                </tr>
              </thead>
              <tbody>
                {cards.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => router.push(`/cards/${c.id}`)}
                    className="cursor-pointer border-b border-line text-[16px] text-ink last:border-0 hover:bg-canvas"
                  >
                    <td className="px-6 py-4">
                      <Link href={`/cards/${c.id}`} className="flex items-center gap-3 font-mono font-medium text-ink" onClick={(e) => e.stopPropagation()}>
                        {c.source === "photo" ? (
                          <span className="grid size-8 place-items-center rounded-lg bg-night text-brand-400"><Camera className="size-4" aria-label="Photo card" /></span>
                        ) : (
                          <span className="grid size-8 place-items-center rounded-lg bg-panel text-subtle"><Database className="size-4" aria-label="Synthetic card" /></span>
                        )}
                        {c.card_ref}
                      </Link>
                    </td>
                    <td className="px-6 py-4 font-mono text-[15px]">{c.card_date || <Missing />}</td>
                    <td className="px-6 py-4 font-mono text-[15px]">{c.mc_no || <Missing />}</td>
                    <td className="px-6 py-4 font-mono text-[15px]">{c.emp_no || <Missing />}</td>
                    <td className="px-6 py-4">
                      {c.status === "processing" ? (
                        <span className="text-slate-400">–</span>
                      ) : c.flag_count > 0 ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-signal-bg px-2.5 py-0.5 text-[14px] font-medium text-signal-text">
                          <AlertTriangle className="size-4" aria-hidden />
                          {c.flag_count} {c.flag_count === 1 ? "check failed" : "checks failed"}
                        </span>
                      ) : (
                        <span className="text-muted">All passed</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <StatusPill status={c.status} />
                    </td>
                    <td className="px-6 py-4 text-right text-[15px] text-muted">{timeAgo(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showUpload && (
        <UploadDialog
          onClose={() => setShowUpload(false)}
          onUploaded={(id) => {
            notifyCardsChanged();
            router.push(`/cards/${id}`);
          }}
        />
      )}
    </div>
  );
}

function Missing() {
  return <span className="text-subtle">–</span>;
}

function SkeletonRows() {
  return (
    <div className="divide-y divide-slate-100">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex items-center gap-8 px-6 py-5">
          <div className="h-5 w-28 animate-pulse rounded bg-slate-200" />
          <div className="h-5 w-24 animate-pulse rounded bg-slate-100" />
          <div className="h-5 w-28 animate-pulse rounded bg-slate-100" />
          <div className="h-5 w-24 animate-pulse rounded bg-slate-100" />
          <div className="ml-auto h-7 w-32 animate-pulse rounded-full bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

const ACCEPT = ["image/jpeg", "image/png"];

function UploadDialog({ onClose, onUploaded }: { onClose: () => void; onUploaded: (id: number) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function upload(file: File | undefined) {
    if (!file) return;
    if (!ACCEPT.includes(file.type) && !/\.(jpe?g|png)$/i.test(file.name)) {
      setError("Please choose a JPEG or PNG photo of the job card.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await uploadCard(file);
      onUploaded(res.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The upload didn't work. Please try again.");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-ink/40 p-8 backdrop-blur-[2px]" onClick={() => !busy && onClose()}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-title"
        className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 id="upload-title" className="text-[22px] font-semibold text-ink">
            Upload job card
          </h2>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close" className="rounded-lg p-2 text-muted hover:bg-panel">
            <X className="size-6" aria-hidden />
          </button>
        </div>
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            upload(e.dataTransfer.files?.[0]);
          }}
          className={`mt-6 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-8 py-16 text-center transition-colors ${
            drag ? "border-brand-500 bg-brand-50" : "border-line-strong hover:border-brand-400 hover:bg-brand-50/60"
          }`}
        >
          {busy ? (
            <>
              <Loader2 className="size-12 animate-spin text-brand-500" aria-hidden />
              <span className="mt-4 text-lg font-medium text-ink">Uploading…</span>
            </>
          ) : (
            <>
              <ImageUp className="size-12 text-brand-500" aria-hidden />
              <span className="mt-4 text-xl font-semibold text-ink">Drop the scanned card here</span>
              <span className="mt-1.5 text-base text-muted">or click to choose a file · JPEG or PNG</span>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png"
            className="sr-only"
            disabled={busy}
            onChange={(e) => upload(e.target.files?.[0])}
          />
        </label>
        {error && (
          <p className="mt-4 flex items-center gap-2 text-base text-bad">
            <AlertCircle className="size-5" aria-hidden />
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
