"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function MeetingsPage() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to view meetings.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Meetings
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          View Teams meeting transcripts and AI-generated summaries.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Meeting Transcripts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-16 text-zinc-400 gap-3">
            <div className="h-12 w-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-xl">
              M
            </div>
            <p className="text-sm">Meeting transcript viewer coming soon.</p>
            <p className="text-xs text-zinc-400 max-w-md text-center">
              Browse recent Teams meetings, view transcripts, and get AI-powered summaries.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
