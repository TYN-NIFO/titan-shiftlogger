/**
 * DEV-ONLY fixtures, used when NEXT_PUBLIC_MOCK=1 (the top bar then shows "MOCK DATA").
 * Synthetic data only. Never used for the demo video.
 */
import type { Card, CardEdit, CardRow, CardSummary, ChatAnswer, Flag, Health, Masters } from "./types";
import { ROW_FIELDS } from "./types";

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

const IDLE: Record<string, string> = {
  "10801": "Preventive Maintenance",
  "10803": "Electrical Machine breakdown",
  "10804": "Mechanical Machine breakdown",
  "10806": "No Load",
  "10808": "No Utilities (Power, Compressed Air, Water, Chilled water & Air duct)",
  "10810": "No Tool",
  "10811": "Tool Reconditioning",
  "10813": "Absenteeism",
  "10815": "Training",
  "10836": "Machine Cleaning",
};

function row(r: Partial<CardRow>): CardRow {
  const out = { unclear: [] } as unknown as CardRow;
  for (const f of ROW_FIELDS) out[f] = "";
  return { ...out, ...r, unclear: r.unclear ?? [] };
}

function header(h: Partial<Card["header"]>): Card["header"] {
  return { date: "", component_description: "", cc: "", operation_description: "", mc_no: "", ...h };
}

type Template = Omit<Card, "id" | "card_ref" | "source" | "status" | "image_url">;

const TEMPLATES: Record<string, Template> = {
  C04: {
    read_seconds: 14.8,
    error: null,
    header: header({ date: "11/11/26", mc_no: "604020.08" }),
    rows: [
      row({ emp_no: "280419", shift: "A", opn_code: "10613", time_from: "6.00", time_to: "2.30", total_hours: "8.00", unclear: ["opn_code"] }),
    ],
    total_hours: "8.00",
    flags: [
      { flag: "invalid_code", text: "Opn/Idle code is not on the code sheet", where: "rows[0].opn_code", detail: "Code '10613' not on code sheet", suggestion: "10813" },
      { flag: "unclear_cell", text: "The reader marked this cell as unclear", where: "rows[0].opn_code", detail: "Reader marked rows[0].opn_code as unclear", suggestion: null },
    ],
  },
  C08: {
    read_seconds: 15.6,
    error: null,
    header: header({ date: "13/11/2026", cc: "1163", operation_description: "F, W, T", mc_no: "604020.08" }),
    rows: [
      row({ emp_no: "280671", shift: "B", opn_code: "10202", comp_code: "1163", qty_prod: "600", qty_accp: "650", time_from: "2.30", time_to: "6.00", total_hours: "3.30" }),
      row({ emp_no: "280671", shift: "B", opn_code: "10202", comp_code: "1163", qty_prod: "700", qty_accp: "700", time_from: "6.00", time_to: "11.00", total_hours: "4.00" }),
    ],
    total_hours: "7.30",
    flags: [
      { flag: "accp_gt_prod", text: "Qty accepted is more than qty produced", where: "rows[0].qty_accp", detail: "Accepted 650 > produced 600", suggestion: null },
      { flag: "qty_balance", text: "Qty produced does not equal accepted + rejected + rework", where: "rows[0].qty_prod", detail: "600 produced, 650 accounted for", suggestion: null },
      { flag: "row_hours_mismatch", text: "Row Total Hours does not match its From-To time", where: "rows[1].total_hours", detail: "6.00 to 11.00 is 5.00 h, written 4.00", suggestion: "5.00" },
      { flag: "shift_hours_not_8", text: "Shift hours do not add up to 8.00", where: "total_hours", detail: "Rows add up to 7.30", suggestion: null },
    ],
  },
  C02: {
    read_seconds: 13.9,
    error: null,
    header: header({ date: "10/11/26", cc: "1163", operation_description: "F, W, T", mc_no: "604020.11" }),
    rows: [
      row({ emp_no: "280133", shift: "A", opn_code: "10202", comp_code: "1163", qty_prod: "500", qty_accp: "500", time_from: "6.00", time_to: "8.00", total_hours: "2.00" }),
      row({ emp_no: "280133", shift: "A", opn_code: "10804", time_from: "8.00", time_to: "10.30", total_hours: "2.30" }),
      row({ emp_no: "280133", shift: "A", opn_code: "10202", comp_code: "1163", qty_prod: "800", qty_accp: "800", time_from: "10.30", time_to: "2.30", total_hours: "3.30" }),
    ],
    total_hours: "8.00",
    flags: [],
  },
};

interface MockCard extends Card {
  created_at: string;
  ready_at?: number;
  template?: string;
}

const now = Date.now();
const iso = (minsAgo: number) => new Date(now - minsAgo * 60_000).toISOString();

function photoCard(id: number, ref: string, status: Card["status"], minsAgo: number, tpl?: string): MockCard {
  const t = TEMPLATES[tpl ?? ref] ?? TEMPLATES.C02;
  return {
    ...structuredClone(t),
    id,
    card_ref: ref,
    source: "photo",
    status,
    image_url: `/mock/${ref}_front.jpeg`,
    flags: status === "approved" ? [] : structuredClone(t.flags),
    created_at: iso(minsAgo),
  };
}

