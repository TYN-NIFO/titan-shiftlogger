import { Camera, Database, ScanLine, ShieldCheck, UserCheck } from "lucide-react";
import type { CardsSummary } from "@/lib/api";

/**
 * The flow every photo card goes through, drawn as a line with stations (night panel).
 * Counts are live from /api/cards/summary.
 */
export default function Pipeline({ s }: { s: CardsSummary | null }) {
  const photo = s?.photo_total ?? 0;
  const auto = s?.photo_auto_approved ?? 0;
  const waiting = s?.needs_review ?? 0;
  const reading = s?.processing ?? 0;
  const pct = photo ? Math.round((100 * auto) / photo) : 0;

  return (
    <section className="rise mt-6 overflow-hidden rounded-3xl bg-night px-8 pt-6 pb-7 text-night-text">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[12px] tracking-[0.08em] text-night-muted uppercase">How a job card flows</p>
        <p className="font-mono text-[12px] text-night-muted">
          {s ? `${s.total.toLocaleString("en-IN")} cards in the database` : "…"}
        </p>
      </div>

      <div className="relative mt-7 grid grid-cols-5">
        {/* the line */}
        <span className="absolute top-[22px] right-[10%] left-[10%] h-px bg-night-line" aria-hidden />
        <span className="absolute top-[22px] left-[10%] h-px w-[60%] bg-brand-500/60" aria-hidden />

        <Station icon={<Camera className="size-5" />} title="Scanned" value={s ? String(photo) : "–"} note="photo cards in" />
        <Station icon={<ScanLine className="size-5" />} title="Read by AI" value={s ? String(photo - reading) : "–"} note={reading ? `${reading} reading now` : "every field, as written"} />
        <Station icon={<ShieldCheck className="size-5" />} title="Checked" value="8 rules" note="codes · hours · qty · masters" />
        <Station icon={<Database className="size-5" />} title="Saved automatically" value={s ? String(auto) : "–"} note={s ? `${pct}% passed every check` : ""} tone="ok" />
        <Station icon={<UserCheck className="size-5" />} title="Waiting for supervisor" value={s ? String(waiting) : "–"} note="only cards with a doubt" tone="signal" />
      </div>
    </section>
  );
}

function Station({
  icon,
  title,
  value,
  note,
  tone,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  note: string;
  tone?: "ok" | "signal";
}) {
  const ring =
    tone === "signal"
      ? "border-signal text-signal shadow-[0_0_0_6px_rgba(240,100,60,0.15)]"
      : tone === "ok"
        ? "border-brand-500 text-brand-400"
        : "border-night-line text-night-text";
  return (
    <div className="relative flex flex-col items-center text-center">
      <span className={`relative z-10 grid size-11 place-items-center rounded-full border-2 bg-night ${ring}`} aria-hidden>
        {icon}
      </span>
      <p className="mt-3 text-[14px] text-night-muted">{title}</p>
      <p className={`mt-1 text-[30px] leading-none font-semibold tracking-tight tabular-nums ${tone === "signal" ? "text-[#ff8a63]" : "text-white"}`}>{value}</p>
      <p className="mt-1.5 font-mono text-[12px] text-night-muted">{note}</p>
    </div>
  );
}
