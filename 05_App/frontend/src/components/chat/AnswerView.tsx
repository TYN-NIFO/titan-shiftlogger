"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell as BarCell, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Code2, ShieldCheck, Table2 } from "lucide-react";
import type { ChatAnswer, Cell } from "@/lib/types";
import { columnLabel, formatCell, toNumber } from "@/lib/format";

const TOP = "#2ec0bb";
const REST = "#2b5a64";
const TICK = { fontSize: 13, fill: "#7fa0a6", fontFamily: "var(--font-code)" };

type Tab = "view" | "table" | "query";

/** One answer: header with trust checks, the text, a callout of the top result, and Chart / Table / Query tabs. */
export default function AnswerView({ answer }: { answer: ChatAnswer }) {
  const hasData = answer.columns.length > 0 && answer.rows.length > 0;
  const hasView = hasData && !!answer.view?.type;
  const [tab, setTab] = useState<Tab>(hasView ? "view" : "table");
  const checks = answer.checks;

  return (
    <article className="rise overflow-hidden rounded-3xl border border-line bg-surface">
      <header className="flex items-center gap-3 border-b border-line px-6 py-3">
        <span className="eyebrow">Answer · from approved job cards</span>
        <span className="ml-auto flex items-center gap-2">
          {checks?.sql_valid && <Badge>Read-only query</Badge>}
          {checks?.numbers_match && <Badge>Numbers match the data</Badge>}
          {answer.ms ? <span className="font-mono text-[12px] text-subtle">{(answer.ms / 1000).toFixed(1)} s</span> : null}
        </span>
      </header>

      <div className="px-6 pt-5 pb-6">
        <p className="text-[19px] leading-relaxed text-ink">{answer.text}</p>

        {hasData && (
          <>
            <Callout answer={answer} />
            <div className="mt-5 flex items-center gap-1 border-b border-line">
              {hasView && <TabBtn on={tab === "view"} onClick={() => setTab("view")} icon={<BarChart3 className="size-4" aria-hidden />} label={answer.view?.type === "table" ? "Ranking" : "Chart"} />}
              <TabBtn on={tab === "table"} onClick={() => setTab("table")} icon={<Table2 className="size-4" aria-hidden />} label={`Data · ${answer.rows.length} rows`} />
              {answer.sql && <TabBtn on={tab === "query"} onClick={() => setTab("query")} icon={<Code2 className="size-4" aria-hidden />} label="Query" />}
            </div>
            <div className="mt-4">
              {tab === "view" && hasView && <View answer={answer} />}
              {tab === "table" && <RankedTable columns={answer.columns} rows={answer.rows} highlight={valueIndex(answer)} />}
              {tab === "query" && (
                <pre className="overflow-x-auto rounded-2xl bg-night p-5 font-mono text-[14px] leading-relaxed text-night-text">{answer.sql}</pre>
              )}
            </div>
          </>
        )}
      </div>
    </article>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5 rounded-full bg-ok-bg px-2.5 py-1 text-[12px] font-medium text-ok">
      <ShieldCheck className="size-3.5" aria-hidden />
      {children}
    </span>
  );
}

