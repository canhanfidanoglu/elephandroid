"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function ReportsPage() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-zinc-500">Please sign in to view reports.</p>
      </div>
    );
  }

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

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Document Reports</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center py-12 text-zinc-400 gap-2">
              <div className="h-12 w-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-xl">
                R
              </div>
              <p className="text-sm">PPTX/DOCX report generation coming soon.</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Natural Language Reports</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center py-12 text-zinc-400 gap-2">
              <div className="h-12 w-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-xl">
                NL
              </div>
              <p className="text-sm">Ask questions about project progress.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
