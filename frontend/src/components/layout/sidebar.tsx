"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "H" },
  { href: "/tasks", label: "Tasks", icon: "T" },
  { href: "/chat", label: "Chat", icon: "C" },
  { href: "/reports", label: "Reports", icon: "R" },
  { href: "/meetings", label: "Meetings", icon: "M" },
  { href: "/wizard", label: "Wizard", icon: "W" },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-56 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex h-14 items-center border-b border-zinc-200 px-4 dark:border-zinc-800">
        <Link href="/" className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
          Elephandroid
        </Link>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-[#0078d4]/10 text-[#0078d4]"
                  : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
              }`}
            >
              <span className="flex h-6 w-6 items-center justify-center rounded bg-zinc-100 text-xs font-bold dark:bg-zinc-800">
                {icon}
              </span>
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
        <p className="text-xs text-zinc-400">
          MS365 Enterprise Automation
        </p>
      </div>
    </aside>
  );
}
