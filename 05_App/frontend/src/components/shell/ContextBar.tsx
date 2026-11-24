"use client";

import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { MOCK } from "@/lib/api";

const TITLES: [string, string][] = [
  ["/chat", "Ask the data"],
  ["/cards/", "Job card"],
  ["/cards", "Job cards"],
  ["/review", "Review queue"],
];

const STATE: Record<string, { dot: string; label: string; live?: boolean }> = {
  live: { dot: "bg-brand-500", label: "AI live · on-premises", live: true },
  "ai-offline": { dot: "bg-signal", label: "AI service offline" },
  stub: { dot: "bg-bad", label: "Test mode · canned answers" },
  offline: { dot: "bg-bad", label: "Backend offline" },
  checking: { dot: "bg-subtle", label: "Checking…" },
};

/** Top bar: where you are on the shop floor (breadcrumb) and the system status. */
export default function ContextBar({ state }: { state: string }) {
  const path = usePathname() || "/";
  const title = TITLES.find(([p]) => path.startsWith(p))?.[1] ?? "Shift Logger";
  const s = STATE[state] ?? STATE.checking;
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface/90 px-8 backdrop-blur">
      {/* eslint-disable-next-line @next/next/no-img-element -- static SVG brand mark */}
      <img src="/titan-logo.svg" alt="Titan Company" className="h-12 w-12" />
      <span className="h-6 w-px bg-line-strong" aria-hidden />
      <span className="text-[15px] font-semibold tracking-tight text-ink">Shift Logger</span>
      <Crumb />
      <span className="font-mono text-[13px] text-muted">Watch Division</span>
      <Crumb />
      <span className="font-mono text-[13px] text-muted">Case Centre 1300 · Press Shop</span>
      <Crumb />
      <span className="text-[14px] font-medium text-ink">{title}</span>

      <div className="ml-auto flex items-center gap-3">
        {MOCK && <span className="rounded-md bg-fuchsia-100 px-2 py-1 font-mono text-[11px] font-semibold text-fuchsia-700">MOCK DATA</span>}
        <span className="font-mono text-[13px] text-muted">Shifts A · B</span>
        <span className="h-4 w-px bg-line-strong" aria-hidden />
        <span className="flex items-center gap-2 rounded-full border border-line px-3 py-1 text-[13px] text-ink" aria-live="polite">
          <span className={`size-2 rounded-full ${s.dot} ${s.live ? "live-dot" : ""}`} aria-hidden />
          {s.label}
        </span>
      </div>
    </header>
  );
}

function Crumb() {
  return <ChevronRight className="size-3.5 text-subtle" aria-hidden />;
}
