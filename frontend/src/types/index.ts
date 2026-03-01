// ── Auth ────────────────────────────────────────────────────────────

export interface User {
  user_id: string;
}

// ── Planner ─────────────────────────────────────────────────────────

export interface PlanInfo {
  id: string;
  title: string;
  group_id: string;
}

export interface BucketInfo {
  id: string;
  name: string;
  plan_id: string;
  order_hint: string;
}

export interface TaskInfo {
  id: string;
  title: string;
  bucket_id: string;
  percent_complete: number;
  priority: number;
  start_date: string | null;
  due_date: string | null;
  applied_categories: Record<string, boolean>;
}

export interface Group {
  id: string;
  displayName: string;
}

// ── Excel ───────────────────────────────────────────────────────────

export interface ParsedTask {
  ticket_id: string;
  title: string;
  epic: string | null;
  description: string | null;
  bucket_name: string | null;
  priority: number | null;
  start_date: string | null;
  due_date: string | null;
  assignee: string | null;
  checklist_items: string[];
}

// ── Chat ────────────────────────────────────────────────────────────

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ── Meetings ────────────────────────────────────────────────────────

export interface Meeting {
  id: string;
  subject: string;
  start: string;
  end: string;
  organizer: string;
}

// ── Reports ─────────────────────────────────────────────────────────

export interface ReportOptions {
  plan_id: string;
  format: "pptx" | "docx";
}

// ── AI Health ───────────────────────────────────────────────────────

export interface AIHealth {
  available: boolean;
  llm_provider: string;
  model: string;
}

// ── Priority helpers ────────────────────────────────────────────────

export const PRIORITY_LABELS: Record<number, string> = {
  1: "Urgent",
  3: "High",
  5: "Medium",
  9: "Low",
};

export const PRIORITY_COLORS: Record<number, string> = {
  1: "text-red-700 bg-red-50",
  3: "text-orange-700 bg-orange-50",
  5: "text-blue-700 bg-blue-50",
  9: "text-gray-700 bg-gray-50",
};
