"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function ChatPage() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to use the chat.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Chat
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          RAG-powered chat with document ingestion and Planner task management.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Chat Interface</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-16 text-zinc-400 gap-3">
            <div className="h-12 w-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-xl">
              C
            </div>
            <p className="text-sm">Chat interface coming soon.</p>
            <p className="text-xs text-zinc-400 max-w-md text-center">
              Upload documents, ask questions with RAG context, and manage Planner tasks via natural language.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
