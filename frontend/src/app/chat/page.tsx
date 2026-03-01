"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import {
  getGroups,
  getPlans,
  getBuckets,
  createChatSession,
  getChatSessionList,
  getChatMessages,
  sendChatMessage,
  approvePendingTasks,
  rejectPendingTasks,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type {
  Group,
  PlanInfo,
  BucketInfo,
  ChatSessionFull,
  ChatMessageFull,
  ParsedTask,
  SSEEvent,
} from "@/types";

// ── Inline markdown renderer ────────────────────────────────────────

function renderMarkdown(text: string): string {
  let html = text
    // code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
      return `<pre class="bg-zinc-900 text-zinc-100 rounded-md p-3 my-2 text-xs overflow-x-auto"><code>${escapeHtml(code.trim())}</code></pre>`;
    })
    // inline code
    .replace(/`([^`]+)`/g, '<code class="bg-zinc-200 dark:bg-zinc-700 px-1 py-0.5 rounded text-xs">$1</code>')
    // bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // unordered lists
    .replace(/^[\s]*[-*]\s+(.+)$/gm, "<li>$1</li>")
    // line breaks
    .replace(/\n/g, "<br />");

  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li>.*?<\/li>(?:<br \/>)?)+)/g, '<ul class="list-disc pl-5 my-1">$1</ul>');
  // Remove <br> inside <ul>
  html = html.replace(/<ul[^>]*>([\s\S]*?)<\/ul>/g, (_m, inner) => {
    return `<ul class="list-disc pl-5 my-1">${inner.replace(/<br \/>/g, "")}</ul>`;
  });

  return html;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ── Pending tasks card ──────────────────────────────────────────────

interface PendingTaskCardProps {
  pendingId: string;
  tasks: ParsedTask[];
  status: "pending" | "synced" | "rejected";
  sessionId: string;
  planId: string;
  buckets: BucketInfo[];
  onResolved: () => void;
}

function PendingTaskCard({
  pendingId,
  tasks,
  status,
  sessionId,
  planId,
  buckets,
  onResolved,
}: PendingTaskCardProps) {
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const defaultBucket = buckets[0]?.id ?? "";

  async function handleApprove() {
    if (!planId || !defaultBucket) return;
    setResolving(true);
    setError(null);
    try {
      await approvePendingTasks(sessionId, pendingId, planId, defaultBucket);
      onResolved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setResolving(false);
    }
  }

  async function handleReject() {
    setResolving(true);
    setError(null);
    try {
      await rejectPendingTasks(sessionId, pendingId);
      onResolved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rejection failed");
    } finally {
      setResolving(false);
    }
  }

  const resolved = status === "synced" || status === "rejected";

  return (
    <Card className="my-2 border-[#0078d4]/30">
      <CardContent className="py-3 px-4">
        <p className="text-xs font-semibold text-zinc-500 mb-2 uppercase tracking-wide">
          Extracted Tasks ({tasks.length})
        </p>
        <ul className="space-y-1">
          {tasks.map((t, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span className="mt-0.5 h-4 w-4 rounded border border-zinc-300 flex-shrink-0 flex items-center justify-center text-[10px]">
                {resolved && status === "synced" ? "\u2713" : ""}
              </span>
              <span className="text-zinc-800 dark:text-zinc-200">{t.title}</span>
              {t.bucket_name && (
                <Badge className="ml-auto text-[10px]">{t.bucket_name}</Badge>
              )}
            </li>
          ))}
        </ul>
        {error && (
          <p className="text-xs text-red-600 mt-2">{error}</p>
        )}
        {resolved ? (
          <p className="text-xs mt-3 text-zinc-400">
            {status === "synced" ? "Tasks synced to Planner." : "Tasks rejected."}
          </p>
        ) : (
          <div className="flex gap-2 mt-3">
            <Button
              variant="primary"
              className="text-xs px-3 py-1"
              onClick={handleApprove}
              disabled={resolving || !planId}
            >
              {resolving ? <Spinner className="h-3 w-3" /> : "Approve & Sync"}
            </Button>
            <Button
              variant="ghost"
              className="text-xs px-3 py-1"
              onClick={handleReject}
              disabled={resolving}
            >
              Reject
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Main chat page ──────────────────────────────────────────────────

interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  pendingTaskSet?: {
    id: string;
    status: "pending" | "synced" | "rejected";
    tasks: ParsedTask[];
  };
  actionResult?: { action: string; result: string };
}

export default function ChatPage() {
  const { user } = useAuth();

  // Plan selector state
  const [groups, setGroups] = useState<Group[]>([]);
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [buckets, setBuckets] = useState<BucketInfo[]>([]);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedPlan, setSelectedPlan] = useState("");
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [loadingPlans, setLoadingPlans] = useState(false);

  // Chat state
  const [sessions, setSessions] = useState<ChatSessionFull[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load groups on mount
  useEffect(() => {
    if (!user) return;
    setLoadingGroups(true);
    getGroups()
      .then(setGroups)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingGroups(false));
  }, [user]);

  // Load plans when group changes
  useEffect(() => {
    if (!selectedGroup) {
      setPlans([]);
      setSelectedPlan("");
      return;
    }
    setLoadingPlans(true);
    setError(null);
    getPlans(selectedGroup)
      .then(setPlans)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingPlans(false));
  }, [selectedGroup]);

  // Load buckets when plan changes
  useEffect(() => {
    if (!selectedPlan) {
      setBuckets([]);
      return;
    }
    getBuckets(selectedPlan)
      .then(setBuckets)
      .catch(() => {});
  }, [selectedPlan]);

  // Load chat sessions
  useEffect(() => {
    if (!user) return;
    setLoadingSessions(true);
    getChatSessionList()
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoadingSessions(false));
  }, [user]);

  // Load messages when session changes
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    setLoadingMessages(true);
    getChatMessages(activeSessionId)
      .then((msgs) => {
        setMessages(
          msgs.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            pendingTaskSet: m.pending_task_set
              ? {
                  id: m.pending_task_set.id,
                  status: m.pending_task_set.status,
                  tasks: JSON.parse(m.pending_task_set.tasks_json),
                }
              : undefined,
          })),
        );
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingMessages(false));
  }, [activeSessionId]);

  // Create new session
  async function handleNewChat() {
    setError(null);
    try {
      const session = await createChatSession();
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create session");
    }
  }

  // Send message
  async function handleSend() {
    const content = inputValue.trim();
    if (!content || streaming) return;

    let sessionId = activeSessionId;

    // Auto-create session if none selected
    if (!sessionId) {
      try {
        const session = await createChatSession();
        setSessions((prev) => [session, ...prev]);
        setActiveSessionId(session.id);
        sessionId = session.id;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create session");
        return;
      }
    }

    setInputValue("");
    setError(null);

    // Add user message locally
    const userMsg: LocalMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content,
    };
    const assistantMsg: LocalMessage = {
      id: `local-assistant-${Date.now()}`,
      role: "assistant",
      content: "",
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);

    const assistantId = assistantMsg.id;

    await sendChatMessage(
      sessionId,
      content,
      selectedPlan,
      (event: SSEEvent) => {
        if (event.type === "chunk") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + event.content }
                : m,
            ),
          );
        } else if (event.type === "tasks") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    pendingTaskSet: {
                      id: event.pending_id,
                      status: "pending" as const,
                      tasks: event.tasks,
                    },
                  }
                : m,
            ),
          );
        } else if (event.type === "action_result") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    actionResult: { action: event.action, result: event.result },
                  }
                : m,
            ),
          );
        }
      },
      () => {
        setStreaming(false);
        // Refresh session list to update title
        getChatSessionList().then(setSessions).catch(() => {});
      },
      (err) => {
        setStreaming(false);
        setError(err.message);
      },
    );

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  // Handle task resolution (approve/reject)
  function handleTaskResolved() {
    if (activeSessionId) {
      getChatMessages(activeSessionId)
        .then((msgs) => {
          setMessages(
            msgs.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              pendingTaskSet: m.pending_task_set
                ? {
                    id: m.pending_task_set.id,
                    status: m.pending_task_set.status,
                    tasks: JSON.parse(m.pending_task_set.tasks_json),
                  }
                : undefined,
            })),
          );
        })
        .catch(() => {});
    }
  }

  // Keyboard handler
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // Auto-resize textarea
  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInputValue(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to use the chat.</p>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-0 -mt-2">
      {/* ── Left Sidebar ─────────────────────────────────── */}
      <div className="w-72 flex-shrink-0 border-r border-zinc-200 dark:border-zinc-800 flex flex-col bg-zinc-50 dark:bg-zinc-950 rounded-l-lg">
        {/* Plan selector */}
        <div className="p-3 border-b border-zinc-200 dark:border-zinc-800 space-y-2">
          <div>
            <label className="block text-xs font-medium text-zinc-500 mb-1">
              Group
            </label>
            {loadingGroups ? (
              <Spinner />
            ) : (
              <select
                className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900"
                value={selectedGroup}
                onChange={(e) => {
                  setSelectedGroup(e.target.value);
                  setSelectedPlan("");
                }}
              >
                <option value="">Select group...</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.displayName}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-500 mb-1">
              Plan
            </label>
            {loadingPlans ? (
              <Spinner />
            ) : (
              <select
                className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900"
                value={selectedPlan}
                onChange={(e) => setSelectedPlan(e.target.value)}
                disabled={!selectedGroup}
              >
                <option value="">Select plan...</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* New Chat button */}
        <div className="p-3 border-b border-zinc-200 dark:border-zinc-800">
          <Button
            variant="primary"
            className="w-full text-xs"
            onClick={handleNewChat}
          >
            + New Chat
          </Button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto">
          {loadingSessions ? (
            <div className="flex justify-center py-6">
              <Spinner />
            </div>
          ) : sessions.length === 0 ? (
            <p className="text-xs text-zinc-400 p-3 text-center">
              No chat sessions yet.
            </p>
          ) : (
            sessions.map((s) => (
              <button
                key={s.id}
                className={`w-full text-left px-3 py-2.5 border-b border-zinc-100 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors ${
                  activeSessionId === s.id
                    ? "bg-[#0078d4]/10 border-l-2 border-l-[#0078d4]"
                    : ""
                }`}
                onClick={() => setActiveSessionId(s.id)}
              >
                <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
                  {s.title || "New Chat"}
                </p>
                <p className="text-[10px] text-zinc-400 mt-0.5">
                  {new Date(s.created_at).toLocaleDateString()}
                </p>
              </button>
            ))
          )}
        </div>
      </div>

      {/* ── Main Chat Area ───────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 bg-white dark:bg-zinc-950 rounded-r-lg">
        {/* Error bar */}
        {error && (
          <div className="px-4 py-2 bg-red-50 border-b border-red-200 text-xs text-red-700 flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-600 ml-2"
            >
              x
            </button>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {!activeSessionId && messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-zinc-400 gap-3">
              <div className="h-14 w-14 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center">
                <svg
                  className="h-7 w-7 text-zinc-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25z"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium">Chat with Elephandroid</p>
              <p className="text-xs max-w-sm text-center">
                Select a plan and start chatting. Manage Planner tasks, ask questions, and get AI-powered insights via natural language.
              </p>
            </div>
          ) : loadingMessages ? (
            <div className="flex justify-center py-12">
              <Spinner className="h-8 w-8" />
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <div key={msg.id}>
                  <div
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm ${
                        msg.role === "user"
                          ? "bg-[#0078d4] text-white rounded-br-sm"
                          : "bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 rounded-bl-sm"
                      }`}
                    >
                      {msg.role === "user" ? (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      ) : msg.content ? (
                        <div
                          className="prose prose-sm dark:prose-invert max-w-none [&_pre]:my-2 [&_code]:text-xs"
                          dangerouslySetInnerHTML={{
                            __html: renderMarkdown(msg.content),
                          }}
                        />
                      ) : streaming &&
                        msg.id ===
                          messages[messages.length - 1]?.id ? (
                        <span className="inline-flex gap-1">
                          <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce" />
                          <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce [animation-delay:0.15s]" />
                          <span className="h-2 w-2 rounded-full bg-zinc-400 animate-bounce [animation-delay:0.3s]" />
                        </span>
                      ) : null}
                    </div>
                  </div>

                  {/* Action result inline */}
                  {msg.actionResult && (
                    <div className="flex justify-start mt-1">
                      <div className="max-w-[75%] rounded-lg border border-green-200 bg-green-50 dark:bg-green-900/20 dark:border-green-800 px-3 py-2 text-xs text-green-800 dark:text-green-300">
                        <p className="font-semibold text-[10px] uppercase tracking-wide text-green-600 dark:text-green-400 mb-1">
                          {msg.actionResult.action.replace(/_/g, " ")}
                        </p>
                        <div
                          dangerouslySetInnerHTML={{
                            __html: renderMarkdown(msg.actionResult.result),
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Pending task set */}
                  {msg.pendingTaskSet && activeSessionId && (
                    <div className="flex justify-start mt-1 ml-0">
                      <div className="max-w-[75%]">
                        <PendingTaskCard
                          pendingId={msg.pendingTaskSet.id}
                          tasks={msg.pendingTaskSet.tasks}
                          status={msg.pendingTaskSet.status}
                          sessionId={activeSessionId}
                          planId={selectedPlan}
                          buckets={buckets}
                          onResolved={handleTaskResolved}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-zinc-200 dark:border-zinc-800 p-4">
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              className="flex-1 resize-none rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0078d4] focus:border-transparent placeholder:text-zinc-400"
              placeholder={
                selectedPlan
                  ? "Type a message... (Enter to send, Shift+Enter for newline)"
                  : "Select a plan to start managing tasks, or just chat..."
              }
              rows={1}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={streaming}
            />
            <Button
              variant="primary"
              onClick={handleSend}
              disabled={!inputValue.trim() || streaming}
              className="flex-shrink-0"
            >
              {streaming ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                  />
                </svg>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