function TabBtn({ on, onClick, icon, label }: { on: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={`-mb-px flex items-center gap-2 border-b-2 px-3 py-2.5 text-[14px] font-medium transition-colors ${
        on ? "border-brand-500 text-ink" : "border-transparent text-muted hover:text-ink"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function labelIndex(answer: ChatAnswer): number {
  const { columns, view } = answer;
  return Math.max(0, view?.x ? columns.indexOf(view.x) : 0);
}

/** A "*_name" column next to the id (operator / machine / component name), if the query returned one. */
function nameIndex(answer: ChatAnswer): number {
  return answer.columns.findIndex((c) => c.endsWith("_name"));
}

function valueIndex(answer: ChatAnswer): number {
  const { columns, rows, view } = answer;
  const xi = labelIndex(answer);
  let yi = view?.y ? columns.indexOf(view.y) : -1;
  if (yi < 0) yi = columns.findIndex((c, i) => i !== xi && !/(_no|_code|_name)$/.test(c) && rows.some((r) => toNumber(r[i]) !== null));
  return yi;
}

/** The first row, called out: e.g. "604021.05 · 163.5 breakdown hours". Straight from the data, no AI. */
function Callout({ answer }: { answer: ChatAnswer }) {
  const yi = valueIndex(answer);
  const xi = labelIndex(answer);
  const ni = nameIndex(answer);
  if (yi < 0 || answer.rows.length < 2) return null;
  const first = answer.rows[0];
  const second = answer.rows[1];
  const a = toNumber(first[yi]);
  const b = toNumber(second[yi]);
  const ratio = a !== null && b ? a / b : null;
  return (
    <div className="mt-5 grid grid-cols-[auto_1fr] items-center gap-6 rounded-2xl border border-line bg-panel px-5 py-4">
      <div>
        <p className="eyebrow">Top result</p>
        <p className="mt-1 text-[24px] leading-tight font-semibold tracking-tight text-ink">
          {ni >= 0 ? formatCell(first[ni]) : <span className="font-mono">{formatCell(first[xi])}</span>}
        </p>
        {ni >= 0 && <p className="mt-0.5 font-mono text-[14px] text-muted">{formatCell(first[xi])}</p>}
      </div>
      <div className="flex items-center gap-8 border-l border-line pl-6">
        <div>
          <p className="text-[28px] leading-none font-semibold tracking-tight text-ink tabular-nums">{formatCell(first[yi])}</p>
          <p className="mt-1 text-[13px] text-muted">{columnLabel(answer.columns[yi])}</p>
        </div>
        <div>
          <p className={`text-[18px] leading-none text-muted ${ni >= 0 ? "" : "font-mono"}`}>
            {ni >= 0 ? formatCell(second[ni]) : formatCell(second[xi])} · <span className="font-mono">{formatCell(second[yi])}</span>
          </p>
          <p className="mt-1.5 text-[13px] text-muted">
            Next
            {ratio && ratio > 1.05 ? ` · top is ${ratio.toFixed(1)}× higher` : ratio && ratio < 0.95 ? ` · top is ${(1 / ratio).toFixed(1)}× lower` : ""}
          </p>
        </div>
      </div>
    </div>
  );
}

function View({ answer }: { answer: ChatAnswer }) {
  const view = answer.view!;
  const { columns, rows } = answer;
  const xi = labelIndex(answer);
  const yi = valueIndex(answer);

  if ((view.type === "bar" || view.type === "line") && yi >= 0) {
    const ni = nameIndex(answer);
    const data = rows.map((r) => ({ x: formatCell(r[xi]), name: ni >= 0 ? formatCell(r[ni]) : "", y: toNumber(r[yi]) ?? 0 }));
    const yLabel = columnLabel(columns[yi]);
    return (
      <figure className="rounded-2xl bg-night px-6 pt-5 pb-4">
        <figcaption className="flex items-center justify-between">
          <span className="text-[15px] font-medium text-white">{view.title || yLabel}</span>
          <span className="font-mono text-[12px] text-night-muted">{yLabel}</span>
        </figcaption>
        <div className="mt-3 h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            {view.type === "bar" ? (
              <BarChart data={data} margin={{ top: 26, right: 8, bottom: 0, left: -8 }}>
                <CartesianGrid vertical={false} stroke="#17404c" />
                <XAxis dataKey="x" tick={<NameTick names={data} />} tickLine={false} axisLine={{ stroke: "#22505c" }} height={ni >= 0 ? 48 : 30} interval={0} />
                <YAxis tick={TICK} tickLine={false} axisLine={false} width={48} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  labelFormatter={(x, p) => {
                    const nm = (p?.[0]?.payload as { name?: string } | undefined)?.name;
                    return nm ? `${x} · ${nm}` : String(x);
                  }}
                  formatter={(v) => [formatCell(v as number), yLabel]}
                  contentStyle={{ background: "#10303a", border: "1px solid #22505c", borderRadius: 10, color: "#cfe3e5", fontSize: 13 }}
                />
                <Bar dataKey="y" radius={[6, 6, 0, 0]} maxBarSize={64}>
                  {data.map((_, i) => (
                    <BarCell key={i} fill={i === 0 ? TOP : REST} />
                  ))}
                  <LabelList
                    dataKey="y"
                    position="top"
                    formatter={(v: unknown) => formatCell(v as number)}
                    style={{ fontSize: 14, fontWeight: 500, fill: "#ffffff", fontFamily: "var(--font-code)" }}
                  />
                </Bar>
              </BarChart>
            ) : (
              <LineChart data={data} margin={{ top: 20, right: 16, bottom: 0, left: -8 }}>
                <CartesianGrid vertical={false} stroke="#17404c" />
                <XAxis dataKey="x" tick={TICK} tickLine={false} axisLine={{ stroke: "#22505c" }} />
                <YAxis tick={TICK} tickLine={false} axisLine={false} width={48} />
                <Tooltip
                  formatter={(v) => [formatCell(v as number), yLabel]}
                  contentStyle={{ background: "#10303a", border: "1px solid #22505c", borderRadius: 10, color: "#cfe3e5", fontSize: 13 }}
                />
                <Line type="monotone" dataKey="y" stroke={TOP} strokeWidth={2.5} dot={{ r: 3, fill: TOP }} activeDot={{ r: 5 }} />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </figure>
    );
  }

  if (view.type === "kpi") {
    const k = yi >= 0 ? yi : 0;
    return (
      <div className="inline-flex flex-col rounded-2xl bg-night px-8 py-6">
        <span className="text-5xl font-semibold tracking-tight text-white">{formatCell(rows[0][k])}</span>
        <span className="mt-2 text-base text-night-muted">{view.title || columnLabel(columns[k])}</span>
      </div>
    );
  }

  return <RankedTable columns={columns} rows={rows} highlight={yi} />;
}

/** X-axis tick: the id in mono, and the name underneath when there is one. */
function NameTick(props: { x?: number; y?: number; payload?: { value: string; index: number }; names: { name: string }[] }) {
  const { x = 0, y = 0, payload, names } = props;
  const name = payload ? names[payload.index]?.name : "";
  return (
    <g transform={`translate(${x},${y})`}>
      <text dy={14} textAnchor="middle" fill="#cfe3e5" fontSize={13} fontFamily="var(--font-code)">
        {payload?.value}
      </text>
      {name && (
        <text dy={32} textAnchor="middle" fill="#7fa0a6" fontSize={12}>
          {name}
        </text>
      )}
    </g>
  );
}

function RankedTable({ columns, rows, highlight }: { columns: string[]; rows: Cell[][]; highlight: number }) {
  const max = Math.max(...rows.map((r) => Math.abs(toNumber(r[highlight]) ?? 0)), 1);
  return (
    <div className="max-h-[420px] overflow-auto rounded-2xl border border-line">
      <table className="w-full text-left">
        <thead className="sticky top-0 bg-panel">
          <tr className="font-mono text-[12px] tracking-[0.06em] text-muted uppercase">
            <th className="w-14 px-4 py-3 text-center">#</th>
            {columns.map((c, i) => (
              <th key={c} className={`px-4 py-3 font-medium ${isNumericCol(rows, i) ? "text-right" : ""}`}>
                {columnLabel(c)}
              </th>
            ))}
            {highlight >= 0 && <th className="w-48 px-4 py-3" aria-label="Bar" />}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => {
            const v = toNumber(r[highlight]);
            return (
              <tr key={ri} className="border-t border-line">
                <td className="px-4 py-2.5 text-center">
                  <span
                    className={`inline-grid size-7 place-items-center rounded-lg font-mono text-[13px] font-medium ${
                      ri < 3 ? "bg-night text-brand-400" : "text-subtle"
                    }`}
                  >
                    {String(ri + 1).padStart(2, "0")}
                  </span>
                </td>
                {r.map((cell, ci) => (
                  <td
                    key={ci}
                    className={`px-4 py-2.5 text-[15px] ${columns[ci].endsWith("_name") ? "font-sans" : "font-mono"} ${isNumericCol(rows, ci) ? "text-right" : ""} ${
                      ci === highlight ? "font-semibold text-ink" : "text-ink/80"
                    }`}
                  >
                    {formatCell(cell)}
                  </td>
                ))}
                {highlight >= 0 && (
                  <td className="px-4 py-2.5">
                    <span className="block h-1.5 overflow-hidden rounded-full bg-panel">
                      <span
                        className={`block h-full rounded-full ${ri < 3 ? "bg-brand-500" : "bg-brand-200"}`}
                        style={{ width: `${(100 * Math.abs(v ?? 0)) / max}%` }}
                      />
                    </span>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function isNumericCol(rows: Cell[][], i: number) {
  return rows.length > 0 && rows.every((r) => typeof r[i] === "number" || r[i] === null);
}
