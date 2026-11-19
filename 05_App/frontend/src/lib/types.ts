/** Shapes from 05_App/CONTRACT.md ("API"). Field values on cards are strings, as written. */

export type CardStatus = "processing" | "needs_review" | "approved" | "failed";
export type CardSource = "photo" | "synthetic" | string;

export interface Health {
  ok: boolean;
  db: boolean | string;
  llm_mode: string;
  ollama_reachable: boolean;
  read_model?: string;
  chat_model?: string;
}

export interface Masters {
  employees: string[];
  machines: { mc_no: string; machine_type: string }[];
  components: { comp_code: string; description: string }[];
  idle_codes: Record<string, string>;
  production_codes: Record<string, string>;
  rework_codes: Record<string, string>;
  rejection_codes: Record<string, string>;
}

export interface CardSummary {
  id: number;
  card_ref: string;
  source: CardSource;
  card_date: string | null;
  mc_no: string | null;
  emp_no: string | null;
  status: CardStatus;
  flag_count: number;
  created_at: string;
}

export const HEADER_FIELDS = ["date", "component_description", "cc", "operation_description", "mc_no"] as const;
export type HeaderField = (typeof HEADER_FIELDS)[number];
export type CardHeader = Record<HeaderField, string>;

export const ROW_FIELDS = [
  "emp_no",
  "shift",
  "opn_code",
  "wo_no",
  "comp_code",
  "qty_prod",
  "qty_accp",
  "rej_code",
  "rej_qty",
  "rework_code",
  "rework_qty",
  "time_from",
  "time_to",
  "total_hours",
] as const;
export type RowField = (typeof ROW_FIELDS)[number];
export type CardRow = Record<RowField, string> & { unclear: string[] };

export interface Flag {
  flag: string;
  text: string;
  where: string | null;
  detail?: string | null;
  suggestion?: string | null;
}

export interface Card {
  id: number;
  card_ref: string;
  source: CardSource;
  status: CardStatus;
  image_url: string | null;
  read_seconds: number | null;
  error: string | null;
  header: CardHeader;
  rows: CardRow[];
  total_hours: string;
  flags: Flag[];
}

export interface CardEdit {
  header: CardHeader;
  rows: CardRow[];
  total_hours: string;
}

export type ViewType = "bar" | "line" | "table" | "kpi" | null;

export interface ChatView {
  type: ViewType;
  x?: string | null;
  y?: string | null;
  title?: string | null;
}

export type Cell = string | number | boolean | null;

export interface ChatAnswer {
  route: "data" | "chat" | string;
  text: string;
  view: ChatView | null;
  columns: string[];
  rows: Cell[][];
  sql: string | null;
  checks?: { sql_valid?: boolean; numbers_match?: boolean; fallback_text?: boolean } | null;
  ms?: number;
}

export interface ChatTurn {
  role: "user" | "assistant";
  text: string;
}
