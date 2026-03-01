"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function WizardPage() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to use the wizard.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Project Wizard
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Extract tasks from multiple sources and create a Planner project in one step.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[
          { title: "Paste Text", desc: "Paste meeting notes, specs, or any text to extract tasks." },
          { title: "Outlook Email", desc: "Pull tasks from your Outlook inbox messages." },
          { title: "Teams Chat", desc: "Extract action items from Teams conversations." },
          { title: "Upload Document", desc: "Upload PDF, DOCX, or TXT files for task extraction." },
          { title: "Meeting Transcript", desc: "Import a Teams meeting transcript and extract tasks." },
        ].map(({ title, desc }) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle className="text-base">{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-zinc-500">{desc}</p>
              <p className="text-xs text-zinc-400 mt-3">Coming soon</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
