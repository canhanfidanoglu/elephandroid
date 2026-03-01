"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const FEATURES = [
  {
    title: "Tasks",
    description: "View and manage Planner tasks synced from Excel or AI extraction.",
    href: "/tasks",
  },
  {
    title: "Chat",
    description: "RAG-powered chat with document ingestion and task management.",
    href: "/chat",
  },
  {
    title: "Reports",
    description: "Generate PPTX/DOCX reports or ask natural language questions about progress.",
    href: "/reports",
  },
  {
    title: "Meetings",
    description: "View Teams meeting transcripts and AI-generated summaries.",
    href: "/meetings",
  },
  {
    title: "Wizard",
    description: "Multi-source project wizard: extract tasks from emails, chats, and documents.",
    href: "/wizard",
  },
];

export default function DashboardPage() {
  const { user, loading, loginUrl } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-400">Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-6">
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
          Elephandroid
        </h1>
        <p className="text-zinc-500 max-w-md text-center">
          MS365 enterprise automation: Excel sync, AI task extraction, RAG chat, reports, and more.
        </p>
        <a href={loginUrl}>
          <Button>Sign in with Microsoft</Button>
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Dashboard
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Welcome back. Select a module to get started.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ title, description, href }) => (
          <Link key={href} href={href}>
            <Card className="h-full transition-shadow hover:shadow-md cursor-pointer">
              <CardHeader>
                <CardTitle>{title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-zinc-500">{description}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