let nextId = 2000;
const store: MockCard[] = [
  photoCard(1012, "C04", "needs_review", 8),
  photoCard(1011, "C08", "needs_review", 12),
  photoCard(1010, "C03", "needs_review", 40, "C08"),
  photoCard(1009, "C01", "needs_review", 55, "C04"),
  photoCard(1008, "C02", "approved", 70),
  photoCard(1007, "C07", "approved", 80),
  photoCard(1006, "C10", "approved", 95),
  ...Array.from({ length: 8 }, (_, i): MockCard => {
    const c = photoCard(900 - i, `SYN-${900 - i}`, "approved", 60 * 24 * (i + 4));
    return { ...c, source: "synthetic", image_url: null, header: { ...c.header, date: `${14 - i}/11/26` } };
  }),
];

function settle(c: MockCard) {
  if (c.status === "processing" && c.ready_at && Date.now() >= c.ready_at) {
    const t = TEMPLATES[c.template ?? "C02"] ?? TEMPLATES.C02;
    Object.assign(c, structuredClone(t));
    c.status = c.flags.length ? "needs_review" : "approved";
  }
}

function summary(c: MockCard): CardSummary {
  return {
    id: c.id,
    card_ref: c.card_ref,
    source: c.source,
    card_date: c.header.date || null,
    mc_no: c.header.mc_no || null,
    emp_no: c.rows[0]?.emp_no || null,
    status: c.status,
    flag_count: c.flags.length,
    created_at: c.created_at,
  };
}

function find(id: number): MockCard {
  const c = store.find((x) => x.id === id);
  if (!c) throw new Error("We couldn't find that card.");
  settle(c);
  return c;
}

export async function getHealth(): Promise<Health> {
  return { ok: true, db: true, llm_mode: "live", ollama_reachable: true };
}

export async function getMasters(): Promise<Masters> {
  return {
    employees: ["279842", "279915", "280133", "280207", "280356", "280419", "280588", "280671"],
    machines: [
      { mc_no: "604020.08", machine_type: "Press" },
      { mc_no: "604020.11", machine_type: "Press" },
      { mc_no: "604021.03", machine_type: "CNC" },
      { mc_no: "604021.05", machine_type: "CNC" },
    ],
    components: [
      { comp_code: "6147", description: "Case Back" },
      { comp_code: "1163", description: "Case Middle" },
    ],
    idle_codes: IDLE,
    production_codes: { "10202": "Production" },
    rework_codes: { "001": "Black Stains", "002": "Burr" },
    rejection_codes: { "001": "DAMAGE", "004": "Tool chipped off", "008": "Crack" },
  };
}

export async function listCards(q: { status?: string; source?: string; limit?: number }): Promise<CardSummary[]> {
  await delay(200);
  store.forEach(settle);
  return store
    .filter((c) => (!q.status || c.status === q.status) && (!q.source || c.source === q.source))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, q.limit ?? 50)
    .map(summary);
}

export async function uploadCard(file: File): Promise<{ id: number; status: string }> {
  await delay(500);
  const ref = file.name.replace(/\.[^.]+$/, "").replace(/_front$/i, "");
  const tpl = TEMPLATES[ref.toUpperCase().slice(0, 3)] ? ref.toUpperCase().slice(0, 3) : "C02";
  const c: MockCard = {
    ...photoCard(nextId++, ref, "processing", 0, tpl),
    image_url: URL.createObjectURL(file),
    rows: [],
    flags: [],
    read_seconds: null,
    ready_at: Date.now() + 5000,
    template: tpl,
  };
  store.push(c);
  return { id: c.id, status: "processing" };
}

export async function getCard(id: number): Promise<Card> {
  await delay(150);
  return structuredClone(find(id));
}

function cellValue(e: CardEdit, where: string | null): string | undefined {
  if (!where) return undefined;
  if (where === "total_hours") return e.total_hours;
  if (where.startsWith("header.")) return e.header[where.slice(7) as keyof Card["header"]];
  const m = /^rows\[(\d+)\]\.(\w+)$/.exec(where);
  return m ? (e.rows[Number(m[1])]?.[m[2] as keyof CardRow] as string | undefined) : undefined;
}

export async function saveCard(id: number, edit: CardEdit): Promise<Card> {
  await delay(500);
  const c = find(id);
  // Mock re-check: a flag clears once its cell has been changed.
  const kept: Flag[] = c.flags.filter((f) => cellValue(edit, f.where) === cellValue(c, f.where));
  // Corrected cells lose their "unclear" mark; the card stays in review until approved.
  const rows = edit.rows.map((r, i) => ({ ...r, unclear: (r.unclear ?? []).filter((f) => c.rows[i]?.[f as keyof CardRow] === r[f as keyof CardRow]) }));
  Object.assign(c, structuredClone(edit), { rows, flags: kept });
  return structuredClone(c);
}

