"use client";

import { useAuth } from "@/components/providers/auth-provider";
import { getLogoutUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function Header() {
  const { user, loading, loginUrl } = useAuth();

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-zinc-200 bg-white/80 px-6 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
      <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
        MS365 Enterprise Automation
      </h2>

      <div className="flex items-center gap-3">
        {loading ? (
          <span className="text-sm text-zinc-400">Loading...</span>
        ) : user ? (
          <>
            <span className="text-sm text-zinc-600 dark:text-zinc-400">
              {user.user_id.slice(0, 8)}...
            </span>
            <a href={getLogoutUrl()}>
              <Button variant="ghost" className="text-xs">
                Sign out
              </Button>
            </a>
          </>
        ) : (
          <a href={loginUrl}>
            <Button className="text-xs">Sign in with Microsoft</Button>
          </a>
        )}
      </div>
    </header>
  );
}
