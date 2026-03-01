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

export { ApiError, API_URL };
