"use client";

import { useEffect, useState } from "react";

/** Whole seconds since `active` became true; resets when it turns false. */
export function useElapsed(active: boolean): number {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    if (!active) {
      setSecs(0);
      return;
    }
    const start = Date.now();
    setSecs(0);
    const t = setInterval(() => setSecs(Math.floor((Date.now() - start) / 1000)), 250);
    return () => clearInterval(t);
  }, [active]);
  return secs;
}
