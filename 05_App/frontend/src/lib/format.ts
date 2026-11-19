import type { Cell, HeaderField, RowField } from "./types";

/** Grid column headers, as printed on the job card. */
export const ROW_LABELS: Record<RowField, string> = {
  emp_no: "Emp No",
  shift: "Shift",
  opn_code: "Opn/Idle Code",
  wo_no: "W.O. No",
  comp_code: "Comp Code",
  qty_prod: "Qty Prod",
  qty_accp: "Qty Accp",
  rej_code: "Rej Code",
  rej_qty: "Rej Qty",
  rework_code: "Rework Code",
  rework_qty: "Rework Qty",
  time_from: "From",
  time_to: "To",
  total_hours: "Total Hrs",
};

export const HEADER_LABELS: Record<HeaderField, string> = {
  date: "Date",
  component_description: "Component Description",
  cc: "CC",
  operation_description: "Operation Description",
  mc_no: "M/C No",
};

/** Human label for a `where` path, e.g. "rows[0].opn_code" -> "Row 1 · Opn/Idle Code". */
export function whereLabel(where: string | null | undefined): string {
  if (!where) return "Whole card";
  if (where === "total_hours") return "Total";
  if (where.startsWith("header.")) return HEADER_LABELS[where.slice(7) as HeaderField] ?? where.slice(7);
  const m = /^rows\[(\d+)\]\.(\w+)$/.exec(where);
  if (m) return `Row ${Number(m[1]) + 1} · ${ROW_LABELS[m[2] as RowField] ?? m[2]}`;
  return where;
}

const COLUMN_LABELS: Record<string, string> = {
  mc_no: "M/C No",
  emp_no: "Emp No",
  comp_code: "Comp Code",
  machine_type: "Machine type",
  efficiency_pct: "Output vs standard (%)",
  qty_accp: "Qty accepted",
  qty_prod: "Qty produced",
  std_qty: "Standard qty",
  card_date: "Date",
  emp_name: "Operator",
  machine_name: "Machine",
  component_name: "Component",
};

/** Human label for a SQL result column. */
export function columnLabel(col: string): string {
  if (COLUMN_LABELS[col]) return COLUMN_LABELS[col];
  const s = col.replace(/_pct$/, " (%)").replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const nf = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

/** Format a result cell for display. Codes and IDs stay as text. */
export function formatCell(v: Cell): string {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") return nf.format(v);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

export function toNumber(v: Cell): number | null {
  if (typeof v === "number") return v;
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return Number(v);
  return null;
}

export function timeAgo(isoDate: string): string {
  const t = new Date(isoDate).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
