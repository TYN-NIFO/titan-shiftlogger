"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardCheck, Layers, MessageSquareText } from "lucide-react";

const ITEMS = [
  { href: "/chat", label: "Ask", icon: MessageSquareText },
  { href: "/cards", label: "Cards", icon: Layers },
  { href: "/review", label: "Review", icon: ClipboardCheck },
] as const;

/** Narrow dark navigation rail: icon + short label, review count as a coral badge. */
export default function Rail({ reviewCount }: { reviewCount: number | null }) {
  const path = usePathname() || "/";
  return (
    <nav aria-label="Main" className="flex w-[84px] shrink-0 flex-col items-center bg-night py-4">
      <Link href="/chat" aria-label="Shift Logger home" className="mb-6 grid size-11 place-items-center rounded-xl bg-brand-500 text-night">
        <Logo />
      </Link>
      <ul className="flex w-full flex-col gap-1 px-2">
        {ITEMS.map(({ href, label, icon: Icon }) => {
          const active = path.startsWith(href);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`relative flex flex-col items-center gap-1 rounded-xl py-2.5 text-[12px] font-medium transition-colors ${
                  active ? "bg-night-3 text-white" : "text-night-muted hover:bg-night-2 hover:text-night-text"
                }`}
              >
                {active && <span className="absolute top-3 bottom-3 -left-2 w-[3px] rounded-r-full bg-brand-500" aria-hidden />}
                <Icon className={`size-[22px] ${active ? "text-brand-400" : ""}`} strokeWidth={1.75} aria-hidden />
                {label}
                {href === "/review" && reviewCount ? (
                  <span className="absolute top-1.5 right-3 grid min-w-5 place-items-center rounded-full bg-signal px-1 font-mono text-[11px] font-semibold text-white">
                    {reviewCount}
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}
      </ul>
      <span className="mt-auto font-mono text-[10px] tracking-[0.18em] text-night-muted [writing-mode:vertical-rl] rotate-180">
        PROOF OF CONCEPT
      </span>
    </nav>
  );
}

/** Simple mark: a job card with a tick, drawn as strokes. */
function Logo() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <rect x="4.5" y="3.5" width="15" height="17" rx="2.5" />
      <path d="M8 8.5h8M8 12h4" strokeLinecap="round" />
      <path d="m11.5 16 1.8 1.8 3.4-3.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
