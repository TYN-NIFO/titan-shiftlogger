"use client";

import ContextBar from "./ContextBar";
import Rail from "./Rail";
import { useStatus } from "./useStatus";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { state, reviewCount } = useStatus();
  return (
    <div className="flex h-full">
      <Rail reviewCount={reviewCount} />
      <div className="flex min-w-0 flex-1 flex-col">
        <ContextBar state={state} />
        <main className="min-h-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
