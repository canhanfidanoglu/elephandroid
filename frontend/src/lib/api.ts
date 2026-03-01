const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ────────────────────────────────────────────────────────────

import type {
  User,
  Group,
  PlanInfo,
  BucketInfo,
  TaskInfo,
  AIHealth,
  ChatSession,
  ChatMessage,
  Meeting,
} from "@/types";

export function getLoginUrl(): string {
  return `${API_URL}/auth/login`;
}

export function getLogoutUrl(): string {
  return `${API_URL}/auth/logout`;
}

export async function getMe(): Promise<User> {
  return request<User>("/auth/me");
}

// ── Planner ─────────────────────────────────────────────────────────

export async function getGroups(): Promise<Group[]> {
  return request<Group[]>("/planner/groups");
}

export async function getPlans(groupId: string): Promise<PlanInfo[]> {
  return request<PlanInfo[]>(`/planner/plans?group_id=${encodeURIComponent(groupId)}`);
}

export async function getBuckets(planId: string): Promise<BucketInfo[]> {
  return request<BucketInfo[]>(`/planner/buckets?plan_id=${encodeURIComponent(planId)}`);
}

export async function getTasks(planId: string): Promise<TaskInfo[]> {
  return request<TaskInfo[]>(`/sync/tasks?plan_id=${encodeURIComponent(planId)}`);
}

// ── AI ──────────────────────────────────────────────────────────────

export async function getAIHealth(): Promise<AIHealth> {
  return request<AIHealth>("/ai/health");
}

// ── Chat ────────────────────────────────────────────────────────────

export async function getChatSessions(): Promise<ChatSession[]> {
  return request<ChatSession[]>("/chat/sessions");
}

export async function getChatHistory(sessionId: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/chat/sessions/${sessionId}/history`);
}

// ── Meetings ────────────────────────────────────────────────────────

export async function getMeetings(): Promise<Meeting[]> {
  return request<Meeting[]>("/meetings/list");
}

// ── Reports ─────────────────────────────────────────────────────────

export function getReportDownloadUrl(planId: string, format: string): string {
  return `${API_URL}/reports/generate?plan_id=${encodeURIComponent(planId)}&format=${format}`;
}

// ── SSE helper ──────────────────────────────────────────────────────

export function createSSEStream(path: string): EventSource {
  return new EventSource(`${API_URL}${path}`, { withCredentials: true });
}

// === Chat API (chat-builder) ===

import type {
  ChatSessionFull,
  ChatMessageFull,
  SSEEvent,
} from "@/types";

export async function createChatSession(title?: string): Promise<ChatSessionFull> {
  return request<ChatSessionFull>("/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ title: title ?? null }),
  });
}

export async function getChatSessionList(): Promise<ChatSessionFull[]> {
  return request<ChatSessionFull[]>("/chat/sessions");
}

export async function getChatMessages(sessionId: string): Promise<ChatMessageFull[]> {
  return request<ChatMessageFull[]>(`/chat/sessions/${sessionId}/messages`);
}

export async function sendChatMessage(
  sessionId: string,
  content: string,
  planId: string,
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  const url = `${API_URL}/chat/sessions/${sessionId}/messages`;
  try {
    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, plan_id: planId }),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(body || res.statusText);
    }

    const reader = res.body?.getReader();
    if (!reader) {
      throw new Error("No response body");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;
        const data = trimmed.slice(6);
        if (data === "[DONE]") {
          onDone();
          return;
        }
        try {
          const event: SSEEvent = JSON.parse(data);
          onEvent(event);
        } catch {
          // skip malformed events
        }
      }
    }

    onDone();
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

export async function approvePendingTasks(
  sessionId: string,
  pendingId: string,
  planId: string,
  defaultBucketId: string,
): Promise<{ status: string; sync_result: Record<string, unknown> }> {
  return request(`/chat/sessions/${sessionId}/tasks/${pendingId}/approve`, {
    method: "POST",
    body: JSON.stringify({
      plan_id: planId,
      default_bucket_id: defaultBucketId,
      auto_create_buckets: true,
    }),
  });
}

export async function rejectPendingTasks(
  sessionId: string,
  pendingId: string,
): Promise<{ status: string }> {
  return request(`/chat/sessions/${sessionId}/tasks/${pendingId}/reject`, {
    method: "POST",
  });
}

// === Wizard API (wizard-builder) ===

import type {
  InboxEmail,
  TeamsChat,
  WizardExtractRequest,
  WizardExtractResponse,
  WizardDocumentResponse,
  WizardCreateProjectRequest,
  WizardCreateProjectResponse,
} from "@/types";

export async function getInbox(top = 20): Promise<InboxEmail[]> {
  return request<InboxEmail[]>(`/emails/inbox?top=${top}`);
}

export async function getTeamsChats(top = 20): Promise<TeamsChat[]> {
  return request<TeamsChat[]>(`/teams-chat/chats?top=${top}`);
}

export async function wizardExtract(
  body: WizardExtractRequest,
): Promise<WizardExtractResponse> {
  return request<WizardExtractResponse>("/wizard/extract", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function wizardExtractDocument(
  file: File,
  ticketPrefix = "PRJ",
): Promise<WizardDocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("ticket_prefix", ticketPrefix);

  const url = `${API_URL}/wizard/extract-document`;
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json();
}

export async function wizardCreateProject(
  body: WizardCreateProjectRequest,
): Promise<WizardCreateProjectResponse> {
  return request<WizardCreateProjectResponse>("/wizard/create-project", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// === Reports API (reports-builder) ===

import type { PlanReport } from "@/types";

export async function getPlanProgress(planId: string): Promise<PlanReport> {
  return request<PlanReport>(
    `/reports/plan-progress?plan_id=${encodeURIComponent(planId)}`,
  );
}

export function getReportPptxUrl(planId: string): string {
  return `${API_URL}/reports/plan-progress/pptx?plan_id=${encodeURIComponent(planId)}`;
}

export function getReportDocxUrl(planId: string): string {
  return `${API_URL}/reports/plan-progress/docx?plan_id=${encodeURIComponent(planId)}`;
}

export async function streamNLReport(
  planId: string,
  query: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  const url = `${API_URL}/reports/natural-language`;
  try {
    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: planId, query }),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(body || res.statusText);
    }

    const reader = res.body?.getReader();
    if (!reader) {
      throw new Error("No response body");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;
        const data = trimmed.slice(6);
        if (data === "[DONE]") {
          onDone();
          return;
        }
        try {
          const parsed = JSON.parse(data);
          if (parsed.type === "chunk" && parsed.content) {
            onChunk(parsed.content);
          }
        } catch {
          // skip malformed events
        }
      }
    }

    onDone();
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

export { ApiError, API_URL };
