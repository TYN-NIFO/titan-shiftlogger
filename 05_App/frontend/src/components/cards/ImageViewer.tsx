"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImageOff, Maximize2, ZoomIn, ZoomOut } from "lucide-react";

const MIN = 1;
const MAX = 6;

/** Card photo, fitted to the panel; wheel or buttons to zoom, drag to pan, double-click to zoom in. */
export default function ImageViewer({ src, alt }: { src: string | null; alt: string }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ s: 1, x: 0, y: 0 });
  const drag = useRef<{ px: number; py: number; x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [broken, setBroken] = useState(false);

  /** Zoom to scale `ns`, keeping the point `p` (relative to the panel centre) still. */
  const zoomAt = useCallback((ns: number, p = { x: 0, y: 0 }) => {
    setView((v) => {
      const s = Math.min(MAX, Math.max(MIN, ns));
      if (s === MIN) return { s: 1, x: 0, y: 0 };
      const k = s / v.s;
      return { s, x: p.x - (p.x - v.x) * k, y: p.y - (p.y - v.y) * k };
    });
  }, []);

  const centreOffset = (clientX: number, clientY: number) => {
    const r = boxRef.current!.getBoundingClientRect();
    return { x: clientX - (r.left + r.width / 2), y: clientY - (r.top + r.height / 2) };
  };

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const p = centreOffset(e.clientX, e.clientY);
      setView((v) => {
        const s = Math.min(MAX, Math.max(MIN, v.s * Math.exp(-e.deltaY * 0.0015)));
        if (s === MIN) return { s: 1, x: 0, y: 0 };
        const k = s / v.s;
        return { s, x: p.x - (p.x - v.x) * k, y: p.y - (p.y - v.y) * k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    setBroken(false);
    setView({ s: 1, x: 0, y: 0 });
  }, [src]);

  if (!src || broken) {
    return (
      <div className="grid h-full place-items-center bg-slate-100 text-grey-brand">
        <div className="flex flex-col items-center gap-3 text-lg">
          <ImageOff className="size-10" aria-hidden />
          {src ? "The photo couldn't be loaded." : "No photo for this card (synthetic data)."}
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full overflow-hidden grid-paper">
      <div
        ref={boxRef}
        className={`flex h-full w-full touch-none items-center justify-center p-4 select-none ${
          view.s > 1 ? (dragging ? "cursor-grabbing" : "cursor-grab") : "cursor-zoom-in"
        }`}
        onPointerDown={(e) => {
          if (view.s <= 1) return;
          (e.target as Element).setPointerCapture?.(e.pointerId);
          drag.current = { px: e.clientX, py: e.clientY, x: view.x, y: view.y };
          setDragging(true);
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d) return;
          setView((v) => ({ ...v, x: d.x + e.clientX - d.px, y: d.y + e.clientY - d.py }));
        }}
        onPointerUp={() => {
          drag.current = null;
          setDragging(false);
        }}
        onDoubleClick={(e) => zoomAt(view.s > 1 ? 1 : 2.5, centreOffset(e.clientX, e.clientY))}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- served by the backend, size unknown */}
        <img
          src={src}
          alt={alt}
          draggable={false}
          onError={() => setBroken(true)}
          className="max-h-full max-w-full rounded-lg object-contain shadow-[0_20px_60px_rgba(0,0,0,0.45)]"
          style={{
            transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})`,
            transition: dragging ? "none" : "transform 120ms ease-out",
          }}
        />
      </div>

      <div className="absolute right-4 bottom-4 flex items-center gap-1 rounded-xl bg-night-2/95 p-1 text-night-text shadow-md ring-1 ring-night-line">
        <ToolButton label="Zoom out" onClick={() => zoomAt(view.s / 1.5)} disabled={view.s <= MIN}>
          <ZoomOut className="size-5" aria-hidden />
        </ToolButton>
        <span className="w-14 text-center font-mono text-sm text-night-text tabular-nums">{Math.round(view.s * 100)}%</span>
        <ToolButton label="Zoom in" onClick={() => zoomAt(view.s * 1.5)} disabled={view.s >= MAX}>
          <ZoomIn className="size-5" aria-hidden />
        </ToolButton>
        <ToolButton label="Fit to panel" onClick={() => setView({ s: 1, x: 0, y: 0 })} disabled={view.s === 1}>
          <Maximize2 className="size-5" aria-hidden />
        </ToolButton>
      </div>
    </div>
  );
}

function ToolButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="grid size-10 place-items-center rounded-lg text-night-text hover:bg-night-3 disabled:text-night-muted disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}
