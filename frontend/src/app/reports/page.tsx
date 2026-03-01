"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import {
  getGroups,
  getPlans,
  getPlanProgress,
  getReportPptxUrl,
  getReportDocxUrl,
  streamNLReport,
} from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Group, PlanInfo, PlanReport } from "@/types";

const EXAMPLE_QUERIES = [
  "Bu haftaki ilerleme nasil?",
  "List overdue tasks",
  "Sprint burndown raporu",
  "Who has the most work?",
];

export default function ReportsPage() {
  const { user } = useAuth();

  // Plan selector state
  const [groups, setGroups] = useState<Group[]>([]);
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedPlan, setSelectedPlan] = useState("");
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [loadingPlans, setLoadingPlans] = useState(false);

  // Report data state
  const [report, setReport] = useState<PlanReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // NL query state
  const [nlQuery, setNlQuery] = useState("");
  const [nlResponse, setNlResponse] = useState("");
  const [nlStreaming, setNlStreaming] = useState(false);
  const nlResponseRef = useRef("");
  const responseEndRef = useRef<HTMLDivElement>(null);

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

  // Load report when plan changes
  const loadReport = useCallback(async () => {
    if (!selectedPlan) {
      setReport(null);
      return;
    }
    setLoadingReport(true);
    setError(null);
    try {
      const data = await getPlanProgress(selectedPlan);
      setReport(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load report");
    } finally {
      setLoadingReport(false);
    }
  }, [selectedPlan]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  // NL report streaming
  const handleNLQuery = useCallback(
    async (query: string) => {
      if (!selectedPlan || !query.trim()) return;
      setNlStreaming(true);
      setNlResponse("");
      nlResponseRef.current = "";

      await streamNLReport(
        selectedPlan,
        query.trim(),
        (chunk) => {
          nlResponseRef.current += chunk;
          setNlResponse(nlResponseRef.current);
        },
        () => {
          setNlStreaming(false);
        },
        (err) => {
          setNlResponse(
            nlResponseRef.current + `\n\n[Error: ${err.message}]`,
          );
          setNlStreaming(false);
        },
      );
    },
    [selectedPlan],
  );

  const handleClearNL = () => {
    setNlQuery("");
    setNlResponse("");
    nlResponseRef.current = "";
  };

  // Scroll to bottom of NL response as it streams
  useEffect(() => {
    if (nlStreaming) {
      responseEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [nlResponse, nlStreaming]);

  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to view reports.</p>
      </div>
    );
  }

  const totalInProgress = report
    ? report.total_tasks - report.completed_tasks - report.buckets.reduce((s, b) => s + b.not_started, 0)
    : 0;
  const totalNotStarted = report
    ? report.buckets.reduce((s, b) => s + b.not_started, 0)
    : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Reports
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Generate PPTX/DOCX reports or query progress with natural language.
        </p>
      </div>

      {/* Plan Selector */}
      <Card>
        <CardContent className="flex flex-wrap gap-4 pt-6">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              Group
            </label>
            {loadingGroups ? (
              <Spinner />
            ) : (
              <select
                className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                value={selectedGroup}
                onChange={(e) => {
                  setSelectedGroup(e.target.value);
                  setSelectedPlan("");
                  setReport(null);
                }}
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

          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-1">
              Plan
            </label>
            {loadingPlans ? (
              <Spinner />
            ) : (
              <select
                className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                value={selectedPlan}
                onChange={(e) => setSelectedPlan(e.target.value)}
                disabled={!selectedGroup}
              >
                <option value="">Select a plan...</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex items-end">
            <Button
              variant="secondary"
              onClick={loadReport}
              disabled={!selectedPlan || loadingReport}
            >
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading */}
      {loadingReport && (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      )}

      {/* Plan Progress & Document Reports */}
      {report && !loadingReport && (
        <div className="space-y-6">
          {/* Progress Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Plan Progress: {report.plan_name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Overall metrics */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="text-center p-3 rounded-lg bg-zinc-50 dark:bg-zinc-900">
                  <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                    {report.total_tasks}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">Total Tasks</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-green-50 dark:bg-green-900/20">
                  <p className="text-2xl font-bold text-green-700 dark:text-green-400">
                    {report.completed_tasks}
                  </p>
                  <p className="text-xs text-green-600 dark:text-green-500 mt-1">
                    Completed
                  </p>
                </div>
                <div className="text-center p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                  <p className="text-2xl font-bold text-blue-700 dark:text-blue-400">
                    {totalInProgress}
                  </p>
                  <p className="text-xs text-blue-600 dark:text-blue-500 mt-1">
                    In Progress
                  </p>
                </div>
                <div className="text-center p-3 rounded-lg bg-zinc-100 dark:bg-zinc-800">
                  <p className="text-2xl font-bold text-zinc-500">
                    {totalNotStarted}
                  </p>
                  <p className="text-xs text-zinc-400 mt-1">Not Started</p>
                </div>
              </div>

              {/* Overall completion bar */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Overall Completion
                  </span>
                  <span className="text-sm font-bold text-[#0078d4]">
                    {report.overall_percentage}%
                  </span>
                </div>
                <div className="h-3 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[#0078d4] transition-all duration-500"
                    style={{ width: `${report.overall_percentage}%` }}
                  />
                </div>
              </div>

              {/* Bucket breakdown */}
              {report.buckets.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">
                    Breakdown by Bucket
                  </h4>
                  <div className="space-y-3">
                    {report.buckets.map((bucket) => {
                      const pct =
                        bucket.total > 0
                          ? Math.round((bucket.completed / bucket.total) * 100)
                          : 0;
                      const inProgressPct =
                        bucket.total > 0
                          ? Math.round(
                              (bucket.in_progress / bucket.total) * 100,
                            )
                          : 0;
                      return (
                        <div key={bucket.name}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm text-zinc-600 dark:text-zinc-400">
                              {bucket.name}
                            </span>
                            <span className="text-xs text-zinc-500">
                              {bucket.completed}/{bucket.total} done
                            </span>
                          </div>
                          <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden flex">
                            <div
                              className="h-full bg-green-500 transition-all duration-500"
                              style={{ width: `${pct}%` }}
                            />
                            <div
                              className="h-full bg-blue-400 transition-all duration-500"
                              style={{ width: `${inProgressPct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-xs text-zinc-500">
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-3 h-3 rounded-full bg-green-500" />
                      Completed
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-3 h-3 rounded-full bg-blue-400" />
                      In Progress
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-3 h-3 rounded-full bg-zinc-200 dark:bg-zinc-700" />
                      Not Started
                    </span>
                  </div>
                </div>
              )}

              {/* Download buttons */}
              <div className="flex gap-3 pt-2">
                <Button
                  variant="primary"
                  onClick={() => window.open(getReportPptxUrl(selectedPlan))}
                >
                  Download PPTX
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => window.open(getReportDocxUrl(selectedPlan))}
                >
                  Download DOCX
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Natural Language Reports */}
          <Card>
            <CardHeader>
              <CardTitle>Natural Language Reports</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Query input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  className="flex-1 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm placeholder:text-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                  placeholder="Ask anything about your project..."
                  value={nlQuery}
                  onChange={(e) => setNlQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !nlStreaming) {
                      handleNLQuery(nlQuery);
                    }
                  }}
                  disabled={nlStreaming}
                />
                <Button
                  onClick={() => handleNLQuery(nlQuery)}
                  disabled={!nlQuery.trim() || nlStreaming}
                >
                  {nlStreaming ? "Generating..." : "Ask"}
                </Button>
                {(nlResponse || nlQuery) && (
                  <Button
                    variant="ghost"
                    onClick={handleClearNL}
                    disabled={nlStreaming}
                  >
                    Clear
                  </Button>
                )}
              </div>

              {/* Example query chips */}
              {!nlResponse && !nlStreaming && (
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_QUERIES.map((q) => (
                    <button
                      key={q}
                      className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs text-zinc-600 hover:bg-[#0078d4] hover:text-white hover:border-[#0078d4] transition-colors dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-[#0078d4] dark:hover:text-white"
                      onClick={() => {
                        setNlQuery(q);
                        handleNLQuery(q);
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}

              {/* Streaming response area */}
              {(nlResponse || nlStreaming) && (
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-900 max-h-[400px] overflow-y-auto">
                  {nlResponse ? (
                    <div className="text-sm text-zinc-800 dark:text-zinc-200 whitespace-pre-wrap leading-relaxed">
                      {renderMarkdown(nlResponse)}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-zinc-400">
                      <Spinner />
                      Analyzing project data...
                    </div>
                  )}
                  {nlStreaming && nlResponse && (
                    <span className="inline-block w-1.5 h-4 bg-[#0078d4] animate-pulse ml-0.5 align-text-bottom" />
                  )}
                  <div ref={responseEndRef} />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Empty state when no plan selected */}
      {!selectedPlan && !loadingReport && (
        <div className="flex flex-col items-center justify-center py-16 text-zinc-400 gap-3">
          <div className="h-16 w-16 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center">
            <svg
              className="h-8 w-8 text-zinc-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <p className="text-sm">Select a group and plan to view reports.</p>
        </div>
      )}
    </div>
  );
}

/**
 * Simple markdown renderer: bold, lists, line breaks.
 */
function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Bullet list items
    if (/^[\s]*[-*]\s/.test(line)) {
      const content = line.replace(/^[\s]*[-*]\s/, "");
      elements.push(
        <div key={i} className="flex gap-2 ml-2">
          <span className="text-zinc-400 select-none">-</span>
          <span>{applyInlineFormatting(content)}</span>
        </div>,
      );
      continue;
    }

    // Numbered list items
    if (/^[\s]*\d+[.)]\s/.test(line)) {
      const match = line.match(/^([\s]*\d+[.)]\s)(.*)/);
      if (match) {
        elements.push(
          <div key={i} className="flex gap-2 ml-2">
            <span className="text-zinc-400 select-none">{match[1].trim()}</span>
            <span>{applyInlineFormatting(match[2])}</span>
          </div>,
        );
        continue;
      }
    }

    // Headers (### or ##)
    if (/^#{1,3}\s/.test(line)) {
      const content = line.replace(/^#{1,3}\s/, "");
      elements.push(
        <p key={i} className="font-semibold mt-2">
          {content}
        </p>,
      );
      continue;
    }

    // Empty lines
    if (!line.trim()) {
      elements.push(<br key={i} />);
      continue;
    }

    // Regular text
    elements.push(
      <p key={i}>{applyInlineFormatting(line)}</p>,
    );
  }

  return <>{elements}</>;
}

function applyInlineFormatting(text: string): React.ReactNode {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
}
