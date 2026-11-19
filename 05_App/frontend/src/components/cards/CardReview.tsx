"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, AlertTriangle, ArrowLeft, Check, CheckCircle2, Loader2, Plus, Save, Sparkles } from "lucide-react";
import { ApiError, approveCard, getCard, getMasters, imageSrc, notifyCardsChanged, saveCard } from "@/lib/api";
import type { Card, CardEdit, CardRow, Flag, HeaderField, Masters, RowField } from "@/lib/types";
import { HEADER_FIELDS, ROW_FIELDS } from "@/lib/types";
import { HEADER_LABELS, ROW_LABELS, whereLabel } from "@/lib/format";
import { useElapsed } from "@/lib/useElapsed";
import { useToast } from "@/components/Toast";
import ImageViewer from "./ImageViewer";
import StatusPill from "./StatusPill";

const POLL_MS = 1500;

/** Column widths (px) for the 14 row fields, sized for 1920 px wide screens. */
const COL_W: Record<RowField, number> = {
  emp_no: 82,
  shift: 56,
  opn_code: 108,
  wo_no: 70,
  comp_code: 72,
  qty_prod: 70,
  qty_accp: 70,
  rej_code: 60,
  rej_qty: 56,
  rework_code: 68,
  rework_qty: 64,
  time_from: 68,
  time_to: 68,
  total_hours: 70,
};

const rowKey = (i: number, f: RowField) => `rows[${i}].${f}`;
const headerKey = (f: HeaderField) => `header.${f}`;
const TOTAL_KEY = "total_hours";

function toEdit(c: Card): CardEdit {
  return {
    header: { ...c.header },
    rows: c.rows.map((r) => ({ ...r, unclear: [...(r.unclear ?? [])] })),
    total_hours: c.total_hours ?? "",
  };
}

function emptyRow(): CardRow {
  const r = { unclear: [] } as unknown as CardRow;
  for (const f of ROW_FIELDS) r[f] = "";
  return r;
}

/**
 * One card: photo on the left, what the AI read on the right.
 * `onApproved` is set when the card is shown inside the Review queue (no back arrow; the queue moves to the next card).
 */
