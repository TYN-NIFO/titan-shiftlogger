"use client";

import { CheckCircle2, AlertCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";

type Kind = "success" | "error";
interface ToastMsg {
  id: number;
  text: string;
  kind: Kind;
}

const Ctx = createContext<(text: string, kind?: Kind) => void>(() => {});

export function useToast() {
  return useContext(Ctx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMsg[]>([]);
  const show = useCallback((text: string, kind: Kind = "success") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);
  return (
    <Ctx.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-8 z-50 flex flex-col items-center gap-3" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-center gap-3 rounded-xl px-6 py-4 text-lg font-medium shadow-lg ${
              t.kind === "success" ? "bg-deep-900 text-white" : "bg-red-700 text-white"
            }`}
          >
            {t.kind === "success" ? (
              <CheckCircle2 className="size-6 text-emerald-300" aria-hidden />
            ) : (
              <AlertCircle className="size-6" aria-hidden />
            )}
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
