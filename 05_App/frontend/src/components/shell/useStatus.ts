"use client";

import { useCallback, useEffect, useState } from "react";
import { getHealth, listCards } from "@/lib/api";
import type { Health } from "@/lib/types";

/** Shared polling for the AI/backend status and the review count (used by the rail and the context bar). */
export function useStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);
  const [reviewCount, setReviewCount] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setHealth(await getHealth());
      setOffline(false);
    } catch {
      setOffline(true);
    }
    try {
      setReviewCount((await listCards({ status: "needs_review", limit: 200 })).length);
    } catch {
      /* shown as offline */
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 12_000);
    const onChange = () => refresh();
    window.addEventListener("titan:cards-changed", onChange);
    return () => {
      clearInterval(t);
      window.removeEventListener("titan:cards-changed", onChange);
    };
  }, [refresh]);

  const state: "checking" | "offline" | "stub" | "ai-offline" | "live" = offline
    ? "offline"
    : !health
      ? "checking"
      : health.llm_mode !== "live"
        ? "stub"
        : !health.ok
          ? "ai-offline"
          : "live";

  return { state, reviewCount, health };
}