export default function CardReview({ id, onApproved }: { id: string; onApproved?: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [card, setCard] = useState<Card | null>(null);
  const [draft, setDraft] = useState<CardEdit | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [masters, setMasters] = useState<Masters | null>(null);
  const [busy, setBusy] = useState<"save" | "approve" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const [pulse, setPulse] = useState<{ key: string; n: number } | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});

  const cardRef = useRef<Card | null>(null);
  const processing = card?.status === "processing";
  const elapsed = useElapsed(!card || processing);

  const load = useCallback(async () => {
    try {
      const c = await getCard(id);
      const prev = cardRef.current;
      // Fill the editor on first load and when reading finishes.
      if (!prev || prev.status === "processing") {
        setDraft(toEdit(c));
        if (prev?.status === "processing" && c.status !== "processing") notifyCardsChanged();
      }
      cardRef.current = c;
      setCard(c);
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Couldn't open this card. Please try again.");
    }
  }, [id]);

  useEffect(() => {
    load();
    getMasters()
      .then(setMasters)
      .catch(() => {});
  }, [load]);

  useEffect(() => {
    if (!processing) return;
    const t = setTimeout(load, POLL_MS);
    return () => clearTimeout(t);
  }, [processing, card, load]);

  const flagsByKey = useMemo(() => {
    const m = new Map<string, Flag[]>();
    for (const f of card?.flags ?? []) {
      if (!f.where) continue;
      m.set(f.where, [...(m.get(f.where) ?? []), f]);
    }
    return m;
  }, [card]);

  const unclear = useMemo(() => {
    const s = new Set<string>();
    card?.rows.forEach((r, i) =>
      (r.unclear ?? []).forEach((f) => s.add(f.startsWith("header.") ? f : rowKey(i, f as RowField))),
    );
    return s;
  }, [card]);

  const dirty = useMemo(() => !!card && !!draft && JSON.stringify(toEdit(card)) !== JSON.stringify(draft), [card, draft]);

  function setValue(key: string, value: string) {
    setDraft((d) => {
      if (!d) return d;
      if (key === TOTAL_KEY) return { ...d, total_hours: value };
      if (key.startsWith("header.")) return { ...d, header: { ...d.header, [key.slice(7)]: value } };
      const m = /^rows\[(\d+)\]\.(\w+)$/.exec(key);
      if (!m) return d;
      const i = Number(m[1]);
      const rows = d.rows.map((r, ri) => (ri === i ? { ...r, [m[2]]: value } : r));
      return { ...d, rows };
    });
  }

  function editable(key: string | null): boolean {
    if (!key || !draft) return false;
    if (key === TOTAL_KEY) return true;
    if (key.startsWith("header.")) return (HEADER_FIELDS as readonly string[]).includes(key.slice(7));
    const m = /^rows\[(\d+)\]\.(\w+)$/.exec(key);
    return !!m && Number(m[1]) < draft.rows.length && (ROW_FIELDS as readonly string[]).includes(m[2]);
  }

  function showCell(key: string | null) {
    if (!key || !editable(key)) return;
    setPulse((p) => ({ key, n: (p?.n ?? 0) + 1 }));
    const el = document.getElementById(`cell-${key}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    (el as HTMLInputElement | null)?.focus({ preventScroll: true });
  }

  function applySuggestion(f: Flag) {
    if (!f.where || !f.suggestion) return;
    setValue(f.where, f.suggestion);
    setApplied((a) => ({ ...a, [`${f.flag}|${f.where}`]: f.suggestion! }));
    showCell(f.where);
  }

  async function onSave() {
    if (!card || !draft) return;
    setBusy("save");
    setActionError(null);
    try {
      const c = await saveCard(card.id, draft);
      cardRef.current = c;
      setCard(c);
      setDraft(toEdit(c));
      setApplied({});
      notifyCardsChanged();
      toast(c.flags.length ? "Changes saved. The card was checked again." : "Changes saved. All checks passed.");
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Couldn't save the changes. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function onApprove() {
    if (!card || !draft) return;
    setBusy("approve");
    setActionError(null);
    try {
      if (dirty) await saveCard(card.id, draft);
      await approveCard(card.id);
      notifyCardsChanged();
      toast("Saved to the database");
      if (onApproved) {
        setBusy(null);
        onApproved();
      } else {
        router.push("/cards");
      }
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Couldn't approve the card. Please try again.");
      setBusy(null);
    }
  }

  if (loadError && !card) {
    return (
      <div className="mx-auto max-w-3xl px-8 py-16">
        <div className="flex items-center gap-3 rounded-2xl border border-bad/30 bg-bad-bg p-6 text-lg text-bad">
          <AlertCircle className="size-6" aria-hidden />
          {loadError}
          <Link href="/cards" className="ml-auto rounded-lg bg-white px-4 py-2 font-medium ring-1 ring-bad/30">
            Back to job cards
          </Link>
        </div>
      </div>
    );
  }

  const src = card ? imageSrc(card) : null;

  return (
    <div className={`grid h-full ${onApproved ? "grid-cols-[minmax(0,27fr)_minmax(0,73fr)]" : "grid-cols-[minmax(0,34fr)_minmax(0,66fr)]"}`}>
      <section className="relative min-h-0" aria-label="Card photo">
        <span className="absolute top-5 left-6 z-10 font-mono text-[12px] tracking-[0.08em] text-night-muted uppercase">Scanned card · as written</span>
        {card ? <ImageViewer src={src} alt={`Job card ${card.card_ref}`} /> : <div className="h-full animate-pulse bg-slate-200/70" />}
      </section>

      <section className="min-h-0 overflow-y-auto bg-surface" aria-label="What the AI read">
        <div className="px-7 py-7">
          {/* Title and actions */}
          <div className="flex items-start gap-4">
            {!onApproved && (
              <Link href="/cards" aria-label="Back to job cards" className="mt-0.5 rounded-lg p-2 text-muted hover:bg-panel hover:text-ink">
                <ArrowLeft className="size-6" aria-hidden />
              </Link>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3">
                <h1 className="text-[26px] font-semibold tracking-tight text-ink">Job card <span className="font-mono">{card?.card_ref ?? ""}</span></h1>
                {card && <StatusPill status={card.status} large />}
              </div>
              {card && !processing && card.status !== "failed" && (
                <p className="mt-1 flex items-center gap-2 text-[15px] text-muted">
                  <Sparkles className="size-4 text-brand-500" aria-hidden />
                  Read by AI{card.read_seconds ? ` in ${card.read_seconds.toFixed(1)} s` : ""}. Check it against the photo.
                </p>
              )}
            </div>
            {card && !processing && (
              <div className="flex shrink-0 items-center gap-3">
                <button
                  type="button"
                  onClick={onSave}
                  disabled={!dirty || !!busy}
                  className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-[15px] font-medium text-ink ring-1 ring-line-strong transition-colors hover:bg-panel disabled:text-subtle disabled:ring-line disabled:hover:bg-transparent"
                >
                  {busy === "save" ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <Save className="size-5" aria-hidden />}
                  Save changes
                </button>
                <button
                  type="button"
                  onClick={onApprove}
                  disabled={!!busy || (card.status === "approved" && !dirty)}
                  className="flex items-center gap-2 rounded-xl bg-night px-5 py-2.5 text-[15px] font-semibold text-white transition-colors hover:bg-night-2 disabled:bg-panel disabled:text-subtle"
                >
                  {busy === "approve" ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <Check className="size-5 text-brand-400" aria-hidden />}
                  {card.status === "approved" && !dirty ? "Approved" : "Approve"}
                </button>
              </div>
            )}
          </div>

          {actionError && (
            <p className="mt-4 flex items-center gap-2 rounded-xl bg-bad-bg px-4 py-3 text-base text-bad">
              <AlertCircle className="size-5" aria-hidden />
              {actionError}
            </p>
          )}

          {!card || processing ? (
            <ReadingSkeleton seconds={elapsed} />
          ) : (
            <>
              {card.status === "failed" && (
                <div className="mt-6 flex items-start gap-3 rounded-xl border border-bad/30 bg-bad-bg p-5 text-lg text-bad">
                  <AlertCircle className="mt-0.5 size-6 shrink-0" aria-hidden />
                  <div>
                    <p className="font-semibold">The AI couldn&apos;t read this card.</p>
                    <p className="mt-1 text-base">Try uploading a clearer photo, or type the fields in below.</p>
                  </div>
                </div>
              )}

              {card.flags.length > 0 ? (
                <FlagList
                  flags={card.flags}
                  applied={applied}
                  onShow={showCell}
                  onHover={setFocusKey}
                  onUse={applySuggestion}
                  canEdit={editable}
                />
              ) : (
                card.status !== "failed" && (
                  <div className="mt-6 flex items-center gap-3 rounded-2xl border border-ok/20 bg-ok-bg px-5 py-4 text-[16px] text-ok">
                    <CheckCircle2 className="size-5" aria-hidden />
                    All checks passed: codes, quantities, hours and master lists.
                  </div>
                )
              )}

              {draft && (
                <>
                  <HeaderFields
                    draft={draft}
                    masters={masters}
                    flagsByKey={flagsByKey}
                    unclear={unclear}
                    focusKey={focusKey}
                    pulse={pulse}
                    onChange={setValue}
                  />
                  <RowGrid
                    draft={draft}
                    masters={masters}
                    flagsByKey={flagsByKey}
                    unclear={unclear}
                    focusKey={focusKey}
                    pulse={pulse}
                    onChange={setValue}
                    onAddRow={() => setDraft((d) => (d ? { ...d, rows: [...d.rows, emptyRow()] } : d))}
                  />
                </>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}

/** Replace internal paths like rows[0].opn_code in a flag detail with readable labels. */
function friendlyDetail(d: string): string {
  return d.replace(/rows\[\d+\]\.\w+|header\.\w+/g, (m) => whereLabel(m));
}

function ReadingSkeleton({ seconds }: { seconds: number }) {
  return (
    <div className="mt-8" aria-live="polite">
      <div className="flex items-center gap-3 rounded-2xl border border-brand-100 bg-brand-50 px-5 py-4 text-[16px] font-medium text-deep-900">
        <Loader2 className="size-5 animate-spin text-brand-600" aria-hidden />
        AI is reading the card…
        <span className="tabular-nums text-grey-brand">{seconds} s</span>
      </div>
      <div className="mt-8 grid grid-cols-5 gap-4">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 w-20 animate-pulse rounded bg-slate-200" />
            <div className="h-11 animate-pulse rounded-lg bg-slate-100" />
          </div>
        ))}
      </div>
      <div className="mt-8 space-y-3">
        <div className="h-10 animate-pulse rounded-lg bg-slate-200/80" />
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-slate-100" />
        ))}
      </div>
    </div>
  );
}

function FlagList({
  flags,
  applied,
  onShow,
  onHover,
  onUse,
  canEdit,
}: {
  flags: Flag[];
  applied: Record<string, string>;
  onShow: (k: string | null) => void;
  onHover: (k: string | null) => void;
  onUse: (f: Flag) => void;
  canEdit: (k: string | null) => boolean;
}) {
  return (
    <div className="mt-6 overflow-hidden rounded-3xl border border-signal/30 bg-surface">
      <div className="flex items-center gap-3 bg-signal px-5 py-3 text-white">
        <AlertTriangle className="size-5" aria-hidden />
        <h2 className="text-[16px] font-semibold">
          Held for the supervisor · {flags.length === 1 ? "1 check failed" : `${flags.length} checks failed`}
        </h2>
        <span className="ml-auto font-mono text-[12px] text-white/85">click a check to jump to the cell</span>
      </div>
      <ul className="divide-y divide-line px-2 py-1">
        {flags.map((f, i) => {
          const done = applied[`${f.flag}|${f.where}`];
          return (
            <li
              key={`${f.flag}-${f.where}-${i}`}
              onMouseEnter={() => onHover(f.where)}
              onMouseLeave={() => onHover(null)}
              className="flex items-center gap-4 rounded-lg px-3 py-3 hover:bg-canvas"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-signal-bg font-mono text-[13px] font-semibold text-signal-text">
                {String(i + 1).padStart(2, "0")}
              </span>
              <button
                type="button"
                onClick={() => onShow(f.where)}
                disabled={!canEdit(f.where)}
                className="min-w-0 flex-1 text-left disabled:cursor-default"
              >
                <span className="block text-[16px] font-medium text-ink">{f.text}</span>
                <span className="mt-1 flex flex-wrap items-center gap-x-3 text-[14px] text-muted">
                  <span className="rounded-md bg-panel px-2 py-0.5 font-mono text-[12px] font-medium text-ink">
                    {whereLabel(f.where)}
                  </span>
                  {f.detail && f.detail !== f.text && f.flag !== "unclear_cell" && <span>{friendlyDetail(f.detail)}</span>}
                </span>
              </button>
              {f.suggestion && canEdit(f.where) &&
                (done ? (
                  <span className="flex shrink-0 items-center gap-1.5 text-[15px] font-medium text-ok">
                    <Check className="size-5" aria-hidden />
                    Changed to {done}
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => onUse(f)}
                    className="shrink-0 rounded-lg bg-night px-3.5 py-2 font-mono text-[14px] font-medium text-white hover:bg-night-2"
                  >
                    Use {f.suggestion}
                  </button>
                ))}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface CellState {
  flagsByKey: Map<string, Flag[]>;
  unclear: Set<string>;
  focusKey: string | null;
  pulse: { key: string; n: number } | null;
}

function cellClass(key: string, s: CellState) {
  const flagged = s.flagsByKey.has(key);
  const hot = s.focusKey === key;
  return [
    "w-full rounded-md px-2 py-2 font-mono text-[14px] text-ink outline-none transition-shadow",
    "focus:ring-2 focus:ring-brand-500",
    flagged ? "bg-signal-bg ring-2 ring-signal" : "bg-transparent hover:bg-panel",
    hot ? "ring-[3px] ring-signal-text" : "",
    s.unclear.has(key) ? "border-b-2 border-dotted border-signal-text rounded-b-none" : "",
  ].join(" ");
}

function pulseClass(key: string, s: CellState) {
  return s.pulse?.key === key ? (s.pulse.n % 2 ? "flag-pulse-a" : "flag-pulse-b") : "";
}

function HeaderFields({
  draft,
  masters,
  onChange,
  ...s
}: CellState & { draft: CardEdit; masters: Masters | null; onChange: (k: string, v: string) => void }) {
  const machineType = masters?.machines?.find((m) => m.mc_no === draft.header.mc_no)?.machine_type;
  return (
    <div className="mt-8">
      <h2 className="eyebrow">Card header</h2>
      <div className="mt-3 grid grid-cols-[1fr_1.6fr_0.8fr_1.4fr_1.1fr] gap-4">
        {HEADER_FIELDS.map((f) => {
          const key = headerKey(f);
          return (
            <label key={f} className="block">
              <span className="mb-1 block text-[13px] font-medium text-muted">{HEADER_LABELS[f]}</span>
              <input
                id={`cell-${key}`}
                value={draft.header[f] ?? ""}
                onChange={(e) => onChange(key, e.target.value)}
                className={`${cellClass(key, s)} border border-line ${pulseClass(key, s)}`}
              />
              {f === "mc_no" && machineType && <span className="mt-1 block text-[13px] text-subtle">{machineType}</span>}
            </label>
          );
        })}
      </div>
    </div>
  );
}

function codeHint(f: RowField, v: string, m: Masters | null): string | null {
  if (!m || !v) return null;
  const c = v.trim();
  if (f === "opn_code") {
    if (m.idle_codes?.[c]) return m.idle_codes[c];
    if (m.production_codes?.[c]) return m.production_codes[c];
    return null;
  }
  if (f === "rej_code") return m.rejection_codes?.[c] ?? null;
  if (f === "rework_code") return m.rework_codes?.[c] ?? null;
  return null;
}

function RowGrid({
  draft,
  masters,
  onChange,
  onAddRow,
  ...s
}: CellState & { draft: CardEdit; masters: Masters | null; onChange: (k: string, v: string) => void; onAddRow: () => void }) {
  return (
    <div className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="eyebrow">Rows · as read from the card</h2>
        <button
          type="button"
          onClick={onAddRow}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[15px] font-medium text-muted hover:bg-panel hover:text-ink"
        >
          <Plus className="size-5" aria-hidden />
          Add row
        </button>
      </div>
      <div className="mt-3 overflow-x-auto rounded-xl border border-line">
        <table className="w-full table-fixed border-collapse">
          <colgroup>
            <col style={{ width: 40 }} />
            {ROW_FIELDS.map((f) => (
              <col key={f} style={{ width: COL_W[f] }} />
            ))}
          </colgroup>
          <thead>
            <tr className="bg-night text-left align-bottom text-[12px] leading-tight font-medium text-night-text">
              <th className="px-2 py-3 text-center">#</th>
              {ROW_FIELDS.map((f) => (
                <th key={f} className="border-l border-night-line px-2 py-3">
                  {ROW_LABELS[f]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {draft.rows.length === 0 && (
              <tr>
                <td colSpan={15} className="px-4 py-6 text-center text-base text-muted">
                  No rows were read. Use &ldquo;Add row&rdquo; to type them in.
                </td>
              </tr>
            )}
            {draft.rows.map((r, i) => (
              <tr key={i} className="border-t border-line align-top">
                <td className="px-2 py-3.5 text-center text-[13px] font-medium text-subtle">{i + 1}</td>
                {ROW_FIELDS.map((f) => {
                  const key = rowKey(i, f);
                  const hint = codeHint(f, r[f], masters);
                  return (
                    <td key={f} className="border-l border-line p-1">
                      <input
                        id={`cell-${key}`}
                        value={r[f] ?? ""}
                        onChange={(e) => onChange(key, e.target.value)}
                        aria-label={`Row ${i + 1} ${ROW_LABELS[f]}`}
                        title={s.flagsByKey.get(key)?.map((x) => x.text).join("\n") || hint || undefined}
                        className={`${cellClass(key, s)} ${pulseClass(key, s)}`}
                      />
                      {f === "opn_code" && hint && (
                        <span className="mt-0.5 block truncate px-2 text-[12px] leading-snug text-subtle" title={hint}>
                          {hint}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="border-t border-line-strong bg-panel font-mono">
              <td colSpan={14} className="px-4 py-3 text-right text-[15px] font-semibold text-ink">
                Total
              </td>
              <td className="border-l border-line p-1">
                <input
                  id={`cell-${TOTAL_KEY}`}
                  value={draft.total_hours ?? ""}
                  onChange={(e) => onChange(TOTAL_KEY, e.target.value)}
                  aria-label="Total hours"
                  className={`${cellClass(TOTAL_KEY, s)} font-bold ${pulseClass(TOTAL_KEY, s)}`}
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[14px] text-muted">
        Times are as written on the card (12-hour, &ldquo;3.30&rdquo; = 3 h 30 m). Cells with a dotted underline were hard to read.
      </p>
    </div>
  );
}
