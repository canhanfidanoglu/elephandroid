"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  getGroups,
  getInbox,
  getTeamsChats,
  wizardExtract,
  wizardExtractDocument,
  wizardCreateProject,
} from "@/lib/api";
import type {
  Group,
  InboxEmail,
  TeamsChat,
  WizardTask,
  WizardExtractResponse,
} from "@/types";
import { PRIORITY_LABELS, PRIORITY_COLORS } from "@/types";

// ---------------------------------------------------------------------------
// Step indicator
// ---------------------------------------------------------------------------

const STEPS = ["Select Sources", "Review Tasks", "Create Project"] as const;

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2">
      {STEPS.map((label, i) => {
        const step = i + 1;
        const active = step === current;
        const done = step < current;
        return (
          <div key={label} className="flex items-center gap-2">
            {i > 0 && (
              <div
                className={`h-px w-8 ${done ? "bg-[#0078d4]" : "bg-zinc-300 dark:bg-zinc-700"}`}
              />
            )}
            <div className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                  active
                    ? "bg-[#0078d4] text-white"
                    : done
                      ? "bg-[#0078d4]/20 text-[#0078d4]"
                      : "bg-zinc-200 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400"
                }`}
              >
                {done ? "\u2713" : step}
              </span>
              <span
                className={`hidden text-sm sm:inline ${
                  active
                    ? "font-medium text-zinc-900 dark:text-zinc-100"
                    : "text-zinc-500"
                }`}
              >
                {label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source tabs
// ---------------------------------------------------------------------------

type SourceTab = "email" | "teams" | "upload" | "text";

const SOURCE_TABS: { key: SourceTab; label: string }[] = [
  { key: "email", label: "Email" },
  { key: "teams", label: "Teams Chat" },
  { key: "upload", label: "Upload" },
  { key: "text", label: "Text" },
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function WizardPage() {
  const { user } = useAuth();

  // Step state
  const [step, setStep] = useState(1);

  // -- Step 1 state --
  const [activeTab, setActiveTab] = useState<SourceTab>("email");

  // Email
  const [emails, setEmails] = useState<InboxEmail[]>([]);
  const [loadingEmails, setLoadingEmails] = useState(false);
  const [selectedEmailIds, setSelectedEmailIds] = useState<Set<string>>(
    new Set(),
  );

  // Teams Chat
  const [chats, setChats] = useState<TeamsChat[]>([]);
  const [loadingChats, setLoadingChats] = useState(false);
  const [selectedChatIds, setSelectedChatIds] = useState<Set<string>>(
    new Set(),
  );

  // Upload
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Text
  const [pastedText, setPastedText] = useState("");

  // Extra context
  const [extraContext, setExtraContext] = useState("");

  // Extraction
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);

  // -- Step 2 state --
  const [tasks, setTasks] = useState<WizardTask[]>([]);
  const [checkedTasks, setCheckedTasks] = useState<Set<number>>(new Set());
  const [extractionSources, setExtractionSources] = useState<
    { label: string; task_count: number }[]
  >([]);

  // -- Step 3 state --
  const [groups, setGroups] = useState<Group[]>([]);
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [planName, setPlanName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createdPlanId, setCreatedPlanId] = useState<string | null>(null);
  const [createdTaskCount, setCreatedTaskCount] = useState(0);

  // -- Fetch emails on tab switch --
  const fetchEmails = useCallback(async () => {
    if (emails.length > 0) return;
    setLoadingEmails(true);
    try {
      const data = await getInbox(20);
      setEmails(data);
    } catch {
      // silently fail, user can retry
    } finally {
      setLoadingEmails(false);
    }
  }, [emails.length]);

  // -- Fetch chats on tab switch --
  const fetchChats = useCallback(async () => {
    if (chats.length > 0) return;
    setLoadingChats(true);
    try {
      const data = await getTeamsChats(20);
      setChats(data);
    } catch {
      // silently fail
    } finally {
      setLoadingChats(false);
    }
  }, [chats.length]);

  useEffect(() => {
    if (!user || step !== 1) return;
    if (activeTab === "email") fetchEmails();
    if (activeTab === "teams") fetchChats();
  }, [user, step, activeTab, fetchEmails, fetchChats]);

  // -- Toggle helpers --
  function toggleEmail(id: string) {
    setSelectedEmailIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleChat(id: string) {
    setSelectedChatIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleTask(idx: number) {
    setCheckedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  // -- File handling --
  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files) return;
    setUploadedFiles((prev) => [...prev, ...Array.from(files)]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removeFile(idx: number) {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  // -- Source count badge --
  const sourceCount =
    selectedEmailIds.size +
    selectedChatIds.size +
    uploadedFiles.length +
    (pastedText.trim() ? 1 : 0);

  // -- Extract tasks --
  async function handleExtract() {
    setExtracting(true);
    setExtractError(null);

    try {
      let allTasks: WizardTask[] = [];
      let allSources: { label: string; task_count: number }[] = [];

      // 1. Extract from text/email/chat via /wizard/extract
      const hasTextSources =
        pastedText.trim() ||
        selectedEmailIds.size > 0 ||
        selectedChatIds.size > 0;

      if (hasTextSources) {
        const body = {
          texts: pastedText.trim()
            ? [{ text: pastedText, context: extraContext || undefined }]
            : [],
          emails: Array.from(selectedEmailIds).map((id) => ({
            message_id: id,
          })),
          teams_chats: Array.from(selectedChatIds).map((id) => ({
            chat_id: id,
          })),
          transcripts: [] as [],
          ticket_prefix: "PRJ",
        };

        const result: WizardExtractResponse = await wizardExtract(body);
        allTasks = [...allTasks, ...result.tasks];
        allSources = [...allSources, ...result.sources];

        if (result.errors.length > 0) {
          setExtractError(
            `Some sources had errors: ${result.errors.map((e) => e.error).join("; ")}`,
          );
        }
      }

      // 2. Extract from uploaded documents
      for (const file of uploadedFiles) {
        try {
          const docResult = await wizardExtractDocument(file);
          allTasks = [...allTasks, ...docResult.tasks];
          allSources = [
            ...allSources,
            { label: docResult.source, task_count: docResult.task_count },
          ];
        } catch (err) {
          setExtractError(
            (prev) =>
              (prev ? prev + "; " : "") +
              `Failed to extract from ${file.name}: ${err instanceof Error ? err.message : "Unknown error"}`,
          );
        }
      }

      if (allTasks.length === 0) {
        setExtractError("No tasks were extracted from the selected sources.");
        setExtracting(false);
        return;
      }

      setTasks(allTasks);
      setCheckedTasks(new Set(allTasks.map((_, i) => i)));
      setExtractionSources(allSources);
      setStep(2);
    } catch (err) {
      setExtractError(
        err instanceof Error ? err.message : "Extraction failed.",
      );
    } finally {
      setExtracting(false);
    }
  }

  // -- Update task field --
  function updateTask(idx: number, field: keyof WizardTask, value: unknown) {
    setTasks((prev) =>
      prev.map((t, i) => (i === idx ? { ...t, [field]: value } : t)),
    );
  }

  // -- Step 3: Load groups --
  useEffect(() => {
    if (step !== 3 || groups.length > 0) return;
    setLoadingGroups(true);
    getGroups()
      .then(setGroups)
      .catch(() => {})
      .finally(() => setLoadingGroups(false));
  }, [step, groups.length]);

  // -- Create project --
  async function handleCreateProject() {
    if (!selectedGroup || !planName.trim()) return;
    setCreating(true);
    setCreateError(null);

    const selectedTasks = tasks.filter((_, i) => checkedTasks.has(i));

    try {
      const result = await wizardCreateProject({
        group_id: selectedGroup,
        plan_title: planName.trim(),
        tasks_json: JSON.stringify(selectedTasks),
        auto_create_buckets: true,
      });
      setCreatedPlanId(result.plan_id);
      setCreatedTaskCount(result.task_count);
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : "Failed to create project.",
      );
    } finally {
      setCreating(false);
    }
  }

  // -- Reset wizard --
  function handleReset() {
    setStep(1);
    setSelectedEmailIds(new Set());
    setSelectedChatIds(new Set());
    setUploadedFiles([]);
    setPastedText("");
    setExtraContext("");
    setTasks([]);
    setCheckedTasks(new Set());
    setExtractionSources([]);
    setSelectedGroup("");
    setPlanName("");
    setCreatedPlanId(null);
    setCreatedTaskCount(0);
    setExtractError(null);
    setCreateError(null);
  }

  // -- Auth guard --
  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to use the wizard.</p>
      </div>
    );
  }

  const selectedTaskCount = checkedTasks.size;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Project Wizard
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Extract tasks from multiple sources and create a Planner project in
            one step.
          </p>
        </div>
        <StepIndicator current={step} />
      </div>

      {/* ================================================================ */}
      {/* STEP 1 — Select Sources */}
      {/* ================================================================ */}
      {step === 1 && (
        <>
          {/* Source tabs */}
          <Card>
            <CardContent className="pt-6">
              {/* Tab bar */}
              <div className="flex border-b border-zinc-200 dark:border-zinc-700 mb-4">
                {SOURCE_TABS.map(({ key, label }) => {
                  const count =
                    key === "email"
                      ? selectedEmailIds.size
                      : key === "teams"
                        ? selectedChatIds.size
                        : key === "upload"
                          ? uploadedFiles.length
                          : pastedText.trim()
                            ? 1
                            : 0;
                  return (
                    <button
                      key={key}
                      onClick={() => setActiveTab(key)}
                      className={`relative px-4 py-2 text-sm font-medium transition-colors ${
                        activeTab === key
                          ? "text-[#0078d4] border-b-2 border-[#0078d4] -mb-px"
                          : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                      }`}
                    >
                      {label}
                      {count > 0 && (
                        <span className="ml-1.5 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[#0078d4] px-1.5 text-[10px] font-semibold text-white">
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Email tab */}
              {activeTab === "email" && (
                <div className="space-y-2">
                  {loadingEmails ? (
                    <div className="flex justify-center py-8">
                      <Spinner className="h-6 w-6" />
                    </div>
                  ) : emails.length === 0 ? (
                    <p className="py-8 text-center text-sm text-zinc-400">
                      No emails found. Make sure you have granted Mail.Read
                      permission.
                    </p>
                  ) : (
                    <div className="max-h-80 overflow-y-auto space-y-1">
                      {emails.map((email) => (
                        <label
                          key={email.id}
                          className={`flex items-start gap-3 rounded-md p-3 cursor-pointer transition-colors ${
                            selectedEmailIds.has(email.id)
                              ? "bg-blue-50 dark:bg-blue-900/20"
                              : "hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-zinc-300 text-[#0078d4] focus:ring-[#0078d4]"
                            checked={selectedEmailIds.has(email.id)}
                            onChange={() => toggleEmail(email.id)}
                          />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                              {email.subject}
                            </p>
                            <p className="text-xs text-zinc-500 truncate">
                              {email.from_name || email.from_email}
                              {email.has_attachments && " \u00B7 \uD83D\uDCCE"}
                            </p>
                            <p className="text-xs text-zinc-400 truncate mt-0.5">
                              {email.preview}
                            </p>
                          </div>
                          <span className="text-xs text-zinc-400 whitespace-nowrap flex-shrink-0">
                            {new Date(email.received_at).toLocaleDateString()}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Teams Chat tab */}
              {activeTab === "teams" && (
                <div className="space-y-2">
                  {loadingChats ? (
                    <div className="flex justify-center py-8">
                      <Spinner className="h-6 w-6" />
                    </div>
                  ) : chats.length === 0 ? (
                    <p className="py-8 text-center text-sm text-zinc-400">
                      No Teams chats found. Make sure you have granted Chat.Read
                      permission.
                    </p>
                  ) : (
                    <div className="max-h-80 overflow-y-auto space-y-1">
                      {chats.map((chat) => (
                        <label
                          key={chat.id}
                          className={`flex items-start gap-3 rounded-md p-3 cursor-pointer transition-colors ${
                            selectedChatIds.has(chat.id)
                              ? "bg-blue-50 dark:bg-blue-900/20"
                              : "hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-zinc-300 text-[#0078d4] focus:ring-[#0078d4]"
                            checked={selectedChatIds.has(chat.id)}
                            onChange={() => toggleChat(chat.id)}
                          />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100 truncate">
                              {chat.topic}
                            </p>
                            <p className="text-xs text-zinc-500">
                              {chat.chat_type}
                            </p>
                          </div>
                          <span className="text-xs text-zinc-400 whitespace-nowrap flex-shrink-0">
                            {chat.last_updated
                              ? new Date(
                                  chat.last_updated,
                                ).toLocaleDateString()
                              : ""}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Upload tab */}
              {activeTab === "upload" && (
                <div className="space-y-3">
                  <div
                    className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-zinc-300 dark:border-zinc-600 p-8 cursor-pointer hover:border-[#0078d4] transition-colors"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <svg
                      className="h-10 w-10 text-zinc-400 mb-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                      />
                    </svg>
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">
                      Click to upload PDF, DOCX, or TXT files
                    </p>
                    <p className="text-xs text-zinc-400 mt-1">
                      Multiple files supported
                    </p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      accept=".pdf,.docx,.txt,.xlsx"
                      multiple
                      onChange={handleFileChange}
                    />
                  </div>

                  {uploadedFiles.length > 0 && (
                    <div className="space-y-2">
                      {uploadedFiles.map((file, idx) => (
                        <div
                          key={`${file.name}-${idx}`}
                          className="flex items-center justify-between rounded-md bg-zinc-50 dark:bg-zinc-800/50 p-3"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <Badge>{file.name.split(".").pop()?.toUpperCase()}</Badge>
                            <span className="text-sm text-zinc-700 dark:text-zinc-300 truncate">
                              {file.name}
                            </span>
                            <span className="text-xs text-zinc-400">
                              {(file.size / 1024).toFixed(1)} KB
                            </span>
                          </div>
                          <button
                            onClick={() => removeFile(idx)}
                            className="text-zinc-400 hover:text-red-500 transition-colors p-1"
                          >
                            <svg
                              className="h-4 w-4"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                              />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Text tab */}
              {activeTab === "text" && (
                <textarea
                  className="w-full rounded-md border border-zinc-300 bg-white p-3 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 min-h-[200px] resize-y focus:outline-none focus:ring-2 focus:ring-[#0078d4] focus:border-transparent"
                  placeholder="Paste meeting notes, requirements, specs, or any text containing tasks..."
                  rows={8}
                  value={pastedText}
                  onChange={(e) => setPastedText(e.target.value)}
                />
              )}
            </CardContent>
          </Card>

          {/* Extra context */}
          <Card>
            <CardContent className="pt-6">
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                Additional Context (optional)
              </label>
              <textarea
                className="w-full rounded-md border border-zinc-300 bg-white p-3 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 resize-y focus:outline-none focus:ring-2 focus:ring-[#0078d4] focus:border-transparent"
                placeholder="E.g., 'This is for the Q2 mobile app project' or 'Focus on backend tasks only'..."
                rows={2}
                value={extraContext}
                onChange={(e) => setExtraContext(e.target.value)}
              />
            </CardContent>
          </Card>

          {/* Error */}
          {extractError && (
            <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
              {extractError}
            </div>
          )}

          {/* Extract button */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-500">
              {sourceCount > 0 ? (
                <>
                  <span className="font-medium text-zinc-900 dark:text-zinc-100">
                    {sourceCount}
                  </span>{" "}
                  source{sourceCount !== 1 ? "s" : ""} selected
                </>
              ) : (
                "Select at least one source to extract tasks."
              )}
            </p>
            <Button
              onClick={handleExtract}
              disabled={sourceCount === 0 || extracting}
            >
              {extracting ? (
                <>
                  <Spinner className="h-4 w-4" />
                  Extracting...
                </>
              ) : (
                "Extract Tasks"
              )}
            </Button>
          </div>
        </>
      )}

      {/* ================================================================ */}
      {/* STEP 2 — Review Tasks */}
      {/* ================================================================ */}
      {step === 2 && (
        <>
          {/* Source summary */}
          {extractionSources.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-wrap gap-2">
                  {extractionSources.map((src, i) => (
                    <Badge key={i}>
                      {src.label}: {src.task_count} task
                      {src.task_count !== 1 ? "s" : ""}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Task list */}
          <div className="space-y-3">
            {tasks.map((task, idx) => (
              <Card
                key={idx}
                className={
                  !checkedTasks.has(idx) ? "opacity-50" : ""
                }
              >
                <CardContent className="py-4">
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-zinc-300 text-[#0078d4] focus:ring-[#0078d4]"
                      checked={checkedTasks.has(idx)}
                      onChange={() => toggleTask(idx)}
                    />
                    <div className="flex-1 min-w-0 space-y-2">
                      {/* Title */}
                      <input
                        type="text"
                        className="w-full rounded border border-zinc-200 bg-transparent px-2 py-1 text-sm font-medium text-zinc-900 dark:text-zinc-100 dark:border-zinc-700 focus:outline-none focus:ring-1 focus:ring-[#0078d4]"
                        value={task.title}
                        onChange={(e) =>
                          updateTask(idx, "title", e.target.value)
                        }
                      />

                      {/* Description */}
                      {task.description && (
                        <p className="text-xs text-zinc-500 px-2">
                          {task.description}
                        </p>
                      )}

                      {/* Inline controls */}
                      <div className="flex flex-wrap items-center gap-3 px-2">
                        {/* Priority */}
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-zinc-500">
                            Priority:
                          </span>
                          <select
                            className="rounded border border-zinc-200 bg-white px-2 py-0.5 text-xs dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
                            value={task.priority ?? 5}
                            onChange={(e) =>
                              updateTask(
                                idx,
                                "priority",
                                Number(e.target.value),
                              )
                            }
                          >
                            <option value={1}>Urgent</option>
                            <option value={3}>High</option>
                            <option value={5}>Medium</option>
                            <option value={9}>Low</option>
                          </select>
                        </div>

                        {/* Bucket / Category */}
                        {task.bucket_name && (
                          <Badge>{task.bucket_name}</Badge>
                        )}

                        {/* Epic */}
                        {task.epic && (
                          <Badge variant="warning">{task.epic}</Badge>
                        )}

                        {/* Ticket ID */}
                        <span className="text-[10px] text-zinc-400 font-mono">
                          {task.ticket_id}
                        </span>
                      </div>
                    </div>

                    {/* Priority badge (right side) */}
                    <Badge
                      className={`flex-shrink-0 ${
                        PRIORITY_COLORS[task.priority ?? 5] ??
                        PRIORITY_COLORS[5]
                      }`}
                    >
                      {PRIORITY_LABELS[task.priority ?? 5] ?? "Medium"}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Error */}
          {extractError && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-400">
              {extractError}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="secondary" onClick={() => setStep(1)}>
                Back
              </Button>
              <p className="text-sm text-zinc-500">
                <span className="font-medium text-zinc-900 dark:text-zinc-100">
                  {selectedTaskCount}
                </span>{" "}
                of {tasks.length} task{tasks.length !== 1 ? "s" : ""} selected
              </p>
            </div>
            <Button
              onClick={() => {
                setPlanName("");
                setStep(3);
              }}
              disabled={selectedTaskCount === 0}
            >
              Continue to Create Project
            </Button>
          </div>
        </>
      )}

      {/* ================================================================ */}
      {/* STEP 3 — Create Project */}
      {/* ================================================================ */}
      {step === 3 && !createdPlanId && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Project Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Group selector */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                  Microsoft 365 Group
                </label>
                {loadingGroups ? (
                  <Spinner />
                ) : (
                  <select
                    className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                    value={selectedGroup}
                    onChange={(e) => setSelectedGroup(e.target.value)}
                  >
                    <option value="">Select a group...</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.displayName}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Plan name */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                  Plan Name
                </label>
                <input
                  type="text"
                  className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-[#0078d4] focus:border-transparent"
                  placeholder="E.g., Q2 Mobile App Sprint"
                  value={planName}
                  onChange={(e) => setPlanName(e.target.value)}
                />
              </div>

              {/* Task summary */}
              <div className="rounded-md bg-zinc-50 dark:bg-zinc-800/50 p-4">
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  <span className="font-medium text-zinc-900 dark:text-zinc-100">
                    {selectedTaskCount}
                  </span>{" "}
                  task{selectedTaskCount !== 1 ? "s" : ""} will be created with
                  auto-generated buckets.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Error */}
          {createError && (
            <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
              {createError}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between">
            <Button variant="secondary" onClick={() => setStep(2)}>
              Back
            </Button>
            <Button
              onClick={handleCreateProject}
              disabled={
                !selectedGroup || !planName.trim() || creating
              }
            >
              {creating ? (
                <>
                  <Spinner className="h-4 w-4" />
                  Creating...
                </>
              ) : (
                "Create Project"
              )}
            </Button>
          </div>
        </>
      )}

      {/* ================================================================ */}
      {/* STEP 3 — Success */}
      {/* ================================================================ */}
      {step === 3 && createdPlanId && (
        <Card>
          <CardContent className="py-12 text-center space-y-4">
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
              <svg
                className="h-8 w-8 text-green-600 dark:text-green-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                Project Created Successfully
              </h2>
              <p className="text-sm text-zinc-500 mt-1">
                {createdTaskCount} task{createdTaskCount !== 1 ? "s" : ""}{" "}
                synced to plan &ldquo;{planName}&rdquo;
              </p>
            </div>
            <div className="flex justify-center gap-3 pt-2">
              <Button variant="secondary" onClick={handleReset}>
                Create Another
              </Button>
              <a
                href={`https://tasks.office.com/`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button>Open in Planner</Button>
              </a>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
