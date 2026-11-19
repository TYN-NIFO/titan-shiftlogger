import { Loader2 } from "lucide-react";
import type { CardStatus } from "@/lib/types";

const STYLES: Record<CardStatus, { label: string; cls: string; dot: string }> = {
  approved: { label: "Saved", cls: "bg-ok-bg text-ok", dot: "bg-ok" },
  needs_review: { label: "Needs review", cls: "bg-warn-bg text-warn-text", dot: "bg-warn" },
  processing: { label: "Reading…", cls: "bg-brand-50 text-deep-900", dot: "" },
  failed: { label: "Failed", cls: "bg-bad-bg text-bad", dot: "bg-bad" },
};

/** Soft status pill with a coloured dot (spinner while the AI is reading). */
export default function StatusPill({ status, large = false }: { status: CardStatus; large?: boolean }) {
  const s = STYLES[status] ?? STYLES.failed;
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full font-medium whitespace-nowrap ${s.cls} ${
        large ? "px-3.5 py-1.5 text-[15px]" : "px-2.5 py-1 text-sm"
      }`}
    >
      {status === "processing" ? (
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
      ) : (
        <span className={`size-1.5 rounded-full ${s.dot}`} aria-hidden />
      )}
      {s.label}
    </span>
  );
}
