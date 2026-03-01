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

// === Chat Extended (chat-builder) ===

export interface ChatSessionFull {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface PendingTaskSetInfo {
  id: string;
  status: "pending" | "synced" | "rejected";
  tasks_json: string;
}

export interface ChatMessageFull {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata: string | null;
  created_at: string;
  pending_task_set?: PendingTaskSetInfo;
}

export interface SSEChunkEvent {
  type: "chunk";
  content: string;
}

export interface SSETasksEvent {
  type: "tasks";
  pending_id: string;
  tasks: ParsedTask[];
}

export interface SSEActionResultEvent {
  type: "action_result";
  action: string;
  result: string;
}

export type SSEEvent = SSEChunkEvent | SSETasksEvent | SSEActionResultEvent;

// === Wizard Types (wizard-builder) ===

export interface InboxEmail {
  id: string;
  subject: string;
  from_name: string;
  from_email: string;
  preview: string;
  received_at: string;
  has_attachments: boolean;
}

export interface TeamsChat {
  id: string;
  topic: string;
  chat_type: string;
  last_updated: string;
}

export interface WizardTextSource {
  text: string;
  context?: string;
}

export interface WizardEmailSource {
  message_id: string;
}

export interface WizardTeamsChatSource {
  chat_id: string;
}

export interface WizardExtractRequest {
  texts: WizardTextSource[];
  emails: WizardEmailSource[];
  teams_chats: WizardTeamsChatSource[];
  transcripts: [];
  ticket_prefix: string;
}

export interface WizardTask {
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

export interface WizardExtractResponse {
  tasks: WizardTask[];
  task_count: number;
  sources: { label: string; task_count: number }[];
  errors: { source: string; error: string }[];
}

export interface WizardDocumentResponse {
  source: string;
  tasks: WizardTask[];
  task_count: number;
}

export interface WizardCreateProjectRequest {
  group_id: string;
  plan_title: string;
  tasks_json: string;
  auto_create_buckets: boolean;
}

export interface WizardCreateProjectResponse {
  plan_id: string;
  plan_title: string;
  sync: Record<string, unknown>;
  task_count: number;
}

// === Reports API (reports-builder) ===

export interface BucketProgress {
  name: string;
  total: number;
  completed: number;
  in_progress: number;
  not_started: number;
}

export interface EpicProgress {
  name: string;
  total: number;
  completed: number;
  percentage: number;
}

export interface PlanReport {
  plan_name: string;
  generated_at: string;
  total_tasks: number;
  completed_tasks: number;
  overall_percentage: number;
  buckets: BucketProgress[];
  epics: EpicProgress[];
}
