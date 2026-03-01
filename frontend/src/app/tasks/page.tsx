"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { getGroups, getPlans, getTasks, getBuckets } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Group, PlanInfo, TaskInfo, BucketInfo } from "@/types";
import { PRIORITY_LABELS, PRIORITY_COLORS } from "@/types";

export default function TasksPage() {
  const { user } = useAuth();

  const [groups, setGroups] = useState<Group[]>([]);
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [buckets, setBuckets] = useState<BucketInfo[]>([]);
  const [tasks, setTasks] = useState<TaskInfo[]>([]);

  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedPlan, setSelectedPlan] = useState("");

  const [loadingGroups, setLoadingGroups] = useState(false);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  // Load tasks + buckets when plan changes
  const loadTasks = useCallback(async () => {
    if (!selectedPlan) {
      setTasks([]);
      setBuckets([]);
      return;
    }
    setLoadingTasks(true);
    setError(null);
    try {
      const [t, b] = await Promise.all([
        getTasks(selectedPlan),
        getBuckets(selectedPlan),
      ]);
      setTasks(t);
      setBuckets(b);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load tasks");
    } finally {
      setLoadingTasks(false);
    }
  }, [selectedPlan]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const bucketMap = Object.fromEntries(buckets.map((b) => [b.id, b.name]));

  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to view tasks.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Tasks
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          View Planner tasks by group and plan.
        </p>
      </div>

      {/* Selectors */}
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
              onClick={loadTasks}
              disabled={!selectedPlan || loadingTasks}
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

      {/* Tasks list */}
      {loadingTasks ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : tasks.length > 0 ? (
        <div className="space-y-3">
          {tasks.map((task) => (
            <Card key={task.id}>
              <CardContent className="flex items-center justify-between gap-4 py-4">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-zinc-900 dark:text-zinc-100 truncate">
                    {task.title}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    {bucketMap[task.bucket_id] && (
                      <Badge>{bucketMap[task.bucket_id]}</Badge>
                    )}
                    {task.due_date && (
                      <span className="text-xs text-zinc-400">
                        Due: {new Date(task.due_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <Badge
                    className={
                      PRIORITY_COLORS[task.priority] ?? PRIORITY_COLORS[5]
                    }
                  >
                    {PRIORITY_LABELS[task.priority] ?? "Medium"}
                  </Badge>

                  <div className="w-20 text-right">
                    <span className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
                      {task.percent_complete}%
                    </span>
                    <div className="mt-1 h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-700">
                      <div
                        className="h-full rounded-full bg-[#0078d4] transition-all"
                        style={{ width: `${task.percent_complete}%` }}
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : selectedPlan ? (
        <div className="flex items-center justify-center py-12">
          <p className="text-zinc-400">No tasks found in this plan.</p>
        </div>
      ) : null}
    </div>
  );
}
