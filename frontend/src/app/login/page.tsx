"use client";

import { getLoginUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function LoginPage() {
  return (
    <div className="flex items-center justify-center py-24">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center">Sign in</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          <p className="text-sm text-zinc-500 text-center">
            Sign in with your Microsoft 365 account to access Elephandroid.
          </p>
          <a href={getLoginUrl()}>
            <Button>Sign in with Microsoft</Button>
          </a>
        </CardContent>
      </Card>
    </div>
  );
}