export async function approveCard(id: number): Promise<Card> {
  await delay(400);
  const c = find(id);
  c.status = "approved";
  return structuredClone(c);
}

const SQL_BREAKDOWN = `SELECT mc_no, ROUND(SUM(hours)::numeric, 1) AS breakdown_hours
FROM v_downtime
WHERE is_cnc AND category = 'breakdown'
  AND card_date BETWEEN DATE '2026-07-20' AND DATE '2026-11-18'
GROUP BY mc_no
ORDER BY breakdown_hours DESC
LIMIT 200`;

const SQL_ABSENT = `SELECT emp_no, COUNT(*) AS absent_shifts
FROM v_absenteeism
GROUP BY emp_no
ORDER BY absent_shifts DESC
LIMIT 10`;

const SQL_PROD = `SELECT emp_no, shift, ROUND(efficiency_pct::numeric, 1) AS efficiency_pct
FROM v_operator_productivity
ORDER BY efficiency_pct ASC
LIMIT 10`;

export async function ask(question: string): Promise<ChatAnswer> {
  await delay(2600);
  const q = question.toLowerCase();
  if (q.includes("cnc") || q.includes("breakdown") || q.includes("downtime")) {
    return {
      route: "data",
      text: "604021.05 lost the most time to breakdowns: 61.5 hours over the last four months, almost twice the next CNC machine, 604021.03 at 33.0 hours.",
      view: { type: "bar", x: "mc_no", y: "breakdown_hours", title: "Breakdown hours by CNC machine" },
      columns: ["mc_no", "breakdown_hours"],
      rows: [
        ["604021.05", 61.5],
        ["604021.03", 33.0],
        ["604021.01", 29.5],
        ["604021.07", 27.0],
        ["604021.09", 24.5],
      ],
      sql: SQL_BREAKDOWN,
      checks: { sql_valid: true, numbers_match: true },
      ms: 8200,
    };
  }
  if (q.includes("absent")) {
    return {
      route: "data",
      text: "Three operators stand out: 280419 missed 15 shifts, 280671 missed 14 and 280873 missed 13. Most operators missed 3 or fewer.",
      view: { type: "table", x: "emp_no", y: "absent_shifts", title: "Absent shifts by operator" },
      columns: ["emp_no", "absent_shifts"],
      rows: [
        ["280419", 15],
        ["280671", 14],
        ["280873", 13],
        ["280112", 6],
        ["279960", 5],
        ["280544", 5],
        ["280305", 4],
      ],
      sql: SQL_ABSENT,
      checks: { sql_valid: true, numbers_match: true },
      ms: 7400,
    };
  }
  if (q.includes("productive") || q.includes("productivity")) {
    return {
      route: "data",
      text: "The least productive operators are 280544 at 71.2% of standard output, 280302 at 73.8% and 280760 at 74.5%.",
      view: { type: "table", x: "emp_no", y: "efficiency_pct", title: "Output against standard, lowest first" },
      columns: ["emp_no", "shift", "efficiency_pct"],
      rows: [
        ["280544", "A", 71.2],
        ["280302", "B", 73.8],
        ["280760", "A", 74.5],
        ["280118", "B", 88.9],
        ["279977", "A", 91.3],
        ["280431", "B", 92.0],
      ],
      sql: SQL_PROD,
      checks: { sql_valid: true, numbers_match: true },
      ms: 9100,
    };
  }
  if (q.includes("trend") || q.includes("per week") || q.includes("weekly")) {
    return {
      route: "data",
      text: "Breakdown hours on CNC machines peaked in the week of 2026-09-14 at 14.5 hours.",
      view: { type: "line", x: "week", y: "breakdown_hours", title: "CNC breakdown hours by week" },
      columns: ["week", "breakdown_hours"],
      rows: [
        ["2026-08-24", 8.0],
        ["2026-08-31", 9.5],
        ["2026-09-07", 11.0],
        ["2026-09-14", 14.5],
        ["2026-09-21", 10.0],
        ["2026-09-28", 7.5],
      ],
      sql: "SELECT date_trunc('week', card_date)::date AS week, SUM(hours) AS breakdown_hours FROM v_downtime WHERE is_cnc AND category = 'breakdown' GROUP BY 1 ORDER BY 1 LIMIT 200",
      checks: { sql_valid: true, numbers_match: true },
      ms: 6100,
    };
  }
  if (q.includes("how many")) {
    return {
      route: "data",
      text: "There are 6,912 approved job cards in the database.",
      view: { type: "kpi", y: "cards", title: "Approved job cards" },
      columns: ["cards"],
      rows: [[6912]],
      sql: "SELECT COUNT(*) AS cards FROM v_production LIMIT 200",
      checks: { sql_valid: true, numbers_match: true },
      ms: 5200,
    };
  }
  return {
    route: "chat",
    text: "I can answer questions about the job-card data: downtime, absenteeism, output and productivity by machine, operator, shift or date.",
    view: { type: null, x: "", y: "", title: "" },
    columns: [],
    rows: [],
    sql: null,
    ms: 1800,
  };
}
